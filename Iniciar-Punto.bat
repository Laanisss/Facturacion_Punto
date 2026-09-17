@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto error
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Abre http://127.0.0.1:8000 en tu navegador.
echo Deja esta ventana abierta. Ctrl+C detiene el servidor.
.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
pause
exit /b
:error
echo No se pudo iniciar. Revisa Python y tu conexion a internet.
pause
exit /b 1
