@echo off
chcp 65001 >nul
title AVTOMAKTAB - Amaliy mashg'ulotlar platformasi
cd /d "%~dp0"

rem Bitta server, bitta port (8080). Port band bolsa ikkinchi server boshlanmaydi -
rem brauzer baribir ochiladi va mavjud serverga ulanadi.

set "PYCMD="
where py >nul 2>nul && set "PYCMD=py"
if not defined PYCMD (
    where python >nul 2>nul && set "PYCMD=python"
)

if not defined PYCMD (
    echo.
    echo [X] Python topilmadi!
    echo     Iltimos, https://www.python.org/downloads/ sahifasidan
    echo     Python 3.12+ o'rnatib, qayta urinib ko'ring.
    echo     O'rnatishda "Add Python to PATH" ni belgilashni unutmang.
    echo.
    pause
    exit /b 1
)

echo [INFO] Server ishga tushirilmoqda...
start /min "" %PYCMD% server.py
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8080/
echo.
echo   Brauzer ochiladi: http://127.0.0.1:8080/
echo   Agar ochilmagan bolsa, manzil qatoriga shu manzilni yozing.
echo   BU OYNA YOPILMASIN - server shu yerda ishlaydi.
echo   (Agar server allaqachon ishlayotgan bolsa, brauzer baribir ochiladi.)
echo.
pause