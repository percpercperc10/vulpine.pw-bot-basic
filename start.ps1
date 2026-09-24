$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Registering commands (if account credentials are configured)..."
py -3 register_commands.py

Write-Host "Starting Vulpine bot..."
py -3 bot.py
