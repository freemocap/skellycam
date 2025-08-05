@echo off
REM Generate Python gRPC code from proto files

REM Create the output directory if it doesn't exist
if not exist "skellycam\api\grpc" mkdir "skellycam\api\grpc"

REM Generate the Python code
python -m grpc_tools.protoc ^
  -I./proto ^
  --python_out=./skellycam/api/grpc ^
  --grpc_python_out=./skellycam/api/grpc ^
  ./proto/skellycam.proto

REM Create an empty __init__.py file if it doesn't exist
if not exist "skellycam\api\grpc\__init__.py" type nul > "skellycam\api\grpc\__init__.py"

REM Fix imports in generated files
powershell -Command "(Get-Content skellycam\api\grpc\skellycam_pb2_grpc.py) -replace 'import skellycam_pb2', 'from . import skellycam_pb2' | Set-Content skellycam\api\grpc\skellycam_pb2_grpc.py"

echo Python gRPC code generation completed successfully.