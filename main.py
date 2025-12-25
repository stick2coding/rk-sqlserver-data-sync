"""
SQL Server数据同步系统 - 主程序入口
"""

import sys
from src.config_loader import ConfigLoader
from src.config_selector import ConfigSelector
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
        # 1. 选择配置文件
        tables_config_path = select_tables_config()
        
        if tables_config_path is None:
            print("未找到有效的表配置文件")
            print("请在 config/table_configs 目录下创建配置文件")
            print("或者使用旧的 config/tables_config.json 文件")
            sys.exit(2)
        
        # 2. 加载配置
        logger.info(f"开始加载配置文件: {tables_config_path}")
        config_loader = ConfigLoader(tables_config_path=tables_config_path)
        
        # 加载数据库配置
        db_config = config_loader.load_db_config()
        source_db_config = config_loader.get_source_database_config()
        target_db_config = config_loader.get_target_database_config()
        sync_settings = config_loader.get_sync_settings()
        related_table_config = config_loader.get_related_table_config()
        
        # 加载表配置
        tables_to_sync = config_loader.get_tables_to_sync()
        
        if not tables_to_sync:
            logger.warning("没有配置需要同步的表")
            print("\n当前配置文件中没有启用的表")
            print("请检查配置文件中的 'enabled' 字段")
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




def select_tables_config():
    """选择表配置文件
    
    Returns:
        Path: 选中的配置文件路径，如果未找到则返回None
    """
    from pathlib import Path
    
    # 1. 尝试使用配置选择器（新版）
    selector = ConfigSelector()
    configs = selector.discover_configs()
    
    if configs:
        # 有配置文件，显示选择菜单
        selected = selector.display_and_select(configs)
        
        if selected:
            print()  # 空行分隔
            return selected['path']
        else:
            return None
    
    # 2. 向后兼容：尝试使用旧的配置文件
    old_config_path = Path("config/tables_config.json")
    
    if old_config_path.exists():
        print("未发现 config/table_configs 目录，使用旧版配置文件")
        print(f"配置文件: {old_config_path}")
        print()
        
        # 验证旧版配置文件格式
        try:
            import json
            with open(old_config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 检查是否是旧版格式（没有name字段）
            if 'name' not in config_data and 'tables' in config_data:
                print("检测到旧版配置文件格式，继续使用...")
                return old_config_path
            elif 'name' in config_data:
                # 新版格式但放在了错误的位置
                print("提示: 检测到新版配置文件格式")
                print("建议将文件移动到 config/table_configs/ 目录")
                return old_config_path
            else:
                print("错误: 配置文件格式不正确")
                return None
                
        except json.JSONDecodeError as e:
            print(f"错误: 配置文件JSON格式错误 - {e}")
            return None
        except Exception as e:
            print(f"错误: 读取配置文件失败 - {e}")
            return None
    
    # 3. 没有找到任何配置文件
    print("错误: 未找到任何表配置文件")
    print()
    print("请选择以下方式之一:")
    print("  1. 在 config/table_configs/ 目录下创建新配置文件")
    print("  2. 创建 config/tables_config.json 文件")
    print()
    return None


if __name__ == "__main__":
    main()
