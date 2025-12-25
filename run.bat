@echo off
REM SQL Server 数据同步系统启动脚本

echo ========================================
echo SQL Server 数据同步系统
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

REM 运行主程序
python main.py

REM 暂停以查看输出
pause
