@echo off

echo `RUN PYTHON` script begin...!

echo Activate virtual environment...
CALL venv\Scripts\activate.bat

echo  Run `python skellycam/__main__.py`...
CALL python skellycam/__main__.py

echo `RUN PYTHON` script complete!

