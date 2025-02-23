#!/bin/bash

# Get the directory of the script
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Script is located in: $script_dir"

sudo apt-get update
sudo apt-get install -y clang portaudio19-dev
nuitka --onefile --linux-icon="$script_dir/../shared/skellycam-logo/skellycam-favicon.ico" --user-package-configuration-file="$script_dir/../installers/skellycam-nuitka.config.yml" "$script_dir/../skellycam/__main__.py"