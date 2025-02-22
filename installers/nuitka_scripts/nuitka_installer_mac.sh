# scripts/build_mac.sh
#!/bin/bash
nuitka --onefile --macos-create-app-bundle=1 --macos-app-icon=shared/skellycam-logo/skellycam-favicon.ico --user-package-configuration-file=installers/skellycam-nuitka.config.yml --output-filename=skellycam-ui/skellycam_server skellycam/__main__.py
