"""
数据库连接测试脚本
用于测试db_config.json中的数据库配置是否可用
"""

import sys
from src.config_loader import ConfigLoader
from src.db_connector import DatabaseConnector
from src.logger import get_logger

logger = get_logger(__name__)


def test_database_connection(db_name: str, db_config: dict) -> bool:
    """测试单个数据库连接
    
    Args:
        db_name: 数据库名称（用于显示）
        db_config: 数据库配置字典
        
    Returns:
        bool: 连接是否成功
    """
    print(f"\n{'=' * 60}")
    print(f"测试数据库: {db_name}")
    print(f"{'=' * 60}")
    print(f"服务器: {db_config['server']}")
    print(f"数据库: {db_config['database']}")
    print(f"用户名: {db_config['username']}")
    print(f"驱动: {db_config['driver']}")
    print(f"{'-' * 60}")
    
    try:
        # 创建数据库连接器
        db_connector = DatabaseConnector(
            db_config,
            retry_times=1,
            retry_interval=1
        )
        
        # 尝试连接
        print("正在连接数据库...")
        connection = db_connector.connect()
        
        # 执行简单测试查询
        print("执行测试查询...")
        query = "SELECT @@VERSION"
        results = db_connector.execute_query(query)
        
        if results and len(results) > 0:
            print("✓ 数据库连接成功！")
            print(f"\n数据库版本信息:")
            version_info = results[0][0]
            # 只显示前几行版本信息
            version_lines = version_info.split('\n')[:3]
            for line in version_lines:
                print(f"  {line}")
            
            # 获取数据库大小信息（可选）
            try:
                size_query = """
                    SELECT 
                        SUM(CAST(size AS BIGINT)) * 8 / 1024 / 1024 AS SizeMB
                    FROM sys.master_files
                    WHERE database_id = DB_ID()
                """
                size_results = db_connector.execute_query(size_query)
                if size_results and size_results[0][0]:
                    size_mb = size_results[0][0]
                    print(f"\n数据库大小: {size_mb:.2f} MB")
            except:
                pass  # 如果查询失败，忽略
            
            # 关闭连接
            db_connector.close()
            
            print(f"\n{'=' * 60}")
            print(f"✓ {db_name} 测试通过")
            print(f"{'=' * 60}\n")
            return True
        else:
            print("✗ 无法获取数据库版本信息")
            db_connector.close()
            return False
            
    except Exception as e:
        print(f"✗ 数据库连接失败！")
        print(f"错误信息: {e}")
        print(f"{'=' * 60}\n")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("SQL Server 数据库连接测试工具")
    print("=" * 60)
    
    try:
        # 1. 加载配置
        print("\n加载配置文件...")
        config_loader = ConfigLoader()
        
        # 加载数据库配置
        db_config = config_loader.load_db_config()
        source_db_config = config_loader.get_source_database_config()
        target_db_config = config_loader.get_target_database_config()
        
        print("✓ 配置文件加载成功\n")
        
        # 2. 测试源数据库
        source_success = test_database_connection("源数据库", source_db_config)
        
        # 3. 测试目标数据库
        target_success = test_database_connection("目标数据库", target_db_config)
        
        # 4. 输出测试结果摘要
        print("\n" + "=" * 60)
        print("测试结果摘要")
        print("=" * 60)
        print(f"源数据库: {'✓ 连接成功' if source_success else '✗ 连接失败'}")
        print(f"目标数据库: {'✓ 连接成功' if target_success else '✗ 连接失败'}")
        print("=" * 60)
        
        # 5. 返回状态码
        if source_success and target_success:
            print("\n✓ 所有数据库连接测试通过！")
            print("配置文件可以使用。\n")
            return 0
        else:
            print("\n✗ 部分数据库连接测试失败！")
            print("请检查配置文件和网络连接。\n")
            return 1
            
    except FileNotFoundError as e:
        print(f"\n✗ 配置文件不存在: {e}")
        print("请确保 config/db_config.json 文件存在。\n")
        return 2
        
    except ValueError as e:
        print(f"\n✗ 配置验证失败: {e}")
        print("请检查配置文件格式和内容。\n")
        return 3
        
    except Exception as e:
        print(f"\n✗ 测试过程中发生错误: {e}\n")
        logger.error("测试失败", exc_info=True)
        return 4


if __name__ == "__main__":
    exit_code = main()
    input("\n按回车键退出...")
    sys.exit(exit_code)
