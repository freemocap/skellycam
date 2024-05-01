@echo off
title run_headless.bat
echo Running skellycam in headless mode...

echo Starting uvicorn server...
start cmd /k "python ./skellycam/backend/run_backend.py"

echo Starting simple websocket client...
start cmd /k " color 2 & python ./skellycam/utilities/simple_websocket_client.py"

echo Skellycam is running in headless mode :D

pause