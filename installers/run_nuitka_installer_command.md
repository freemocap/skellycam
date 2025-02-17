# Nuitka Installer Commands

Copy-paste these commands into your terminal to build the SkellyCam server with Nuitka.

## Windows
```
nuitka --onefile --windows-icon-from-ico=shared/skellycam-logo/skellycam-favicon.ico --user-package-configuration-file=installers/skellycam-nuitka.config.yml skellycam/skellycam_server.py
```

## Mac
```
nuitka --onefile --macos-create-app-bundle=1 --macos-app-icon=shared/skellycam-logo/skellycam-favicon.ico --user-package-configuration-file=installers/skellycam-nuitka.config.yml skellycam/skellycam_server.py
```
## Linux
```
nuitka --onefile --linux-icon=shared/skellycam-logo/skellycam-favicon.ico --user-package-configuration-file=installers/skellycam-nuitka.config.yml skellycam/skellycam_server.py
```
___

## DEBUG OPTIONS

# --report=compilation-report.xml

## not working yet

### --onefile-windows-splash-screen-image=shared/skellycam-logo/skellycam-logo.png

- makes a giant splash screen that covers the whole screen and never goes away lol
- The docs have instructions on how to turn off the splash screen when the app starts up 
