@echo off
REM 数据库连接测试脚本

echo ========================================
echo SQL Server 数据库连接测试工具
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo 错误: 虚拟环境不存在！
    echo 请先运行: python -m venv venv
    pause
    exit /b 1
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 运行测试脚本
python test_connection.py
