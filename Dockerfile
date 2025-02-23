# Use a base image with Python and PowerShell
FROM mcr.microsoft.com/windows/servercore:ltsc2022

# Install Chocolatey and Rcedit
RUN powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; \
    iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"
RUN choco install rcedit -y

# Install Python and Rust
RUN choco install python --version=3.11 -y
RUN choco install rust -y

# Set the working directory
WORKDIR /app

# Copy the PowerShell script and your project files into the container
COPY installers/nuitka_scripts/install-windows-pyapp.ps1 /app/
COPY installers /app/

# Run your PowerShell script
RUN powershell -ExecutionPolicy Bypass -File install-windows-pyapp.ps1

# Entry point to run the built executable
ENTRYPOINT ["./skellycam-server.exe"]
