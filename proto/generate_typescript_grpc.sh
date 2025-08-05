#!/bin/bash
# Generate TypeScript gRPC code from proto files

# Create the output directory if it doesn't exist
mkdir -p skellycam-ui/src/contexts/grpc-context/grpc_generated

# Generate the TypeScript code using protoc with ts_proto plugin
npx protoc \
      --plugin=protoc-gen-ts_proto=./node_modules/.bin/protoc-gen-ts_proto \
      --ts_proto_out=./src/contexts/grpc-context/grpc_generated \
      --ts_proto_opt=env=node,outputServices=nice-grpc,outputServices=generic-definitions \
      ./path/to/your/skellycam.proto
echo "TypeScript gRPC code generation completed successfully."
