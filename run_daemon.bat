@echo off
:: ==============================================================================
:: AVVIOPC PRINT DAEMON SERVICE LAUNCHER
:: Description: Keeps the background automation script active and handles crashes.
:: ==============================================================================
TITLE AvvioPC Print Daemon

:: Clear screen for clean startup visibility
cls

:LAUNCH_NODE
echo [%DATE% %TIME%] [INFO] Initializing Python print daemon execution...
    
:: Execute the python automation core script
::
:: parameter --mode [pdf/printer]
::
"C:\Users\Supervisor\AppData\Local\Programs\Python\Python314\python.exe" print_daemon.py --mode pdf

:: Error level verification block
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] [CRITICAL] Script terminated unexpectedly with exit code %ERRORLEVEL%.
    echo [%DATE% %TIME%] [INFO] Initiating automatic recovery loop in 5 seconds...
    timeout /t 5 /nobreak > nul
    goto LAUNCH_NODE
)

echo [%DATE% %TIME%] [INFO] Script execution completed successfully.
pause