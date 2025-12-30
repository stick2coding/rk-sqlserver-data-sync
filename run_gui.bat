@echo off
chcp 65001 >nul
echo ========================================
echo SQL Server 数据同步系统 - GUI 模式
echo ========================================
echo.

python src/gui_app.py

if %errorlevel% neq 0 (
    echo.
    echo 程序执行出错，错误代码: %errorlevel%
    pause
)
