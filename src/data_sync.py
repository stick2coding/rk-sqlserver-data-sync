"""
数据同步核心模块
负责实现数据同步的主要逻辑
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.db_connector import DatabaseConnector
from src.logger import get_logger

logger = get_logger(__name__)


class DataSync:
    """数据同步类"""
    
    def __init__(self, 
                 source_db: DatabaseConnector, 
                 target_db: DatabaseConnector,
                 batch_size: int = 1000,
                 related_table_config: Dict[str, str] = None):
        """初始化数据同步器
        
        Args:
            source_db: 源数据库连接器
            target_db: 目标数据库连接器
            batch_size: 批处理大小
            related_table_config: 关联表数据库配置
        """
        self.source_db = source_db
        self.target_db = target_db
        self.batch_size = batch_size
        self.related_table_config = related_table_config or {}
        self.sync_stats = {
            'total_tables': 0,
            'success_tables': 0,
            'failed_tables': 0,
            'total_rows': 0,
            'synced_rows': 0,
            'start_time': None,
            'end_time': None
        }
    
    def sync_table(self, table_config: Dict[str, Any]) -> Dict[str, Any]:
        """同步单个表
        
        Args:
            table_config: 表配置字典
            
        Returns:
            Dict[str, Any]: 同步结果
        """
        table_name = table_config['table_name']
        schema = table_config.get('schema', 'dbo')
        sync_mode = table_config['sync_mode']
        sync_strategy = table_config['sync_strategy']
        primary_key = table_config['primary_key']
        
        # 获取表级别的数据库配置（如果有）
        table_source_db = table_config.get('source_database', self.source_db.db_config['database'])
        table_target_db = table_config.get('target_database', self.target_db.db_config['database'])
        
        logger.info(f"开始同步表: [{table_source_db}].[{schema}].[{table_name}] -> [{table_target_db}].[{schema}].[{table_name}] (模式: {sync_mode}, 策略: {sync_strategy})")
        
        table_stats = {
            'table_name': table_name,
            'status': 'success',
            'source_rows': 0,
            'synced_rows': 0,
            'inserted_rows': 0,
            'skipped_rows': 0,
            'related_synced_rows': 0,
            'related_existing_count': 0,
            'related_inserted_count': 0,
            'related_skipped_count': 0,
            'error': None
        }
        
        try:
            # 切换到源数据库（根据表配置）
            logger.info(f"切换到源数据库: {table_source_db}")
            self.source_db.use_database(table_source_db)
            
            # 检查源表是否存在
            if not self.source_db.table_exists(table_name, schema):
                raise Exception(f"源表不存在: [{table_source_db}].[{schema}].[{table_name}]")
            
            # 获取源表的列信息
            source_columns = self.source_db.get_table_columns(table_name, schema)
            column_names = [col['name'] for col in source_columns]
            
            # 获取字段黑名单
            field_blacklist = table_config.get('field_blacklist', [])
            if field_blacklist:
                logger.info(f"字段黑名单: {field_blacklist}")
            
            # 获取源表数据
            logger.info(f"获取表 [{table_source_db}].[{schema}].[{table_name}] 的数据...")
            source_data = self._fetch_table_data(
                table_name, 
                column_names, 
                sync_mode, 
                table_config,
                schema
            )
            
            table_stats['source_rows'] = len(source_data)
            logger.info(f"表 [{table_source_db}].[{schema}].[{table_name}] 源数据行数: {table_stats['source_rows']}")
            
            if table_stats['source_rows'] == 0:
                logger.info(f"表 [{table_source_db}].[{schema}].[{table_name}] 没有数据需要同步")
                return table_stats
            
            # 切换到目标数据库（根据表配置）
            logger.info(f"切换到目标数据库: {table_target_db}")
            self.target_db.use_database(table_target_db)
            
            # 检查目标表是否存在，如果不存在则需要创建
            if not self.target_db.table_exists(table_name, schema):
                logger.warning(f"目标表不存在: [{table_target_db}].[{schema}].[{table_name}]，跳过同步（建议先创建表结构）")
                table_stats['status'] = 'skipped'
                table_stats['error'] = '目标表不存在'
                return table_stats
            
            # 如果是覆盖策略，先清空目标表
            if sync_strategy == 'overwrite':
                logger.info(f"清空目标表: [{table_target_db}].[{schema}].[{table_name}]")
                self.target_db.truncate_table(table_name, schema)
                # 执行数据插入
                self._insert_data(table_name, source_data, column_names, schema, field_blacklist)
                table_stats['synced_rows'] = len(source_data)
                table_stats['inserted_rows'] = len(source_data)
                table_stats['skipped_rows'] = 0
            elif sync_strategy == 'append':
                logger.info(f"使用追加模式同步表: [{table_target_db}].[{schema}].[{table_name}]")
                # 使用临时表模式，先过滤已存在的记录再插入
                insert_stats = self._insert_data_with_temp_table(
                    table_name, 
                    source_data, 
                    column_names, 
                    primary_key,
                    schema,
                    field_blacklist
                )
                table_stats['synced_rows'] = len(source_data)
                table_stats['inserted_rows'] = insert_stats.get('inserted', 0)
                table_stats['skipped_rows'] = insert_stats.get('skipped', 0)
                logger.info(f"表 {table_name} 追加同步完成，源数据 {len(source_data)} 行，插入 {table_stats['inserted_rows']} 行，跳过重复 {table_stats['skipped_rows']} 行")
            else:
                raise Exception(f"不支持的同步策略: {sync_strategy}")
            logger.info(f"表 {table_name} 同步完成，同步行数: {table_stats['synced_rows']}")
            
            # 更新统计信息
            self.sync_stats['synced_rows'] += table_stats['synced_rows']
            
            # 检查是否需要同步关联表WFC_PROCESS
            if table_config.get('sync_related_table', False) and 'BINDID' in column_names:
                logger.info(f"检测到BINDID字段，准备同步关联表WFC_PROCESS")
                # 传入 table_config 以便获取源表数据库信息
                related_stats = self._sync_related_wfc_process(table_name, schema, source_data, column_names, table_config)
                table_stats['related_synced_rows'] = related_stats.get('total', 0)
                table_stats['related_existing_count'] = related_stats.get('existing', 0)
                table_stats['related_inserted_count'] = related_stats.get('inserted', 0)
                table_stats['related_skipped_count'] = related_stats.get('skipped', 0)
                logger.info(f"WFC_PROCESS关联表同步完成: 已存在 {table_stats['related_existing_count']}, 插入 {table_stats['related_inserted_count']}, 跳过重复 {table_stats['related_skipped_count']}")
            
        except Exception as e:
            table_stats['status'] = 'failed'
            table_stats['error'] = str(e)
            logger.error(f"同步表 {table_name} 失败: {e}")
        
        return table_stats
    
    def _fetch_table_data(self, 
                          table_name: str, 
                          column_names: List[str],
                          sync_mode: str,
                          table_config: Dict[str, Any],
                          schema: str = 'dbo') -> List[tuple]:
        """从源表获取数据
        
        Args:
            table_name: 表名
            column_names: 列名列表
            sync_mode: 同步模式
            table_config: 表配置
            schema: 架构名（默认为dbo）
            
        Returns:
            List[tuple]: 数据行列表
        """
        # 构建列名字符串，对列名加方括号防止SQL注入
        columns_str = ', '.join([f"[{col}]" for col in column_names])
        full_table_name = f"[{schema}].[{table_name}]"
        
        if sync_mode == 'full':
            # 全量同步：获取所有数据
            query = f"SELECT {columns_str} FROM {full_table_name}"
            logger.debug(f"全量同步查询: {query}")
            results = self.source_db.execute_query(query)
            
        elif sync_mode == 'incremental':
            # 增量同步：根据last_sync_field获取新增/更新的数据
            last_sync_field = table_config.get('last_sync_field')
            if not last_sync_field:
                raise Exception("增量同步必须配置last_sync_field")
            
            # 获取目标表中该字段的最大值
            max_value = self.target_db.get_max_value(table_name, last_sync_field, schema)
            
            if max_value is None:
                # 目标表为空，获取所有数据
                query = f"SELECT {columns_str} FROM {full_table_name}"
                logger.debug(f"目标表为空，执行全量查询: {query}")
                results = self.source_db.execute_query(query)
            else:
                # 获取大于最大值的数据
                # 根据字段类型构建条件
                query = f"SELECT {columns_str} FROM {full_table_name} WHERE [{last_sync_field}] > ?"
                logger.debug(f"增量同步查询: {query}, 参数: {max_value}")
                results = self.source_db.execute_query(query, (max_value,))
        
        else:
            raise Exception(f"不支持的同步模式: {sync_mode}")
        
        # 转换为tuple列表
        data = [tuple(row) for row in results]
        return data
    
    def _apply_field_blacklist(self, 
                            data: List[tuple], 
                            column_names: List[str],
                            field_blacklist: List[str]) -> tuple:
        """应用字段黑名单，从列名和数据中移除黑名单字段
        
        Args:
            data: 数据列表
            column_names: 列名列表
            field_blacklist: 字段黑名单列表
            
        Returns:
            tuple: (过滤后的数据列表, 过滤后的列名列表)
        """
        if not field_blacklist:
            return data, column_names
        
        # 创建黑名单字段的索引集合（大小写不敏感）
        blacklist_upper = [field.upper() for field in field_blacklist]
        blacklist_indices = set()
        
        for i, col_name in enumerate(column_names):
            if col_name.upper() in blacklist_upper:
                blacklist_indices.add(i)
        
        if not blacklist_indices:
            logger.debug("没有需要处理的黑名单字段")
            return data, column_names
        
        logger.info(f"应用字段黑名单，移除字段索引: {blacklist_indices}")
        
        # 构建过滤后的列名列表
        filtered_column_names = [col for i, col in enumerate(column_names) if i not in blacklist_indices]
        logger.info(f"过滤后的列名: {filtered_column_names}")
        
        # 从数据中移除黑名单字段的值
        processed_data = []
        for row in data:
            processed_row = [val for i, val in enumerate(row) if i not in blacklist_indices]
            processed_data.append(tuple(processed_row))
        
        return processed_data, filtered_column_names
    
    def _insert_data(self, 
                    table_name: str, 
                    data: List[tuple], 
                    column_names: List[str],
                    schema: str = 'dbo',
                    field_blacklist: List[str] = None) -> None:
        """批量插入数据到目标表
        
        Args:
            table_name: 目标表名
            data: 数据列表
            column_names: 列名列表
            schema: 架构名（默认为dbo）
            field_blacklist: 字段黑名单列表
        """
        if not data:
            return
        
        # 应用字段黑名单，返回过滤后的数据和列名
        if field_blacklist:
            data, column_names = self._apply_field_blacklist(data, column_names, field_blacklist)
        
        # 构建插入SQL（使用过滤后的列名）
        columns_str = ', '.join([f"[{col}]" for col in column_names])
        placeholders = ', '.join(['?' for _ in column_names])
        full_table_name = f"[{schema}].[{table_name}]"
        insert_sql = f"INSERT INTO {full_table_name} ({columns_str}) VALUES ({placeholders})"
        
        logger.debug(f"插入SQL: {insert_sql}")
        logger.debug(f"总数据行数: {len(data)}, 批处理大小: {self.batch_size}")
        
        # 分批插入数据
        total_inserted = 0
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i + self.batch_size]
            try:
                self.target_db.execute_batch_update(insert_sql, batch)
                total_inserted += len(batch)
                logger.debug(f"已插入 {total_inserted}/{len(data)} 行")
            except Exception as e:
                logger.error(f"批量插入数据失败 (批次 {i//self.batch_size + 1}): {e}")
                raise
        
        logger.info(f"成功插入 {total_inserted} 行数据到表 [{schema}].[{table_name}]")
    
    def _insert_data_with_temp_table(self, 
                                  table_name: str, 
                                  data: List[tuple], 
                                  column_names: List[str],
                                  primary_key: str,
                                  schema: str = 'dbo',
                                  field_blacklist: List[str] = None) -> Dict[str, int]:
        """使用临时表模式插入数据到目标表（append模式专用）
        
        步骤：
        1. 创建临时表，存储待插入数据的主键ID
        2. 将所有待插入数据的主键ID插入临时表
        3. 通过关联查询，找出目标表中已存在的ID
        4. 过滤掉已存在的数据
        5. 只插入目标表中不存在的数据
        
        Args:
            table_name: 目标表名
            data: 数据列表
            column_names: 列名列表
            primary_key: 主键列名
            schema: 架构名（默认为dbo）
            field_blacklist: 字段黑名单列表
            
        Returns:
            Dict[str, int]: 统计信息 {'inserted': 成功插入数, 'skipped': 跳过数}
        """
        if not data:
            return {'inserted': 0, 'skipped': 0, 'error': 0}
        
        # 应用字段黑名单，返回过滤后的数据和列名
        if field_blacklist:
            data, column_names = self._apply_field_blacklist(data, column_names, field_blacklist)
        
        import time
        start_time = time.time()
        
        # 获取主键在列中的索引
        pk_index = None
        for i, col_name in enumerate(column_names):
            if col_name.upper() == primary_key.upper():
                pk_index = i
                break
        
        if pk_index is None:
            raise Exception(f"未找到主键列 {primary_key}")
        
        full_table_name = f"[{schema}].[{table_name}]"
        temp_table_name = f"#{table_name}_temp_{int(time.time() * 1000)}"
        
        try:
            # 1. 创建临时表
            logger.info(f"创建临时表: {temp_table_name}")
            create_temp_sql = f"""
                CREATE TABLE {temp_table_name} (
                    [{primary_key}] SQL_VARIANT PRIMARY KEY
                )
            """
            self.target_db.execute_update(create_temp_sql)
            
            # 2. 批量插入主键ID到临时表
            logger.info(f"插入主键ID到临时表...")
            pk_values = [(row[pk_index],) for row in data]
            
            insert_temp_sql = f"INSERT INTO {temp_table_name} ([{primary_key}]) VALUES (?)"
            temp_inserted = 0
            for i in range(0, len(pk_values), self.batch_size):
                batch = pk_values[i:i + self.batch_size]
                self.target_db.execute_batch_update(insert_temp_sql, batch)
                temp_inserted += len(batch)
            
            logger.info(f"已插入 {temp_inserted} 个主键ID到临时表")
            
            # 3. 通过关联查询找出目标表中已存在的ID
            logger.info(f"通过临时表查询目标表中已存在的ID...")
            query_existing_sql = f"""
                SELECT t.[{primary_key}]
                FROM {temp_table_name} t
                INNER JOIN {full_table_name} d ON t.[{primary_key}] = d.[{primary_key}]
            """
            existing_results = self.target_db.execute_query(query_existing_sql)
            existing_ids = set(row[0] for row in existing_results if row[0] is not None)
            
            logger.info(f"目标表中已存在 {len(existing_ids)} 条记录")
            
            # 4. 过滤掉已存在的数据
            filtered_data = []
            for row in data:
                if row[pk_index] not in existing_ids:
                    filtered_data.append(row)
            
            logger.info(f"过滤后需要插入的数据: {len(filtered_data)} 行，跳过重复: {len(data) - len(filtered_data)} 行")
            
            # 5. 插入过滤后的数据
            if filtered_data:
                columns_str = ', '.join([f"[{col}]" for col in column_names])
                placeholders = ', '.join(['?' for _ in column_names])
                insert_sql = f"INSERT INTO {full_table_name} ({columns_str}) VALUES ({placeholders})"
                
                for i in range(0, len(filtered_data), self.batch_size):
                    batch = filtered_data[i:i + self.batch_size]
                    self.target_db.execute_batch_update(insert_sql, batch)
                    logger.debug(f"已插入 {min(i + self.batch_size, len(filtered_data))}/{len(filtered_data)} 行")
                
                logger.info(f"成功插入 {len(filtered_data)} 行数据到表 [{schema}].[{table_name}]")
            
            elapsed_time = time.time() - start_time
            logger.info(f"临时表模式插入完成: 插入 {len(filtered_data)}，跳过重复 {len(data) - len(filtered_data)}，总计 {len(data)} 行，总耗时: {elapsed_time:.2f}秒")
            
            return {
                'inserted': len(filtered_data),
                'skipped': len(data) - len(filtered_data),
                'error': 0
            }
            
        except Exception as e:
            logger.error(f"临时表模式插入失败: {e}")
            raise
        finally:
            # 清理临时表
            try:
                drop_temp_sql = f"DROP TABLE {temp_table_name}"
                self.target_db.execute_update(drop_temp_sql)
                logger.debug(f"已删除临时表: {temp_table_name}")
            except Exception as e:
                logger.warning(f"删除临时表失败: {e}")
    
    def _insert_data_safe(self, 
                       table_name: str, 
                       data: List[tuple], 
                       column_names: List[str],
                       schema: str = 'dbo',
                       field_blacklist: List[str] = None) -> Dict[str, int]:
        """安全插入数据到目标表（避免主键冲突，使用分批执行提升性能）
        
        使用分批插入并捕获主键冲突异常，确保不会因为主键重复而中断
        
        Args:
            table_name: 目标表名
            data: 数据列表
            column_names: 列名列表
            schema: 架构名（默认为dbo）
            field_blacklist: 字段黑名单列表
            
        Returns:
            Dict[str, int]: 统计信息 {'inserted': 成功插入数, 'skipped': 跳过数}
        """
        if not data:
            return {'inserted': 0, 'skipped': 0, 'error': 0}
        
        # 应用字段黑名单，返回过滤后的数据和列名
        if field_blacklist:
            data, column_names = self._apply_field_blacklist(data, column_names, field_blacklist)
        
        # 构建插入SQL（使用过滤后的列名）
        columns_str = ', '.join([f"[{col}]" for col in column_names])
        placeholders = ', '.join(['?' for _ in column_names])
        full_table_name = f"[{schema}].[{table_name}]"
        insert_sql = f"INSERT INTO {full_table_name} ({columns_str}) VALUES ({placeholders})"
        
        logger.debug(f"安全插入SQL: {insert_sql}")
        logger.debug(f"总数据行数: {len(data)}, 批处理大小: {self.batch_size}")
        
        # 分批插入并捕获主键冲突异常
        total_inserted = 0
        skipped_count = 0
        error_count = 0
        
        import time
        start_time = time.time()
        
        for batch_num in range(0, len(data), self.batch_size):
            batch = data[batch_num:batch_num + self.batch_size]
            current_batch = batch_num // self.batch_size + 1
            total_batches = (len(data) - 1) // self.batch_size + 1
            
            try:
                # 尝试批量插入
                self.target_db.execute_batch_update(insert_sql, batch)
                batch_inserted = len(batch)
                total_inserted += batch_inserted
                
                logger.debug(f"批次 {current_batch}/{total_batches} 完成，插入 {batch_inserted} 行")
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # 检查是否是主键冲突错误
                if '2627' in error_msg or 'primary key' in error_msg or 'unique' in error_msg or 'duplicate' in error_msg:
                    # 批次中存在主键冲突，回退到逐条插入这个批次
                    logger.debug(f"批次 {current_batch} 检测到主键冲突，回退到逐条插入")
                    
                    batch_inserted = 0
                    batch_skipped = 0
                    
                    for row in batch:
                        try:
                            self.target_db.execute_update(insert_sql, row)
                            batch_inserted += 1
                        except Exception as row_e:
                            row_error_msg = str(row_e).lower()
                            if '2627' in row_error_msg or 'primary key' in row_error_msg or 'unique' in row_error_msg or 'duplicate' in row_error_msg:
                                batch_skipped += 1
                            else:
                                error_count += 1
                                logger.error(f"插入失败: {row_e}")
                                # 非主键冲突的错误，抛出异常
                                if error_count >= 5:
                                    logger.error(f"连续插入错误过多（{error_count}次），中断插入")
                                    raise
                    
                    total_inserted += batch_inserted
                    skipped_count += batch_skipped
                    
                    logger.debug(f"批次 {current_batch}/{total_batches} 逐条完成: 插入 {batch_inserted}, 跳过 {batch_skipped}")
                    
                else:
                    # 非主键冲突的错误，抛出异常
                    error_count += 1
                    logger.error(f"批次 {current_batch} 插入失败: {e}")
                    if error_count >= 5:
                        logger.error(f"连续插入错误过多（{error_count}次），中断插入")
                        raise
            
            # 每处理1000行或每完成一个批次打印一次进度
            if total_inserted + skipped_count >= 1000 or batch_num + self.batch_size >= len(data):
                elapsed_time = time.time() - start_time
                logger.debug(f"已处理 {total_inserted + skipped_count}/{len(data)} 行，成功插入 {total_inserted}，跳过 {skipped_count}，错误 {error_count}，耗时: {elapsed_time:.2f}秒")
        
        elapsed_time = time.time() - start_time
        logger.info(f"安全插入完成: 成功 {total_inserted}，跳过重复 {skipped_count}，错误 {error_count}，总计 {len(data)} 行，总耗时: {elapsed_time:.2f}秒")
        
        return {
            'inserted': total_inserted,
            'skipped': skipped_count,
            'error': error_count
        }
    
    def _sync_related_wfc_process(self, 
                                  source_table_name: str,
                                  source_table_schema: str,
                                  table_data: List[tuple], 
                                  column_names: List[str],
                                  table_config: Dict[str, Any]) -> Dict[str, int]:
        """同步关联表WFC_PROCESS的数据（使用关联子查询，避免手动收集BINDID）
        
        Args:
            source_table_name: 原始表名（包含BINDID的表）
            source_table_schema: 原始表的schema
            table_data: 已同步的表数据
            column_names: 列名列表
            table_config: 表配置（包含源数据库信息）
            
        Returns:
            Dict[str, int]: 统计信息 {
                'total': 需要同步的总行数,
                'inserted': 成功插入数,
                'skipped': 跳过重复数,
                'error': 错误数
            }
        """
        try:
            # 检查BINDID字段是否存在
            if 'BINDID' not in column_names:
                logger.warning("未找到BINDID字段，跳过关联表同步")
                return {'total': 0, 'inserted': 0, 'skipped': 0, 'existing': 0, 'error': 0}
            
            # 获取源表数据库信息
            # 如果表配置中有指定源数据库，则使用配置的；否则使用默认源数据库
            source_table_db = table_config.get('source_database', self.source_db.db_config['database'])
            
            # 获取WFC_PROCESS表所在的目标关联数据库
            related_table = "WFC_PROCESS"
            # WFC_PROCESS使用与原始表相同的schema
            related_schema = source_table_schema
            
            # 切换到源关联数据库（WFC_PROCESS所在的数据库）
            # 注意：这里需要查询WFC_PROCESS，所以我们要切换到WFC_PROCESS所在的数据库
            # WFC_PROCESS通常在awscrmdb中，但我们需要确认
            # 如果related_table_config指定了source_database，则使用它；否则使用默认的source_db
            
            source_related_db = self.related_table_config.get('source_database', self.source_db.db_config['database'])
            logger.info(f"切换到源关联数据库: {source_related_db}")
            self.source_db.use_database(source_related_db)
            
            if not self.source_db.table_exists(related_table, related_schema):
                logger.warning(f"源关联表不存在: [{related_schema}].[{related_table}]")
                return {'total': 0, 'inserted': 0, 'skipped': 0, 'existing': 0, 'error': 0}
            
            # 切换到目标关联数据库
            target_related_db = self.related_table_config.get('target_database', self.target_db.db_config['database'])
            logger.info(f"切换到目标关联数据库: {target_related_db}")
            self.target_db.use_database(target_related_db)
            
            if not self.target_db.table_exists(related_table, related_schema):
                logger.warning(f"目标关联表不存在: [{related_schema}].[{related_table}]")
                return {'total': 0, 'inserted': 0, 'skipped': 0, 'existing': 0, 'error': 0}
            
            # 获取目标表中已存在的ID
            logger.info("获取目标表中已存在的WFC_PROCESS ID...")
            existing_ids = self._get_existing_wfc_process_ids(related_table, related_schema)
            logger.info(f"目标表中已存在 {len(existing_ids)} 个WFC_PROCESS记录")
            
            # 使用关联子查询从源数据库查询需要同步的WFC_PROCESS数据
            logger.info(f"使用关联子查询从源数据库查询WFC_PROCESS数据...")
            # 确保在源关联数据库中查询
            self.source_db.use_database(source_related_db)
            wfc_process_data = self._fetch_wfc_process_data(
                related_table,
                source_table_name,
                source_table_schema,
                source_table_db,  # 传入源表数据库，用于跨库查询
                existing_ids,
                related_schema
            )
            logger.info(f"查询到 {len(wfc_process_data)} 条需要同步的WFC_PROCESS记录")
            
            if not wfc_process_data:
                logger.info("没有需要同步的WFC_PROCESS数据")
                return {
                    'total': 0,
                    'inserted': 0,
                    'skipped': 0,
                    'existing': len(existing_ids),
                    'error': 0
                }
            
            # 获取WFC_PROCESS表的列信息
            # 确保在源关联数据库中查询
            self.source_db.use_database(source_related_db)
            wfc_columns = self.source_db.get_table_columns(related_table, related_schema)
            wfc_column_names = [col['name'] for col in wfc_columns]
            
            # 插入WFC_PROCESS数据（使用安全插入模式避免主键冲突）
            # 确保在目标关联数据库中插入
            self.target_db.use_database(target_related_db)
            insert_stats = self._insert_data_safe(related_table, wfc_process_data, wfc_column_names, related_schema)
            
            return {
                'total': len(wfc_process_data),
                'inserted': insert_stats.get('inserted', 0),
                'skipped': insert_stats.get('skipped', 0),
                'existing': len(existing_ids),
                'error': insert_stats.get('error', 0)
            }
            
        except Exception as e:
            logger.error(f"同步关联表WFC_PROCESS失败: {e}")
            raise
    
    def _get_existing_wfc_process_ids(self, table_name: str, schema: str = 'dbo') -> set:
        """获取目标表中已存在的WFC_PROCESS的ID（使用分批查询避免内存溢出和超时）
        
        Args:
            table_name: 表名
            schema: 架构名（默认为dbo）
            
        Returns:
            set: 已存在的ID集合
        """
        full_table_name = f"[{schema}].[{table_name}]"
        
        # 先检查表的总行数
        try:
            count_query = f"SELECT COUNT(*) FROM {full_table_name}"
            count_results = self.target_db.execute_query(count_query)
            total_count = count_results[0][0] if count_results else 0
            
            logger.info(f"目标表 {table_name} 总行数: {total_count}")
            
            # 如果表为空，直接返回空集合
            if total_count == 0:
                logger.info("目标表为空，无需过滤已存在的ID")
                return set()
            
            # 如果表行数过多（超过10万），使用分批查询
            if total_count > 100000:
                logger.warning(f"目标表行数过多({total_count})，使用分批查询获取ID")
                return self._get_existing_ids_batched(table_name, schema, total_count)
            else:
                # 表行数较少，直接查询所有ID
                query = f"SELECT [ID] FROM {full_table_name}"
                results = self.target_db.execute_query(query)
                existing_ids = set(row[0] for row in results if row[0] is not None)
                logger.info(f"已获取 {len(existing_ids)} 个已存在ID")
                return existing_ids
                
        except Exception as e:
            logger.error(f"获取已存在ID失败: {e}")
            # 出错时返回空集合，不过滤已存在的记录
            logger.warning("将不过滤已存在的ID，可能导致主键冲突")
            return set()
    
    def _get_existing_ids_batched(self, table_name: str, schema: str, total_count: int) -> set:
        """分批获取目标表中已存在的ID（用于大表）
        
        Args:
            table_name: 表名
            schema: 架构名
            total_count: 表的总行数
            
        Returns:
            set: 已存在的ID集合
        """
        full_table_name = f"[{schema}].[{table_name}]"
        batch_size = 10000  # 每批查询1万条
        existing_ids = set()
        
        logger.info(f"开始分批获取已存在ID，总行数: {total_count}, 批次大小: {batch_size}")
        
        try:
            # 使用OFFSET FETCH进行分页查询
            for offset in range(0, total_count, batch_size):
                query = f"""
                    SELECT [ID] 
                    FROM {full_table_name} 
                    ORDER BY [ID]
                    OFFSET {offset} ROWS
                    FETCH NEXT {batch_size} ROWS ONLY
                """
                
                logger.debug(f"查询批次 ID: {offset//batch_size + 1}, OFFSET: {offset}")
                
                results = self.target_db.execute_query(query)
                batch_ids = set(row[0] for row in results if row[0] is not None)
                existing_ids.update(batch_ids)
                
                logger.debug(f"批次 {offset//batch_size + 1}: 获取 {len(batch_ids)} 个ID, 累计 {len(existing_ids)} 个")
                
                # 如果获取到的ID数量少于批次大小，说明已经到末尾
                if len(batch_ids) < batch_size:
                    break
            
            logger.info(f"分批查询完成，共获取 {len(existing_ids)} 个已存在ID")
            return existing_ids
            
        except Exception as e:
            logger.error(f"分批查询失败: {e}")
            # 返回已获取的部分ID
            logger.warning(f"返回部分已获取的ID: {len(existing_ids)} 个")
            return existing_ids
    
    def _fetch_wfc_process_data(self, 
                               table_name: str, 
                               source_table_name: str,
                               source_table_schema: str,
                               source_table_database: str,
                               existing_ids: set,
                               schema: str = 'dbo') -> List[tuple]:
        """从源表获取WFC_PROCESS数据（使用关联子查询，避免手动收集BINDID）
        
        Args:
            table_name: WFC_PROCESS表名
            source_table_name: 原始表名（包含BINDID的表）
            source_table_schema: 原始表的schema
            source_table_database: 原始表的数据库
            existing_ids: 目标表中已存在的ID集合
            schema: WFC_PROCESS表的架构名（默认为dbo）
            
        Returns:
            List[tuple]: WFC_PROCESS数据列表
        """
        # 获取WFC_PROCESS表的列信息
        columns = self.source_db.get_table_columns(table_name, schema)
        column_names = [col['name'] for col in columns]
        columns_str = ', '.join([f"[{col}]" for col in column_names])
        
        # 构建完整表名
        wfc_full_table = f"[{schema}].[{table_name}]"
        
        # 构建源表的完整表名
        # 如果源表数据库与当前数据库不同，则使用三部分命名 [DB].[Schema].[Table]
        # 这样可以支持跨数据库查询
        if source_table_database and source_table_database != self.source_db.db_config['database']:
            source_full_table = f"[{source_table_database}].[{source_table_schema}].[{source_table_name}]"
            logger.debug(f"源表在不同的数据库中，使用三部分命名: {source_full_table}")
        else:
            source_full_table = f"[{source_table_schema}].[{source_table_name}]"
        
        # 找到ID列的索引
        id_index = None
        for i, col_name in enumerate(column_names):
            if col_name.upper() == 'ID':
                id_index = i
                break
        
        if id_index is None:
            logger.warning("未找到ID列，无法过滤已存在的记录")
            id_index = 0
        
        import time
        start_time = time.time()
        
        # 使用关联子查询，避免手动收集BINDID
        # 使用EXISTS而不是IN，性能更好
        query = f"""
            SELECT {columns_str}
            FROM {wfc_full_table} w
            WHERE EXISTS (
                SELECT 1 
                FROM {source_full_table} s
                WHERE s.[BINDID] = w.[ID]
            )
            OPTION (OPTIMIZE FOR UNKNOWN)
        """
        
        logger.info(f"使用关联子查询获取WFC_PROCESS数据...")
        logger.debug(f"查询语句: {query}")
        
        try:
            results = self.source_db.execute_query(query)
            query_time = time.time() - start_time
            logger.info(f"关联子查询完成，获取 {len(results)} 条记录，耗时: {query_time:.2f}秒")
            
            # 转换为tuple列表
            data = [tuple(row) for row in results]
            
            # 过滤掉目标表中已存在的ID
            filtered_data = []
            for row in data:
                if row[id_index] not in existing_ids:
                    filtered_data.append(row)
            
            logger.debug(f"过滤后需要同步的WFC_PROCESS记录数: {len(filtered_data)}")
            
            return filtered_data
            
        except Exception as e:
            logger.error(f"关联子查询失败: {e}")
            logger.error(f"查询语句: {query}")
            raise
    
    def sync_tables(self, table_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量同步多个表
        
        Args:
            table_configs: 表配置列表
            
        Returns:
            Dict[str, Any]: 同步结果汇总
        """
        logger.info("=" * 60)
        logger.info("开始数据同步任务")
        logger.info(f"待同步表数量: {len(table_configs)}")
        logger.info("=" * 60)
        
        # 初始化统计信息
        self.sync_stats = {
            'total_tables': len(table_configs),
            'success_tables': 0,
            'failed_tables': 0,
            'skipped_tables': 0,
            'total_rows': 0,
            'synced_rows': 0,
            'start_time': datetime.now(),
            'end_time': None,
            'details': []
        }
        
        # 测试数据库连接
        logger.info("测试数据库连接...")
        try:
            self.source_db.connect()
            logger.info("源数据库连接测试成功")
            self.target_db.connect()
            logger.info("目标数据库连接测试成功")
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            raise Exception("数据库连接失败，无法执行同步任务")
        
        # 逐个同步表
        for i, table_config in enumerate(table_configs, 1):
            logger.info(f"\n[{i}/{len(table_configs)}] 处理表: {table_config['table_name']}")
            
            result = self.sync_table(table_config)
            self.sync_stats['details'].append(result)
            
            # 更新统计
            if result['status'] == 'success':
                self.sync_stats['success_tables'] += 1
            elif result['status'] == 'failed':
                self.sync_stats['failed_tables'] += 1
            elif result['status'] == 'skipped':
                self.sync_stats['skipped_tables'] += 1
        
        # 完成统计
        self.sync_stats['end_time'] = datetime.now()
        duration = (self.sync_stats['end_time'] - self.sync_stats['start_time']).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info("数据同步任务完成")
        logger.info("=" * 60)
        logger.info(f"总表数: {self.sync_stats['total_tables']}")
        logger.info(f"成功: {self.sync_stats['success_tables']}")
        logger.info(f"失败: {self.sync_stats['failed_tables']}")
        logger.info(f"跳过: {self.sync_stats['skipped_tables']}")
        logger.info(f"同步总行数: {self.sync_stats['synced_rows']}")
        logger.info(f"耗时: {duration:.2f} 秒")
        logger.info("=" * 60)
        
        # 如果有失败的表，抛出异常
        if self.sync_stats['failed_tables'] > 0:
            logger.warning("部分表同步失败，请检查日志")
            failed_tables = [
                detail for detail in self.sync_stats['details'] 
                if detail['status'] == 'failed'
            ]
            for failed in failed_tables:
                logger.error(f"失败表: {failed['table_name']}, 错误: {failed['error']}")
        
        return self.sync_stats
    
    def print_sync_summary(self, stats: Dict[str, Any]) -> None:
        """打印同步摘要
        
        Args:
            stats: 同步统计信息
        """
        print("\n" + "=" * 60)
        print("数据同步摘要")
        print("=" * 60)
        print(f"开始时间: {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"结束时间: {stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        duration = (stats['end_time'] - stats['start_time']).total_seconds()
        print(f"总耗时: {duration:.2f} 秒")
        
        print(f"\n表统计:")
        print(f"  总表数: {stats['total_tables']}")
        print(f"  成功: {stats['success_tables']}")
        print(f"  失败: {stats['failed_tables']}")
        print(f"  跳过: {stats['skipped_tables']}")
        print(f"  同步行数: {stats['synced_rows']}")
        
        if stats['synced_rows'] > 0 and duration > 0:
            speed = stats['synced_rows'] / duration
            print(f"  同步速度: {speed:.2f} 行/秒")
        
        print("\n详细信息:")
        for detail in stats['details']:
            status_symbol = "✓" if detail['status'] == 'success' else ("✗" if detail['status'] == 'failed' else "○")
            print(f"  {status_symbol} {detail['table_name']}: 源数据 {detail['source_rows']} 行")
            
            # 显示主表同步详细信息
            if detail.get('inserted_rows', 0) > 0 or detail.get('skipped_rows', 0) > 0:
                print(f"      主表同步: 插入 {detail['inserted_rows']} 行")
                if detail.get('skipped_rows', 0) > 0:
                    print(f"               跳过重复 {detail['skipped_rows']} 行")
            
            # 显示关联表同步详细信息
            if detail.get('related_synced_rows', 0) > 0:
                print(f"      关联表 WFC_PROCESS:")
                print(f"        需同步: {detail['related_synced_rows']} 行")
                print(f"        已存在: {detail['related_existing_count']} 行")
                print(f"        成功插入: {detail['related_inserted_count']} 行")
                if detail.get('related_skipped_count', 0) > 0:
                    print(f"        跳过重复: {detail['related_skipped_count']} 行")
            
            if detail['status'] == 'failed':
                print(f"      错误: {detail['error']}")
            elif detail['status'] == 'skipped':
                print(f"      原因: {detail['error']}")
        
        print("=" * 60)