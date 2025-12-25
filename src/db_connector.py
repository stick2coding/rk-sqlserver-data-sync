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
    
    def get_connection_string(self) -> str:
        """构建连接字符串
        
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
        )
    
    def connect(self) -> pyodbc.Connection:
        """建立数据库连接
        
        Returns:
            pyodbc.Connection: 数据库连接对象
            
        Raises:
            Exception: 连接失败且重试次数用尽
        """
        if self._connection is not None:
            try:
                # 测试连接是否仍然有效
                self._connection.execute("SELECT 1").fetchone()
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
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("数据库连接已关闭")
            except Exception as e:
                logger.error(f"关闭数据库连接时发生错误: {e}")
            finally:
                self._connection = None
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[pyodbc.Row]:
        """执行查询语句
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            List[pyodbc.Row]: 查询结果列表
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            return results
            
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            logger.error(f"查询语句: {query}")
            raise
        finally:
            cursor.close()
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """执行更新/插入/删除语句
        
        Args:
            query: SQL语句
            params: SQL参数
            
        Returns:
            int: 受影响的行数
        """
        conn = self.connect()
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
        conn = self.connect()
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
        conn = self.connect()
        conn.autocommit = False
        logger.debug("事务已开始")
    
    def commit_transaction(self) -> None:
        """提交事务"""
        conn = self.connect()
        conn.commit()
        logger.debug("事务已提交")
    
    def rollback_transaction(self) -> None:
        """回滚事务"""
        conn = self.connect()
        conn.rollback()
        logger.warning("事务已回滚")
    
    def use_database(self, database_name: str) -> None:
        """切换到指定数据库
        
        Args:
            database_name: 数据库名称
        """
        conn = self.connect()
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
