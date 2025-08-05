#!/bin/bash
# Generate TypeScript gRPC code from proto files

# Create the output directory if it doesn't exist
mkdir -p skellycam-ui/src/contexts/grpc-context/grpc_generated

# Generate the TypeScript code using protoc with ts_proto plugin
npx protoc --plugin=protoc-gen-ts_proto=skellycam-ui/node_modules/.bin/protoc-gen-ts_proto \
           --ts_proto_out=skellycam-ui/src/contexts/grpc-context/grpc_generated \
           --ts_proto_opt=esModuleInterop=true,outputServices=nice-grpc,outputJsonMethods=false \
           -I ./proto \
           ./proto/skellycam.proto

echo "TypeScript gRPC code generation completed successfully."
