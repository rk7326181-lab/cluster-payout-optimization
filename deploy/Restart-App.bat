@echo off
REM Double-click to restart cluster-payout-optimization.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart.ps1" %*
pause
