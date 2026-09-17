@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ejecuta Iniciar-Punto.bat primero para instalar las dependencias.
  pause
  exit /b 1
)
.venv\Scripts\python.exe manage.py create-admin
pause
