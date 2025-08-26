@echo off
REM Genesis Trading Bot - Enkel start/stopp
REM Användning: start-bot.bat [start|stop|restart|status]

if "%1"=="" (
    echo Användning: start-bot.bat [start^|stop^|restart^|status]
    echo.
    echo Exempel:
    echo   start-bot.bat start    - Startar trading bot
    echo   start-bot.bat stop     - Stoppar trading bot
    echo   start-bot.bat restart  - Startar om trading bot
    echo   start-bot.bat status   - Visar status
    echo.
    pause
    exit /b
)

powershell -ExecutionPolicy Bypass -File "scripts\start.ps1" -Action %1

pause
