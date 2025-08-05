#!/bin/bash
# Generate Python gRPC code from proto files

# Create the output directory if it doesn't exist
mkdir -p skellycam/api/grpc

# Generate the Python code
python -m grpc_tools.protoc \
  -I./proto \
  --python_out=./skellycam/api/grpc \
  --grpc_python_out=./skellycam/api/grpc \
  ./proto/skellycam.proto

# Create an empty __init__.py file if it doesn't exist
touch skellycam/api/grpc/__init__.py

# Fix imports in generated files
sed -i 's/import skellycam_pb2/from . import skellycam_pb2/' skellycam/api/grpc/skellycam_pb2_grpc.py

echo "Python gRPC code generation completed successfully."