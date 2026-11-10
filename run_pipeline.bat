

@echo off
REM NHL Betting Model Pipeline Runner
REM Logs to logs/pipeline_YYYYMMDD.log

setlocal

REM Change to project directory
cd /d "C:\Users\Nathan\Downloads\[My Projects]\nhl-betting-model"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Generate log filename with date
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set LOG_FILE=logs\pipeline_%datetime:~0,8%.log

REM Activate virtual environment and run pipeline
echo [%date% %time%] Starting pipeline... >> %LOG_FILE%
call .venv\Scripts\activate.bat
python -m pipelines.run_all >> %LOG_FILE% 2>&1

REM Check exit code
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] Pipeline completed successfully >> %LOG_FILE%
) else (
    echo [%date% %time%] Pipeline failed with exit code %ERRORLEVEL% >> %LOG_FILE%
)

echo. >> %LOG_FILE%
endlocal