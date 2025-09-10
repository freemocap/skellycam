#!/bin/bash

# Clean previous build
echo "Creating pyinstaller build..."
pyinstaller skellycam.spec --clean

# Move the built server to UI directory
echo "Moving server to UI directory..."
mv dist/skellycam_server skellycam-ui/

cd skellycam-ui

echo "Running electron build..."
npm run build

cd ..

echo "Build completed!"