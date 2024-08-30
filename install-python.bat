@echo off

SET PYTHON_PATH=C:\Python311\python.exe

echo Using `python` at: %PYTHON_PATH%

echo Create virtual environment
CALL %%PYTHON_PATH%% -m venv venv

echo Activate virtual environment
CALL venv\Scripts\activate.bat

echo Upgrade pip
CALL %%PYTHON_PATH%% -m ensurepip --upgrade

echo Install Python requirements
CALL pip install -e .

echo  Build with PyInstaller
CALL pyinstaller --onefile skellycam/__main__.py

echo Installation and setup complete!

