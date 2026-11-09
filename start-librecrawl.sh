#!/bin/bash

# Start LibreCrawl - tries Docker first, falls back to Python

mkdir -p data
echo "Checking for Docker..."
if docker compose version &> /dev/null; then
    if ! docker info &> /dev/null; then
        echo "Docker is installed but not running."
        echo "Start Docker (Docker Desktop on Mac), wait until it is running, then run this again."
        exit 1
    fi

    echo "Docker found! Starting LibreCrawl with Docker..."
    docker compose up -d

    # Wait for the service to be ready
    echo "Waiting for LibreCrawl to start..."
    sleep 3

    # Check if container is running
    if docker ps | grep -q librecrawl; then
        echo ""
        echo "================================================================================"
        echo "LibreCrawl is running!"
        echo "Opening browser to http://localhost:5000"
        echo ""
        echo "Press Ctrl+C to stop LibreCrawl and exit"
        echo "DO NOT close this terminal or LibreCrawl will keep running in the background!"
        echo "================================================================================"
        echo ""

        # Detect OS and open browser
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            xdg-open http://localhost:5000 2>/dev/null || sensible-browser http://localhost:5000
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            open http://localhost:5000
        else
            echo "Please open http://localhost:5000 in your browser"
        fi

        # Trap Ctrl+C to gracefully shutdown
        trap 'echo ""; echo "Stopping LibreCrawl..."; docker compose down; exit 0' INT

        # Keep terminal open and show logs
        echo "Showing live logs (press Ctrl+C to stop):"
        echo ""
        docker compose logs -f
    else
        echo "Error: LibreCrawl container failed to start"
        docker compose logs
        exit 1
    fi
else
    echo "Docker not found. Checking for Python..."

    # Python 3.11+, same as the Docker image
    if ! command -v python3 &> /dev/null || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
        echo "Python 3.11 or later not found!"
        echo ""
        echo "Installation instructions:"
        echo "  Ubuntu/Debian: sudo apt install python3 python3-venv"
        echo "  macOS: brew install python"
        echo "  Or download from: https://www.python.org/downloads/"
        exit 1
    fi

    # Own environment: Homebrew and recent Linux Python refuse global pip installs (PEP 668)
    if [ ! -x .venv/bin/python ]; then
        echo "Creating a Python environment in .venv..."
        if ! python3 -m venv .venv; then
            echo "Could not create the Python environment!"
            echo "  Ubuntu/Debian: sudo apt install python3-venv"
            exit 1
        fi
    fi

    echo "Installing Python packages from requirements.txt..."
    if ! .venv/bin/python -m pip install --quiet -r requirements.txt; then
        echo "Failed to install dependencies!"
        exit 1
    fi

    echo "Installing Playwright browser..."
    if ! .venv/bin/python -m playwright install chromium; then
        echo "Failed to install the Playwright browser!"
        exit 1
    fi

    # Run LibreCrawl with Python in local mode
    echo "Starting LibreCrawl in local mode..."
    echo "Opening browser to http://localhost:5000"

    # Open browser after 2 seconds (give Flask time to start)
    (sleep 2 && {
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            xdg-open http://localhost:5000 2>/dev/null || sensible-browser http://localhost:5000
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            open http://localhost:5000
        fi
    }) &

    .venv/bin/python main.py -l
fi
