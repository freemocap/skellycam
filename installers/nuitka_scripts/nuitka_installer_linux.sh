# scripts/build_linux.sh
#!/bin/bash
sudo apt-get update
sudo apt-get install -y clang portaudio19-dev
nuitka --onefile --linux-icon=shared/skellycam-logo/skellycam-favicon.ico --user-package-configuration-file=installers/skellycam-nuitka.config.yml skellycam/__main__.py
