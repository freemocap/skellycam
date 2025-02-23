@echo off
:: Get the directory of the script
set script_dir=%~dp0
echo Script is located in: %script_dir%

nuitka --onefile --windows-icon-from-ico=%script_dir%..\..\shared\skellycam-logo\skellycam-favicon.ico --user-package-configuration-file=%script_dir%skellycam-nuitka.config.yml --remove-output --output-filename=skellycam_server.exe %script_dir%..\..\skellycam\__main__.py