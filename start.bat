@echo off
setlocal EnableDelayedExpansion

echo.
echo  ================================================
echo    ECHO -- Career Intelligence Agent
echo  ================================================
echo.

:: 1. Sync .env
if not exist ".env" (
    if exist ".env.example" (
        echo  Creating .env from .env.example...
        copy ".env.example" ".env" >nul
    ) else (
        echo  ERROR: .env.example not found!
        pause
        exit /b 1
    )
)
echo  Syncing environment configuration...
copy ".env" "frontend\.env" >nul

:: 2. Check Dependencies
python --version >nul 2>&1 || (echo ERROR: Python not found. && pause && exit /b 1)
node --version >nul 2>&1 || (echo ERROR: Node.js not found. && pause && exit /b 1)

:: 3. Menu
:menu
echo.
echo  [1] Start Full App (Local Only)
echo  [2] Start for Vercel (Backend + ngrok Tunnel)
echo  [3] Start Backend Only
echo  [4] Start Frontend Only
echo  [5] Exit
echo.
set /p choice="Select an option [1-5]: "

if "%choice%"=="1" goto start_full
if "%choice%"=="2" goto start_hybrid
if "%choice%"=="3" goto start_backend
if "%choice%"=="4" goto start_frontend
if "%choice%"=="5" exit
goto menu

:start_full
echo  Starting Full App...
start "Echo Backend" cmd /k "cd /d backend && python run.py api"
timeout /t 2 >nul
start "Echo Frontend" cmd /k "cd /d frontend && npm run dev"
goto end

:start_hybrid
:: Check for ngrok
if not exist "ngrok.exe" (
    echo [INFO] ngrok.exe not found.
    echo Please download it from https://ngrok.com/download and place it in the project root.
    pause
    goto menu
)
echo  Starting Backend + Tunnel...
start "Echo Backend" cmd /k "cd /d backend && python run.py api"
timeout /t 2 >nul
start "ngrok Tunnel" cmd /k "ngrok http 8000"
echo.
echo  [IMPORTANT] Once ngrok starts, copy the 'Forwarding' URL (https://...)
echo  and paste it into your Vercel VITE_API_URL environment variable.
goto end

:start_backend
start "Echo Backend" cmd /k "cd /d backend && python run.py api"
goto end

:start_frontend
start "Echo Frontend" cmd /k "cd /d frontend && npm run dev"
goto end

:end
echo.
echo  Setup complete. Windows are launching...
echo.
pause
endlocal
