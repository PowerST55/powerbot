@echo off
REM PowerBot - Discord Bot Launcher
REM Este script inicia el bot de Discord

echo.
echo ========================================
echo       PowerBot - Discord Bot
echo ========================================
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no está instalado o no está en PATH
    echo Por favor, instala Python desde https://www.python.org/
    pause
    exit /b 1
)

REM Cambiar al directorio raíz del proyecto
cd /d "%~dp0.."

REM Verificar si el archivo .env existe
if not exist "keys\.env" (
    echo [ADVERTENCIA] Archivo .env no encontrado en: keys\.env
    echo Por favor, crea el archivo .env con tus credenciales
    echo.
)

REM Instalar dependencias si es necesario
echo Verificando dependencias...
pip install -q discord.py python-dotenv >nul 2>&1

REM Ejecutar el bot desde la raíz
echo.
echo [INFO] Iniciando bot de Discord...
echo.

python -m discordbot

REM Si el bot falla, mostrar el error
if errorlevel 1 (
    echo.
    echo [ERROR] El bot se cerró con un error
    pause
)
