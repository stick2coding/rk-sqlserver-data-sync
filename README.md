# SQL Server 数据同步系统

一个基于Python的SQL Server数据库数据同步工具，支持全量同步和增量同步模式。

## 功能特性

- ✅ 支持全量同步和增量同步两种模式
- ✅ 支持覆盖和追加两种同步策略
- ✅ 批量处理大量数据，提高同步效率
- ✅ 完善的日志记录和错误处理
- ✅ 配置文件驱动，灵活配置同步任务
- ✅ 数据库连接失败自动重试机制
- ✅ 同步进度跟踪和统计信息输出

## 系统要求

- Python 3.8 或更高版本
- SQL Server 数据库
- ODBC Driver for SQL Server

## 项目结构

```
data_sync/
├── venv/                      # 虚拟环境目录
├── config/                    # 配置文件目录
│   ├── db_config.json        # 数据库连接配置
│   ├── tables_config.json    # 表同步配置
│   └── logging_config.json   # 日志配置
├── src/                      # 源代码目录
│   ├── __init__.py
│   ├── db_connector.py      # 数据库连接模块
│   ├── data_sync.py         # 数据同步核心模块
│   ├── config_loader.py     # 配置加载模块
│   └── logger.py            # 日志模块
├── logs/                     # 日志文件目录
├── requirements.txt          # Python依赖包
├── main.py                   # 主程序入口
└── README.md                 # 项目说明文档
```

## 安装步骤

### 1. 克隆或下载项目

```bash
cd data_sync
```

### 2. 创建虚拟环境

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 测试数据库连接（可选）

在配置数据库连接之前，建议先测试数据库连接是否正常：

```bash
# 方式1：使用测试脚本
test_connection.bat

# 方式2：手动运行
venv\Scripts\activate
python test_connection.py
```

测试脚本会：
- 检查配置文件格式是否正确
- 尝试连接源数据库
- 尝试连接目标数据库
- 显示数据库版本和大小信息
- 输出测试结果

如果测试通过，说明配置文件可以正常使用。

### 5. 配置数据库连接

编辑 `config/db_config.json` 文件，填入您的数据库连接信息：

```json
{
  "source_database": {
    "server": "your_source_server",
    "database": "your_source_database",
    "username": "your_username",
    "password": "your_password",
    "driver": "ODBC Driver 17 for SQL Server"
  },
  "target_database": {
    "server": "your_target_server",
    "database": "your_target_database",
    "username": "your_username",
    "password": "your_password",
    "driver": "ODBC Driver 17 for SQL Server"
  },
  "sync_settings": {
    "batch_size": 1000,
    "retry_times": 3,
    "retry_interval": 5
  }
}
```

配置说明：
- `source_database`: 源数据库配置
- `target_database`: 目标数据库配置
- `sync_settings.batch_size`: 批处理大小，建议根据数据量调整
- `sync_settings.retry_times`: 连接失败重试次数
- `sync_settings.retry_interval`: 重试间隔（秒）

### 6. 配置要同步的表

编辑 `config/tables_config.json` 文件，配置需要同步的表：

```json
{
  "tables": [
    {
      "table_name": "users",
      "sync_mode": "full",
      "sync_strategy": "overwrite",
      "primary_key": "id",
      "enabled": true
    },
    {
      "table_name": "orders",
      "sync_mode": "incremental",
      "sync_strategy": "append",
      "primary_key": "id",
      "last_sync_field": "update_time",
      "enabled": true
    }
  ]
}
```

配置说明：
- `table_name`: 表名
- `sync_mode`: 同步模式
  - `full`: 全量同步，同步所有数据
  - `incremental`: 增量同步，只同步新增/更新的数据
- `sync_strategy`: 同步策略
  - `overwrite`: 覆盖模式，同步前先清空目标表
  - `append`: 追加模式，直接追加数据到目标表
- `primary_key`: 主键字段名
- `last_sync_field`: 增量同步时的时间字段（仅增量同步需要）
- `enabled`: 是否启用同步

