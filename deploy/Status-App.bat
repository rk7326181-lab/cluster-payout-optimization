@echo off
REM Double-click to check whether cluster-payout-optimization is running.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0status.ps1" %*
pause
