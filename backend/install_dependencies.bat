@echo off
REM Script para instalar dependencias necesarias para el sistema de BD

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║   INSTALADOR DE DEPENDENCIAS - PowerBot BD                 ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Verificar si pip está disponible
python -m pip --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ERROR: Python no está instalado o pip no está disponible
    pause
    exit /b 1
)

echo [1/2] Instalando dependencias principales...
pip install mysql-connector-python python-dotenv websockets -q

if %errorlevel% neq 0 (
    echo ❌ ERROR: Falló la instalación de dependencias
    pause
    exit /b 1
)

echo ✓ Dependencias instaladas exitosamente

echo.
echo [2/2] Inicializando sistema de BD...
python init_database.py

if %errorlevel% neq 0 (
    echo.
    echo ⚠ La inicialización necesita atención
    echo Revisa los errores arriba
    pause
    exit /b 1
)

echo.
echo ✅ ¡INSTALACIÓN COMPLETADA!
echo.
echo El sistema está listo para usar. Próximos pasos:
echo   1. Abre discordbot en el VPS
echo   2. Los datos se sincronizarán automáticamente
echo   3. Ejecuta 'python sync_tools.py' para monitorear
echo.
pause
