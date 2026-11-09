@echo off

if not exist data mkdir data
echo Checking for Docker...
docker compose version >nul 2>&1
if errorlevel 1 goto nodocker

docker info >nul 2>&1
if errorlevel 1 goto dockernotrunning

echo Docker found! Starting LibreCrawl...
docker compose up -d
if errorlevel 1 goto dockerfailed
timeout /t 3 /nobreak >nul

echo.
echo ================================================================================
echo LibreCrawl is running!
echo Opening browser to http://localhost:5000
echo.
echo Press Ctrl+C to stop LibreCrawl
echo DO NOT close this window or LibreCrawl will keep running!
echo ================================================================================
echo.

start http://localhost:5000
docker compose logs -f
docker compose down
exit /b

:dockernotrunning
echo.
echo ERROR: Docker is installed but not running.
echo Start Docker Desktop, wait until it says it is running, then run this again.
echo.
pause
exit /b 1

:dockerfailed
echo.
echo ERROR: Docker could not start LibreCrawl. The messages above say why.
echo.
pause
exit /b 1

:nodocker
echo Docker not found. Checking for Python...
set PYTHON=python
python --version >nul 2>&1
if not errorlevel 1 goto checkversion
set PYTHON=py
py --version >nul 2>&1
if errorlevel 1 goto nopython

:checkversion
rem Python 3.11+, same as the Docker image
%PYTHON% -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto nopython

rem Own environment, so LibreCrawl's packages don't touch the system Python
if exist .venv\Scripts\python.exe goto installdeps
echo Creating a Python environment in .venv...
%PYTHON% -m venv .venv
if errorlevel 1 goto venvfailed

:installdeps
echo Installing Python packages from requirements.txt...
.venv\Scripts\python -m pip install --quiet -r requirements.txt
if errorlevel 1 goto depsfailed

echo Installing Playwright browser...
.venv\Scripts\python -m playwright install chromium
if errorlevel 1 goto depsfailed

echo Starting LibreCrawl...
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"
.venv\Scripts\python main.py -l
exit /b

:venvfailed
echo.
echo ERROR: Could not create the Python environment in .venv.
echo.
pause
exit /b 1

:depsfailed
echo.
echo ERROR: Failed to install LibreCrawl's dependencies. The messages above say why.
echo.
pause
exit /b 1

:nopython
echo.
echo ERROR: Neither Docker nor Python 3.11+ found!
echo.
echo Please install one of:
echo - Docker Desktop: https://www.docker.com/products/docker-desktop
echo - Python 3.11+: https://www.python.org/downloads/
echo.
pause
exit /b 1
