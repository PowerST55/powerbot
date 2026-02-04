#!/usr/bin/env python3
"""
Script de inicialización del sistema de BD
Ejecutar UNA VEZ al principio para verificar que todo está listo
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'keys', '.env'))
load_dotenv(env_path)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Verifica que las variables de entorno están configuradas"""
    logger.info("🔍 Verificando variables de entorno...")
    
    required_vars = [
        'DB_HOST',
        'DB_PORT',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD'
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
            logger.warning(f"  ❌ {var} no configurado")
        else:
            # Ocultar contraseña en logs
            display_value = '***' if 'PASSWORD' in var else value
            logger.info(f"  ✓ {var}: {display_value}")
    
    if missing:
        logger.error(f"\n❌ Faltan variables: {', '.join(missing)}")
        logger.error(f"   Edita: {env_path}")
        return False
    
    return True

def check_imports():
    """Verifica que los módulos requeridos estén instalados"""
    logger.info("\n📦 Verificando dependencias...")
    
    required_modules = [
        ('mysql.connector', 'mysql-connector-python'),
        ('dotenv', 'python-dotenv'),
    ]
    
    missing = []
    for module, package in required_modules:
        try:
            __import__(module)
            logger.info(f"  ✓ {module}")
        except ImportError:
            missing.append(package)
            logger.warning(f"  ❌ {module} (instalar: pip install {package})")
    
    if missing:
        logger.error(f"\n❌ Faltan dependencias:")
        for pkg in missing:
            logger.error(f"   pip install {pkg}")
        return False
    
    return True

def test_bd_connection():
    """Intenta conectar a la BD"""
    logger.info("\n🔗 Probando conexión a BD...")
    
    try:
        from database import DatabaseManager
        
        db = DatabaseManager()
        if db.is_connected:
            logger.info("  ✓ Conexión exitosa a BD")
            
            # Mostrar información
            try:
                cursor = db.connection.cursor()
                cursor.execute("SELECT DATABASE(), VERSION()")
                db_name, version = cursor.fetchone()
                cursor.close()
                
                logger.info(f"  ✓ BD: {db_name}")
                logger.info(f"  ✓ MySQL: {version}")
            except Exception as e:
                logger.warning(f"  ⚠ No se pudo obtener información: {e}")
            
            db.close()
            return True
        else:
            logger.error("  ❌ No se pudo conectar a BD")
            logger.error(f"     Host: {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}")
            logger.error(f"     BD: {os.getenv('DB_NAME')}")
            return False
    
    except Exception as e:
        logger.error(f"  ❌ Error: {e}")
        return False

def test_usermanager():
    """Intenta importar y usar usermanager"""
    logger.info("\n👥 Probando usermanager...")
    
    try:
        from usermanager import load_user_cache, init_database
        
        # Inicializar BD
        init_database()
        logger.info("  ✓ BD inicializada")
        
        # Cargar caché
        cache = load_user_cache()
        users = cache.get('users', [])
        logger.info(f"  ✓ Caché cargado: {len(users)} usuarios")
        
        return True
    
    except Exception as e:
        logger.error(f"  ❌ Error: {e}")
        return False

def print_summary(all_ok):
    """Imprime resumen final"""
    print("\n" + "="*60)
    if all_ok:
        print(" ✅ ¡INICIALIZACIÓN COMPLETADA CON ÉXITO!")
        print("="*60)
        print("\nTu sistema está listo para usar:")
        print("  1. El caché JSON se sincroniza automáticamente con BD")
        print("  2. Si la BD cae, los cambios se guardan localmente")
        print("  3. Ejecuta 'python sync_tools.py' para monitoreo")
        print("\nPróximos pasos:")
        print("  • Inicia tu discordbot en el VPS")
        print("  • Comienza a agregar usuarios")
        print("  • Verifica sincronización con sync_tools.py")
    else:
        print(" ❌ FALLOS EN LA INICIALIZACIÓN")
        print("="*60)
        print("\nFija los errores anteriores y vuelve a ejecutar este script")
    print("="*60 + "\n")

def main():
    """Función principal"""
    logger.info("╔════════════════════════════════════════════════════════════╗")
    logger.info("║     INICIALIZADOR DE SISTEMA DE BD - PowerBot               ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    
    results = []
    
    # 1. Verificar variables de entorno
    results.append(check_environment())
    
    # 2. Verificar imports
    results.append(check_imports())
    
    # 3. Probar conexión a BD
    results.append(test_bd_connection())
    
    # 4. Probar usermanager
    results.append(test_usermanager())
    
    # Resumen
    all_ok = all(results)
    print_summary(all_ok)
    
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
