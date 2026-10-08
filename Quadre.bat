@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Importacio de la safata d'entrada ===
".venv\Scripts\python.exe" -m quadre importa
echo.
echo === Generacio del quadre ===
".venv\Scripts\python.exe" -m quadre quadre
echo.
pause
