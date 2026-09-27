@echo off
chcp 65001 >nul
title AVTOMAKTAB - Testlar
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -m tests.test_api) else (python -m tests.test_api)
pause