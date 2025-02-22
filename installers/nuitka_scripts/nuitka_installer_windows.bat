# scripts/build_windows.bat
@echo off
nuitka --onefile --windows-icon-from-ico=shared/skellycam-logo/skellycam-favicon.ico --user-package-configuration-file=installers/skellycam-nuitka.config.yml --remove-output --output-filename=skellycam_server.exe skellycam\__main__.py
