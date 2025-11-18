@echo off
REM Start LibreCrawl - tries Docker first, falls back to Python

echo Checking for Docker...
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Docker found! Starting LibreCrawl with Docker...
    docker-compose up -d

    echo Waiting for LibreCrawl to start...
    timeout /t 3 /nobreak >nul

    REM Check if container is running
    docker ps | findstr librecrawl >nul
    if %errorlevel% equ 0 (
        echo LibreCrawl is running!
        echo Opening browser to http://localhost:5000
        start http://localhost:5000
    ) else (
        echo Error: LibreCrawl container failed to start
        docker-compose logs
        exit /b 1
    )
) else (
    echo Docker not found. Checking for Python...

    REM Check for Python
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        py --version >nul 2>&1
        if %errorlevel% neq 0 (
            echo Python not found! Downloading Python installer...

            REM Download Python installer
            echo Downloading Python 3.11...
            powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python-installer.exe'"

            if exist python-installer.exe (
                echo Running Python installer...
                echo Please follow the installer and CHECK 'Add Python to PATH'!
                start /wait python-installer.exe /passive InstallAllUsers=1 PrependPath=1

                REM Clean up installer
                del python-installer.exe

                echo Python installed! Please restart this script.
                pause
                exit /b 0
            ) else (
                echo Failed to download Python installer.
                echo Please install Python manually from https://www.python.org/downloads/
                pause
                exit /b 1
            )
        )
    )

    REM Python is available, install dependencies
    echo Python found! Installing dependencies...

    REM Check if requirements are already installed
    pip show flask >nul 2>&1
    if %errorlevel% neq 0 (
        echo Installing Python packages from requirements.txt...
        pip install -r requirements.txt

        if %errorlevel% neq 0 (
            echo Failed to install dependencies!
            pause
            exit /b 1
        )

        echo Installing Playwright browsers...
        playwright install chromium
    )

    REM Run LibreCrawl with Python in local mode
    echo Starting LibreCrawl in local mode...
    echo Opening browser to http://localhost:5000

    REM Open browser after 2 seconds (give Flask time to start)
    start /b timeout /t 2 /nobreak >nul && start http://localhost:5000

    REM Run main.py with local flag
    python main.py -l
)
