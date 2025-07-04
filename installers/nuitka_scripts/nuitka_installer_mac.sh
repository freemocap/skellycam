#!/bin/bash

# Get the directory of the script
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Script is located in: $script_dir"
brew install portaudio
nuitka --onefile --macos-create-app-bundle=1 --macos-app-icon="$script_dir/../shared/skellycam-logo/skellycam-favicon.ico" --user-package-configuration-file="$script_dir/../installers/skellycam-nuitka.config.yml" --output-filename="skellycam_server" "$script_dir/../skellycam/__main__.py"