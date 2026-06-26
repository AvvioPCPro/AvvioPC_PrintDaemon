@echo off
color 0B
title AvvioPC Print Daemon - Build Automation
echo ========================================================
echo      AVVIOPC BUILD SYSTEM (PyInstaller + Inno Setup)
echo ========================================================
echo.

echo [1/3] Launching Python compilation via PyInstaller...
REM Executing PyInstaller with no console and embedding SumatraPDF
python -m PyInstaller --noconsole --onefile --add-binary "SumatraPDF.exe;." print_daemon.py
if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL ERROR] PyInstaller compilation failed!
    pause
    exit /b %errorlevel%
)
echo [OK] Executable successfully created inside \dist folder.
echo.

echo [2/3] Launching installer creation via Inno Setup...
REM Standard path for Inno Setup 6 compiler using safe quoting syntax
set "INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if not exist "%INNO_PATH%" (
    echo.
    echo [ERROR] Inno Setup compiler not found at standard path.
    echo Please verify the default Inno Setup 6 installation path.
    pause
    exit /b 1
)

REM Compiling the installer.iss file present in the same directory
"%INNO_PATH%" installer.iss
if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL ERROR] Inno Setup compilation failed!
    pause
    exit /b %errorlevel%
)
echo [OK] Installer successfully created.
echo.

echo [3/3] Launching automated upload to GitHub...
REM Copying the generated installer from user documents to the local project directory
set "FILENAME=Install_AvvioPC_Daemon.exe"
set "INNO_OUT_DIR=%USERPROFILE%\Documents\InnoSetupOutput"

if exist "%INNO_OUT_DIR%\%FILENAME%" (
    copy /Y "%INNO_OUT_DIR%\%FILENAME%" "%FILENAME%" >nul
) else (
    echo.
    echo [ERROR] Generated installer file not found in InnoSetupOutput directory!
    pause
    exit /b 1
)

REM Checking if current directory is inside a Git repository workspace
git rev-parse --is-inside-work-tree >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Current directory is not a Git repository.
    echo Please ensure this folder is initialized and linked to GitHub.
    pause
    exit /b 1
)

REM Staging and committing the binary artifact
git add "%FILENAME%"
git commit -m "Automated production build deployment" >nul 2>&1

REM Pushing the updated installer executable to GitHub repository
echo [INFO] Pushing production artifact to GitHub remote tracking branch...
git push origin main
if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL ERROR] GitHub push execution failed!
    echo Please verify network connectivity and repository authentication state.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo   BUILD AND DEPLOYMENT SUCCESSFULLY COMPLETED!
echo   Your installer has been uploaded to GitHub.
echo ========================================================
pause