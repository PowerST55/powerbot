@echo off
REM PowerBot - Discord Bot Launcher
REM Ejecuta el bot de Discord desde la raíz del proyecto

echo.
echo ========================================
echo       PowerBot - Discord Bot Starter
echo ========================================
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no está instalado
    echo Descárgalo desde: https://www.python.org/
    pause
    exit /b 1
)

REM Verificar archivo .env
if not exist "keys\.env" (
    echo [ADVERTENCIA] Archivo .env no encontrado
    echo Por favor, crea: keys\.env
    echo Con el contenido: TOKEN=tu_token_de_discord
    echo.
    pause
)

REM Instalar dependencias
echo [INFO] Verificando dependencias...
pip install -q discord.py python-dotenv >nul 2>&1

REM Ejecutar desde la raíz del proyecto
echo [INFO] Iniciando bot...
echo.

python -m discordbot

if errorlevel 1 (
    echo.
    echo [ERROR] El bot se cerró inesperadamente
    echo.
    pause
)
