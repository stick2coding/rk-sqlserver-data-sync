"""
日志模块
提供统一的日志记录功能
"""

import logging
import logging.config
import json
import os
from pathlib import Path


class Logger:
    """日志管理类"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not Logger._initialized:
            self._setup_logging()
            Logger._initialized = True
    
    def _setup_logging(self):
        """设置日志配置"""
        # 确保logs目录存在
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # 尝试加载日志配置文件
        config_file = Path("config/logging_config.json")
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logging.config.dictConfig(config)
            except Exception as e:
                print(f"加载日志配置文件失败: {e}")
                self._setup_default_logging()
        else:
            self._setup_default_logging()
    
    def _setup_default_logging(self):
        """设置默认日志配置"""
        # 确保logs目录存在
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # 创建日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # 文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            'logs/data_sync.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
    
    @staticmethod
    def get_logger(name: str = None) -> logging.Logger:
        """获取日志记录器
        
        Args:
            name: 日志记录器名称，通常使用__name__
            
        Returns:
            logging.Logger: 日志记录器实例
        """
        if name:
            return logging.getLogger(name)
        return logging.getLogger(__name__)


# 便捷函数
def get_logger(name: str = None) -> logging.Logger:
    """获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称，通常使用__name__
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return Logger().get_logger(name)
