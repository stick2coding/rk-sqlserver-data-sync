"""
配置加载模块
负责读取和验证JSON配置文件
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.logger import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """配置加载器类"""
    
    def __init__(self, db_config_path: str = "config/db_config.json",
                 tables_config_path: str = "config/tables_config.json"):
        """初始化配置加载器
        
        Args:
            db_config_path: 数据库配置文件路径
            tables_config_path: 表配置文件路径
        """
        self.db_config_path = Path(db_config_path)
        self.tables_config_path = Path(tables_config_path)
        self._db_config: Optional[Dict[str, Any]] = None
        self._tables_config: Optional[Dict[str, Any]] = None
    
    def load_db_config(self) -> Dict[str, Any]:
        """加载数据库配置
        
        Returns:
            Dict[str, Any]: 数据库配置字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式错误
            ValueError: 配置内容验证失败
        """
        if self._db_config is not None:
            return self._db_config
        
        if not self.db_config_path.exists():
            raise FileNotFoundError(f"数据库配置文件不存在: {self.db_config_path}")
        
        try:
            with open(self.db_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 验证配置
            self._validate_db_config(config)
            
            self._db_config = config
            logger.info(f"成功加载数据库配置: {self.db_config_path}")
            return self._db_config
            
        except json.JSONDecodeError as e:
            logger.error(f"数据库配置文件JSON格式错误: {e}")
            raise
        except ValueError as e:
            logger.error(f"数据库配置验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"加载数据库配置时发生未知错误: {e}")
            raise
    
    def load_tables_config(self) -> Dict[str, Any]:
        """加载表同步配置
        
        Returns:
            Dict[str, Any]: 表配置字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式错误
            ValueError: 配置内容验证失败
        """
        if self._tables_config is not None:
            return self._tables_config
        
        if not self.tables_config_path.exists():
            raise FileNotFoundError(f"表配置文件不存在: {self.tables_config_path}")
        
        try:
            with open(self.tables_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 验证配置
            self._validate_tables_config(config)
            
            self._tables_config = config
            logger.info(f"成功加载表配置: {self.tables_config_path}")
            return self._tables_config
            
        except json.JSONDecodeError as e:
            logger.error(f"表配置文件JSON格式错误: {e}")
            raise
        except ValueError as e:
            logger.error(f"表配置验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"加载表配置时发生未知错误: {e}")
            raise
    
    def _validate_db_config(self, config: Dict[str, Any]) -> None:
        """验证数据库配置
        
        Args:
            config: 数据库配置字典
            
        Raises:
            ValueError: 配置验证失败
        """
        required_keys = ['source_database', 'target_database', 'sync_settings']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"数据库配置缺少必需字段: {key}")
        
        # 验证source_database
        self._validate_database_config(config['source_database'], 'source_database')
        
        # 验证target_database
        self._validate_database_config(config['target_database'], 'target_database')
        
        # 验证sync_settings
        sync_settings = config['sync_settings']
        if 'batch_size' not in sync_settings:
            sync_settings['batch_size'] = 1000
        if 'retry_times' not in sync_settings:
            sync_settings['retry_times'] = 3
        if 'retry_interval' not in sync_settings:
            sync_settings['retry_interval'] = 5
        
        # 验证类型
        if not isinstance(sync_settings['batch_size'], int) or sync_settings['batch_size'] <= 0:
            raise ValueError("batch_size必须是正整数")
        if not isinstance(sync_settings['retry_times'], int) or sync_settings['retry_times'] < 0:
            raise ValueError("retry_times必须是非负整数")
        if not isinstance(sync_settings['retry_interval'], int) or sync_settings['retry_interval'] < 0:
            raise ValueError("retry_interval必须是非负整数")
    
    def _validate_database_config(self, db_config: Dict[str, Any], config_name: str) -> None:
        """验证单个数据库配置
        
        Args:
            db_config: 数据库配置字典
            config_name: 配置名称（用于错误提示）
            
        Raises:
            ValueError: 配置验证失败
        """
        required_keys = ['server', 'database', 'username', 'password', 'driver']
        for key in required_keys:
            if key not in db_config:
                raise ValueError(f"{config_name}缺少必需字段: {key}")
        
        # 验证非空
        for key in required_keys:
            if not db_config[key] or not isinstance(db_config[key], str):
                raise ValueError(f"{config_name}.{key}必须是非空字符串")
    
    def _validate_tables_config(self, config: Dict[str, Any]) -> None:
        """验证表配置
        
        Args:
            config: 表配置字典
            
        Raises:
            ValueError: 配置验证失败
        """
        if 'tables' not in config:
            raise ValueError("表配置缺少tables字段")
        
        if not isinstance(config['tables'], list):
            raise ValueError("tables必须是列表")
        
        if len(config['tables']) == 0:
            logger.warning("表配置中没有任何表")
            return
        
        # 验证每个表配置
        for i, table_config in enumerate(config['tables']):
            self._validate_table_config(table_config, i)
    
    def _validate_table_config(self, table_config: Dict[str, Any], index: int) -> None:
        """验证单个表配置
        
        Args:
            table_config: 表配置字典
            index: 表索引（用于错误提示）
            
        Raises:
            ValueError: 配置验证失败
        """
        required_keys = ['table_name', 'sync_mode', 'sync_strategy', 'primary_key', 'enabled']
        for key in required_keys:
            if key not in table_config:
                raise ValueError(f"表配置[{index}]缺少必需字段: {key}")
        
        # 验证table_name
        if not table_config['table_name'] or not isinstance(table_config['table_name'], str):
            raise ValueError(f"表配置[{index}].table_name必须是非空字符串")
        
        # 设置默认schema为dbo
        if 'schema' not in table_config:
            table_config['schema'] = 'dbo'
        elif not table_config['schema'] or not isinstance(table_config['schema'], str):
            raise ValueError(f"表配置[{index}].schema必须是非空字符串")
        
        # 设置默认sync_related_table为false
        if 'sync_related_table' not in table_config:
            table_config['sync_related_table'] = False
        elif not isinstance(table_config['sync_related_table'], bool):
            raise ValueError(f"表配置[{index}].sync_related_table必须是布尔值")
        
        # 验证sync_mode
        valid_sync_modes = ['full', 'incremental']
        if table_config['sync_mode'] not in valid_sync_modes:
            raise ValueError(f"表配置[{index}].sync_mode必须是: {valid_sync_modes}")
        
        # 验证sync_strategy
        valid_sync_strategies = ['overwrite', 'append']
        if table_config['sync_strategy'] not in valid_sync_strategies:
            raise ValueError(f"表配置[{index}].sync_strategy必须是: {valid_sync_strategies}")
        
        # 验证primary_key
        if not table_config['primary_key'] or not isinstance(table_config['primary_key'], str):
            raise ValueError(f"表配置[{index}].primary_key必须是非空字符串")
        
        # 验证enabled
        if not isinstance(table_config['enabled'], bool):
            raise ValueError(f"表配置[{index}].enabled必须是布尔值")
        
        # 如果是增量同步，验证last_sync_field
        if table_config['sync_mode'] == 'incremental':
            if 'last_sync_field' not in table_config:
                raise ValueError(f"增量同步表配置[{index}]必须包含last_sync_field字段")
            if not table_config['last_sync_field'] or not isinstance(table_config['last_sync_field'], str):
                raise ValueError(f"表配置[{index}].last_sync_field必须是非空字符串")
        
        # 验证source_database（如果配置了的话）
        if 'source_database' in table_config:
            if not table_config['source_database'] or not isinstance(table_config['source_database'], str):
                raise ValueError(f"表配置[{index}].source_database必须是非空字符串")
        
        # 验证target_database（如果配置了的话）
        if 'target_database' in table_config:
            if not table_config['target_database'] or not isinstance(table_config['target_database'], str):
                raise ValueError(f"表配置[{index}].target_database必须是非空字符串")
    
    def get_source_database_config(self) -> Dict[str, str]:
        """获取源数据库配置
        
        Returns:
            Dict[str, str]: 源数据库配置
        """
        config = self.load_db_config()
        return config['source_database']
    
    def get_target_database_config(self) -> Dict[str, str]:
        """获取目标数据库配置
        
        Returns:
            Dict[str, str]: 目标数据库配置
        """
        config = self.load_db_config()
        return config['target_database']
    
    def get_sync_settings(self) -> Dict[str, Any]:
        """获取同步设置
        
        Returns:
            Dict[str, Any]: 同步设置
        """
        config = self.load_db_config()
        return config['sync_settings']
    
    def get_tables_to_sync(self) -> List[Dict[str, Any]]:
        """获取需要同步的表列表
        
        Returns:
            List[Dict[str, Any]]: 需要同步的表配置列表（仅包含enabled=true的表）
        """
        config = self.load_tables_config()
        return [table for table in config['tables'] if table['enabled']]
    
    def get_all_tables(self) -> List[Dict[str, Any]]:
        """获取所有表配置列表
        
        Returns:
            List[Dict[str, Any]]: 所有表配置列表
        """
        config = self.load_tables_config()
        return config['tables']
    
    def get_related_table_config(self) -> Dict[str, str]:
        """获取关联表配置
        
        Returns:
            Dict[str, str]: 关联表数据库配置
        """
        config = self.load_db_config()
        if 'related_table' not in config:
            return {}
        return config['related_table']
