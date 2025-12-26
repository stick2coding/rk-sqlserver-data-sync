"""
数据库连接模块
负责建立和管理SQL Server数据库连接
"""

import pyodbc
import time
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager
from src.logger import get_logger

logger = get_logger(__name__)


class DatabaseConnector:
    """数据库连接器类"""
    
    def __init__(self, db_config: Dict[str, str], 
                 retry_times: int = 3, 
                 retry_interval: int = 5):
        """初始化数据库连接器
        
        Args:
            db_config: 数据库配置字典
            retry_times: 连接失败重试次数
            retry_interval: 连接失败重试间隔（秒）
        """
        self.db_config = db_config
        self.retry_times = retry_times
        self.retry_interval = retry_interval
        self._connection: Optional[pyodbc.Connection] = None
        self._last_used = 0  # 记录连接最后使用时间
        self._skip_connection_test = False  # 是否跳过连接测试（优化性能）
        self._cursor: Optional[pyodbc.Cursor] = None  # 复用cursor对象（性能优化）
    
    def get_connection_string(self) -> str:
        """构建连接字符串（包含性能优化选项）
        
        Returns:
            str: ODBC连接字符串
        """
        return (
            f"DRIVER={{{self.db_config['driver']}}};"
            f"SERVER={self.db_config['server']};"
            f"DATABASE={self.db_config['database']};"
            f"UID={self.db_config['username']};"
            f"PWD={self.db_config['password']};"
            "TrustServerCertificate=yes;"
            "Connection Timeout=30;"     # 连接超时30秒
            "Query Timeout=300;"          # 查询超时5分钟
            "MARS_Connection=yes;"        # 启用Multiple Active Result Sets
            "ANSI_defaults=OFF;"        # 禁用ANSI默认值（提升性能）
            "AutoTranslate=no;"          # 禁用自动字符集转换（提升性能）
            "UseProcForPrepare=0;"      # 禁用存储过程准备（提升性能）
        )
    
    def connect(self, skip_test: bool = False) -> pyodbc.Connection:
        """建立数据库连接
        
        Args:
            skip_test: 是否跳过连接测试（用于性能优化）
            
        Returns:
            pyodbc.Connection: 数据库连接对象
            
        Raises:
            Exception: 连接失败且重试次数用尽
        """
        current_time = time.time()
        
        # 如果连接存在且未过期（30分钟内），直接复用
        if self._connection is not None:
            # 如果跳过测试或者连接在30分钟内使用过，直接返回
            if skip_test or (current_time - self._last_used < 1800):
                self._last_used = current_time
                return self._connection
            
            # 否则测试连接是否仍然有效
            try:
                self._connection.execute("SELECT 1").fetchone()
                self._last_used = current_time
                return self._connection
            except Exception as e:
                logger.warning(f"现有连接已失效，将重新连接: {e}")
                self.close()
        
        connection_string = self.get_connection_string()
        last_exception = None
        
        for attempt in range(self.retry_times):
            try:
                logger.info(f"尝试连接数据库 {self.db_config['database']} (第{attempt + 1}次)")
                self._connection = pyodbc.connect(connection_string)
                self._last_used = current_time
                logger.info(f"成功连接到数据库: {self.db_config['server']}.{self.db_config['database']}")
                return self._connection
                
            except Exception as e:
                last_exception = e
                logger.warning(f"连接数据库失败 (第{attempt + 1}次): {e}")
                
                if attempt < self.retry_times - 1:
                    logger.info(f"等待{self.retry_interval}秒后重试...")
                    time.sleep(self.retry_interval)
        
        logger.error(f"连接数据库失败，已重试{self.retry_times}次")
        raise Exception(f"无法连接到数据库: {last_exception}")
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self._cursor is not None:
            try:
                self._cursor.close()
            except Exception as e:
                logger.debug(f"关闭cursor时发生错误: {e}")
            finally:
                self._cursor = None
                
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("数据库连接已关闭")
            except Exception as e:
                logger.error(f"关闭数据库连接时发生错误: {e}")
            finally:
                self._connection = None
                self._last_used = 0
    
    def _get_cursor(self) -> pyodbc.Cursor:
        """获取或创建cursor（复用以提升性能）
        
        Returns:
            pyodbc.Cursor: cursor对象
        """
        conn = self.connect(skip_test=True)
        
        # 复用cursor对象，避免每次查询都创建新cursor
        if self._cursor is None:
            self._cursor = conn.cursor()
        elif self._cursor.connection is None:
            # 如果cursor的连接已关闭，重新创建
            self._cursor = conn.cursor()
            
        return self._cursor
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[pyodbc.Row]:
        """执行查询语句（优化性能：复用cursor、优化连接字符串）
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            List[pyodbc.Row]: 查询结果列表
        """
        start_time = time.time()
        execute_time = 0
        fetch_time = 0
        
        # 复用cursor对象
        cursor = self._get_cursor()
        
        # 只在DEBUG级别输出SQL详细信息
        if logger.isEnabledFor(logger.level) and logger.level <= 10:  # DEBUG level
            if params and len(params) > 50:
                logger.debug(f"执行查询，SQL长度: {len(query)}字符，参数数量: {len(params)}")
            else:
                logger.debug(f"执行查询: {query}，参数: {params}")
        
        try:
            if params:
                exec_start = time.time()
                cursor.execute(query, params)
                execute_time = time.time() - exec_start
            else:
                exec_start = time.time()
                cursor.execute(query)
                execute_time = time.time() - exec_start
            
            # 优化：使用fetchall()，但记录执行和获取时间
            fetch_start = time.time()
            results = cursor.fetchall()
            fetch_time = time.time() - fetch_start
            
            elapsed_time = time.time() - start_time
            
            # 如果查询耗时超过1秒，记录警告和详细时间分解
            if elapsed_time > 1.0:
                logger.warning(f"查询耗时较长: {elapsed_time:.2f}秒 (执行: {execute_time:.2f}秒, 获取: {fetch_time:.2f}秒, 行数: {len(results)})")
            
            return results
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"执行查询失败 (耗时: {elapsed_time:.2f}秒): {e}")
            logger.error(f"查询语句: {query[:500]}...")  # 只输出SQL的前500个字符
            if params:
                logger.error(f"参数数量: {len(params)}")
            
            # 发生错误时重置cursor
            try:
                if self._cursor:
                    self._cursor.close()
                    self._cursor = None
            except:
                pass
                
            raise
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """执行更新/插入/删除语句
        
        Args:
            query: SQL语句
            params: SQL参数
            
        Returns:
            int: 受影响的行数
        """
        conn = self.connect(skip_test=True)
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            affected_rows = cursor.rowcount
            logger.debug(f"执行更新成功，影响行数: {affected_rows}")
            return affected_rows
            
        except Exception as e:
            conn.rollback()
            logger.error(f"执行更新失败: {e}")
            logger.error(f"SQL语句: {query}")
            raise
        finally:
            cursor.close()
    
    def execute_batch_update(self, query: str, data: List[Tuple]) -> int:
        """批量执行更新/插入语句
        
        Args:
            query: SQL语句
            data: 数据列表
            
        Returns:
            int: 受影响的行数
        """
        conn = self.connect(skip_test=True)
        cursor = conn.cursor()
        
        try:
            cursor.executemany(query, data)
            conn.commit()
            affected_rows = cursor.rowcount
            logger.debug(f"批量更新成功，影响行数: {affected_rows}")
            return affected_rows
            
        except Exception as e:
            conn.rollback()
            logger.error(f"批量更新失败: {e}")
            logger.error(f"SQL语句: {query}")
            raise
        finally:
            cursor.close()
    
    def get_table_columns(self, table_name: str, schema: str = 'dbo') -> List[Dict[str, Any]]:
        """获取表的列信息
        
        Args:
            table_name: 表名
            schema: 架构名（默认为dbo）
            
        Returns:
            List[Dict[str, Any]]: 列信息列表
        """
        query = """
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
                   IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ? AND TABLE_SCHEMA = ?
            ORDER BY ORDINAL_POSITION
        """
        results = self.execute_query(query, (table_name, schema))
        
        columns = []
        for row in results:
            columns.append({
                'name': row.COLUMN_NAME,
                'type': row.DATA_TYPE,
                'length': row.CHARACTER_MAXIMUM_LENGTH,
                'nullable': row.IS_NULLABLE == 'YES',
                'default': row.COLUMN_DEFAULT
            })
        
        return columns
    
    def get_table_count(self, table_name: str, schema: str = 'dbo') -> int:
        """获取表的行数
        
        Args:
            table_name: 表名
            schema: 架构名（默认为dbo）
            
        Returns:
            int: 表的行数
        """
        query = f"SELECT COUNT(*) FROM [{schema}].[{table_name}]"
        results = self.execute_query(query)
        return results[0][0] if results else 0
    
    def table_exists(self, table_name: str, schema: str = 'dbo') -> bool:
        """检查表是否存在
        
        Args:
            table_name: 表名
            schema: 架构名（默认为dbo）
            
        Returns:
            bool: 表是否存在
        """
        query = """
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = ? AND TABLE_SCHEMA = ?
        """
        results = self.execute_query(query, (table_name, schema))
        return results[0][0] > 0
    
    def get_max_value(self, table_name: str, column_name: str, schema: str = 'dbo') -> Any:
        """获取表中某列的最大值
        
        Args:
            table_name: 表名
            column_name: 列名
            schema: 架构名（默认为dbo）
            
        Returns:
            Any: 最大值，如果表为空则返回None
        """
        query = f"SELECT MAX([{column_name}]) FROM [{schema}].[{table_name}]"
        results = self.execute_query(query)
        return results[0][0] if results and results[0][0] is not None else None
    
    def truncate_table(self, table_name: str, schema: str = 'dbo') -> None:
        """清空表数据
        
        Args:
            table_name: 表名
            schema: 架构名（默认为dbo）
        """
        query = f"TRUNCATE TABLE [{schema}].[{table_name}]"
        self.execute_update(query)
        logger.info(f"已清空表: [{schema}].[{table_name}]")
    
    def begin_transaction(self) -> None:
        """开始事务"""
        conn = self.connect(skip_test=True)
        conn.autocommit = False
        logger.debug("事务已开始")
    
    def commit_transaction(self) -> None:
        """提交事务"""
        conn = self.connect(skip_test=True)
        conn.commit()
        logger.debug("事务已提交")
    
    def rollback_transaction(self) -> None:
        """回滚事务"""
        conn = self.connect(skip_test=True)
        conn.rollback()
        logger.warning("事务已回滚")
    
    def use_database(self, database_name: str) -> None:
        """切换到指定数据库
        
        Args:
            database_name: 数据库名称
        """
        conn = self.connect(skip_test=True)
        try:
            conn.execute(f"USE [{database_name}]")
            logger.debug(f"已切换到数据库: {database_name}")
        except Exception as e:
            logger.error(f"切换数据库失败: {e}")
            raise
    
    def __del__(self):
        """析构函数，自动关闭连接"""
        self.close()


@contextmanager
def transaction(db_connector: DatabaseConnector):
    """事务上下文管理器
    
    Args:
        db_connector: 数据库连接器
        
    Yields:
        DatabaseConnector: 数据库连接器
    """
    try:
        db_connector.begin_transaction()
        yield db_connector
        db_connector.commit_transaction()
    except Exception as e:
        db_connector.rollback_transaction()
        logger.error(f"事务执行失败，已回滚: {e}")
        raise