## 使用方法

### 测试数据库连接

在执行同步之前，建议先测试数据库连接：

```bash
# Windows用户
test_connection.bat

# 或者手动运行
venv\Scripts\activate
python test_connection.py
```

测试工具会显示：
- ✓ 连接成功：显示数据库版本和大小信息
- ✗ 连接失败：显示具体的错误信息

### 运行数据同步

确保虚拟环境已激活，然后运行：

```bash
python main.py
```

### 查看日志

日志文件位于 `logs/data_sync.log`，包含详细的执行记录和错误信息。

### 退出码说明

- `0`: 同步成功
- `1`: 部分表同步失败
- `2`: 配置文件不存在
- `3`: 配置验证失败
- `4`: 执行过程中发生错误

## 使用示例

### 示例1：全量同步用户表

```json
{
  "table_name": "users",
  "sync_mode": "full",
  "sync_strategy": "overwrite",
  "primary_key": "id",
  "enabled": true
}
```

这个配置会：
1. 清空目标数据库中的 users 表
2. 从源数据库读取所有用户数据
3. 批量插入到目标数据库

### 示例2：增量同步订单表

```json
{
  "table_name": "orders",
  "sync_mode": "incremental",
  "sync_strategy": "append",
  "primary_key": "id",
  "last_sync_field": "update_time",
  "enabled": true
}
```

这个配置会：
1. 查询目标表中最大的 `update_time` 值
2. 从源数据库读取 `update_time` 大于该值的订单
3. 追加到目标数据库

## 注意事项

1. **表结构一致性**: 目标表的结构必须与源表一致，否则会导致同步失败。如果目标表不存在，系统会跳过该表的同步。

2. **主键约束**: 使用 `append` 策略时，请确保目标表中没有重复的主键值。

3. **数据量大的表**: 对于数据量很大的表，可以适当增大 `batch_size` 参数以提高性能，但不要设置过大，以免内存不足。

4. **增量同步时间字段**: 增量同步使用的时间字段必须是递增的（如自增ID、创建时间、更新时间等）。

5. **数据库驱动**: 确保已安装正确版本的 ODBC Driver for SQL Server。常用的版本有：
   - ODBC Driver 17 for SQL Server
   - ODBC Driver 18 for SQL Server

6. **网络连接**: 确保能够访问源数据库和目标数据库，网络稳定。

## 常见问题

### Q: 提示"未找到ODBC驱动"怎么办？

A: 需要安装 ODBC Driver for SQL Server。可以从微软官网下载安装：
- https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

### Q: 如何只同步部分表？

A: 在 `config/tables_config.json` 中，将不需要同步的表的 `enabled` 字段设置为 `false`。

### Q: 同步速度很慢怎么办？

A: 可以尝试：
1. 增大 `batch_size` 参数
2. 检查网络连接速度
3. 检查数据库服务器性能

### Q: 目标表结构不匹配怎么办？

A: 目前系统不会自动创建表结构，需要手动在目标数据库中创建与源表结构一致的表。

## 性能优化建议

1. **批量处理**: 根据数据量和内存情况，调整 `batch_size` 参数（推荐值：1000-5000）

2. **网络优化**: 
   - 使用高速网络连接
   - 尽量在同一局域网内同步

3. **数据库优化**:
   - 同步期间避免其他大事务
   - 确保有足够的数据库连接数
   - 考虑在非高峰期执行同步

4. **增量同步**: 对于频繁更新的表，优先使用增量同步模式

## 扩展功能

系统支持以下扩展（可选实现）：
- 同步前数据备份
- 数据冲突检测和解决
- 自定义字段映射
- 邮件/消息通知
- 定时任务调度

## 技术支持

如有问题或建议，请查看日志文件 `logs/data_sync.log` 获取详细信息。

## 许可证

本项目仅供学习和使用。

## 更新日志

### v1.0.0 (2025-12-25)
- 初始版本发布
- 支持全量和增量同步
- 支持覆盖和追加策略
- 完善的日志和错误处理
