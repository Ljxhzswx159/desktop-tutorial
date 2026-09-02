@echo off
chcp 65001 >nul
REM 注塑智能工艺系统一键启动脚本
cd /d "%~dp0backend"
echo ============================================
echo  注塑成型智能工艺参数优化与质量预测系统
echo  启动后访问: http://localhost:8000
echo  API 文档:   http://localhost:8000/docs
echo ============================================
py -3.13 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
