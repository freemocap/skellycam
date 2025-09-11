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

VOLUME=$(hdiutil attach "skellycam-ui/release/2.0.0/skellycam_2.0.0_installer_arm64.dmg" | tail -1 | awk '{print $3}')
# cp -r "/Volumes/skellycam 2.0.0-arm64/skellycam.app" /Applications/
# diskutil unmount "/Volumes/skellycam 2.0.0-arm64"

echo "Build completed!"