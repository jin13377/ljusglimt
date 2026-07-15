@echo off
chcp 65001 >nul
title Starta Ljusglimt
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0starta-ljusglimt.ps1"
if errorlevel 1 pause
