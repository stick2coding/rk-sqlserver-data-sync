"""
SQL Server数据同步系统 - 主程序入口
"""

import sys
from src.config_loader import ConfigLoader
from src.db_connector import DatabaseConnector
from src.data_sync import DataSync
from src.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("SQL Server 数据同步系统")
    print("=" * 60 + "\n")
    
    try:
        # 1. 加载配置
        logger.info("开始加载配置文件...")
        config_loader = ConfigLoader()
        
        # 加载数据库配置
        db_config = config_loader.load_db_config()
        source_db_config = config_loader.get_source_database_config()
        target_db_config = config_loader.get_target_database_config()
        sync_settings = config_loader.get_sync_settings()
        related_table_config = config_loader.get_related_table_config()
        
        # 加载表配置
        tables_to_sync = config_loader.get_tables_to_sync()
        
        if not tables_to_sync:
            logger.warning("没有配置需要同步的表，请检查config/tables_config.json")
            return
        
        logger.info(f"配置加载完成，待同步表数量: {len(tables_to_sync)}")
        
        # 2. 创建数据库连接器
        logger.info("创建数据库连接器...")
        source_db = DatabaseConnector(
            source_db_config,
            retry_times=sync_settings['retry_times'],
            retry_interval=sync_settings['retry_interval']
        )
        
        target_db = DatabaseConnector(
            target_db_config,
            retry_times=sync_settings['retry_times'],
            retry_interval=sync_settings['retry_interval']
        )
        
        # 3. 创建数据同步器
        logger.info("创建数据同步器...")
        data_sync = DataSync(
            source_db=source_db,
            target_db=target_db,
            batch_size=sync_settings['batch_size'],
            related_table_config=related_table_config
        )
        
        # 4. 执行数据同步
        logger.info("开始执行数据同步任务...")
        sync_stats = data_sync.sync_tables(tables_to_sync)
        
        # 5. 打印同步摘要
        data_sync.print_sync_summary(sync_stats)
        
        # 6. 关闭数据库连接
        logger.info("关闭数据库连接...")
        source_db.close()
        target_db.close()
        
        # 7. 根据结果返回状态码
        if sync_stats['failed_tables'] > 0:
            logger.error("数据同步任务完成，但有部分表同步失败")
            sys.exit(1)
        else:
            logger.info("数据同步任务全部完成")
            sys.exit(0)
            
    except FileNotFoundError as e:
        logger.error(f"配置文件不存在: {e}")
        logger.error("请确保配置文件存在于config目录中")
        sys.exit(2)
        
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        logger.error("请检查配置文件格式和内容")
        sys.exit(3)
        
    except Exception as e:
        logger.error(f"数据同步过程中发生错误: {e}", exc_info=True)
        sys.exit(4)


if __name__ == "__main__":
    main()
