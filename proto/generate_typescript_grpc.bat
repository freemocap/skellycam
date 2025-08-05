@echo off
REM Generate TypeScript gRPC code from proto files

REM Create the output directory if it doesn't exist
if not exist "skellycam-ui\src\grpc" mkdir "skellycam-ui\src\grpc"

REM Generate the TypeScript code using protoc with ts_proto plugin
npx protoc ^
  --plugin=protoc-gen-ts_proto=skellycam-ui\node_modules\.bin\protoc-gen-ts_proto ^
  --ts_proto_out=.\skellycam-ui\src\grpc ^
  --ts_proto_opt="env=browser,outputServices=nice-grpc,outputServices=generic-definitions,outputJsonMethods=false,useExactTypes=false" ^
  --proto_path=.\proto ^
  .\proto\skellycam.proto

echo TypeScript gRPC code generation completed successfully.