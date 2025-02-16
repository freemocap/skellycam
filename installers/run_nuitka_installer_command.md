#Windows

nuitka --onefile --windows-icon-from-ico=shared/skellycam-logo/skellycam-favicon.ico --report=compilation-report.xml --onefile-windows-splash-screen-image=shared/skellycam-logo/skellycam-logo.png  --user-package-configuration-file=installers/skellycam-nuitka.config.yml skellycam/skellycam_server.py

#Mac

nuitka --onefile   --macos-create-app-bundle=1 --macos-app-icon=shared/skellycam-logo/skellycam-favicon.ico --report=compilation-report.xml  --user-package-configuration-file=installers/skellycam-nuitka.config.yml skellycam/skellycam_server.py

#Linux

nuitka --onefile  --linux-icon=shared/skellycam-logo/skellycam-favicon.ico --report=compilation-report.xml  --user-package-configuration-file=installers/skellycam-nuitka.config.yml skellycam/skellycam_server.py
