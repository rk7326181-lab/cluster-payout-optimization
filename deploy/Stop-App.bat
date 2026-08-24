@echo off
REM Double-click to stop cluster-payout-optimization.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*
pause
