@echo off
title Design Reference Studio Server
start "" "http://localhost:8080"
python "%~dp0server.py"
pause
