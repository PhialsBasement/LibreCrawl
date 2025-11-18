@echo off

echo Checking for Docker...
docker --version 2>nul
if errorlevel 1 goto nodocker

echo Docker found! Starting LibreCrawl...
docker-compose up -d
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
docker-compose logs -f
docker-compose down
exit /b

:nodocker
echo Docker not found. Checking for Python...
python --version 2>nul
if errorlevel 1 goto trypy

:foundpython
echo Python found! Checking dependencies...
pip show flask 2>nul
if errorlevel 1 goto installdeps

:rundirect
echo Starting LibreCrawl...
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"
python main.py -l
exit /b

:trypy
py --version 2>nul
if errorlevel 1 goto nopython
set PYTHON=py
goto foundpython

:installdeps
echo Installing dependencies...
pip install -r requirements.txt
playwright install chromium
goto rundirect

:nopython
echo.
echo ERROR: Neither Docker nor Python found!
echo.
echo Please install one of:
echo - Docker Desktop: https://www.docker.com/products/docker-desktop
echo - Python 3.11+: https://www.python.org/downloads/
echo.
pause
exit /b 1
