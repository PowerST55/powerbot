#!/usr/bin/env python3
"""
Script de utilidades para sincronización de BD
Útil para mantener sincronizados el VPS y cliente local
"""

import os
import sys
import logging
from datetime import datetime

# Añadir el path del backend
sys.path.insert(0, os.path.dirname(__file__))

from database import DatabaseManager
from sync_manager import SyncManager
from usermanager import load_user_cache, save_user_cache

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_menu():
    """Muestra el menú principal"""
    print("\n" + "="*60)
    print(" UTILIDADES DE SINCRONIZACIÓN - PowerBot BD")
    print("="*60)
    print("\n1. Sincronizar TODO el caché a BD")
    print("2. Verificar estado de sincronización")
    print("3. Limpiar duplicados en caché")
    print("4. Ver conexión a BD")
    print("5. Forzar reconexión a BD")
    print("6. Generar reporte de usuarios")
    print("7. Salir\n")


def sync_all_to_db(db_manager: DatabaseManager):
    """Sincroniza todos los usuarios del caché a BD"""
    logger.info("🔄 Sincronizando caché completo a BD...")
    
    cache_data = load_user_cache()
    users = cache_data.get('users', [])
    
    if not users:
        logger.warning("⚠ No hay usuarios en caché para sincronizar")
        return
    
    synced = 0
    errors = 0
    
    for i, user in enumerate(users, 1):
        try:
            if db_manager.sync_user_from_cache(user):
                synced += 1
                logger.info(f"  [{i}/{len(users)}] ✓ {user.get('name')} sincronizado")
            else:
                errors += 1
        except Exception as e:
            logger.error(f"  [{i}/{len(users)}] ❌ Error: {e}")
            errors += 1
    
    logger.info(f"\n✅ Sincronización completada:")
    logger.info(f"   - Exitosos: {synced}")
    logger.info(f"   - Errores: {errors}")
    logger.info(f"   - Total: {len(users)}")


def check_sync_status(db_manager: DatabaseManager):
    """Verifica el estado de sincronización"""
    logger.info("\n📊 Estado de Sincronización:")
    logger.info(f"   BD conectada: {'✓ Sí' if db_manager.is_connected else '❌ No'}")
    
    cache_data = load_user_cache()
    users = cache_data.get('users', [])
    logger.info(f"   Usuarios en caché: {len(users)}")
    
    if db_manager.is_connected:
        try:
            cursor = db_manager.connection.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as count FROM users")
            result = cursor.fetchone()
            db_count = result['count'] if result else 0
            cursor.close()
            
            logger.info(f"   Usuarios en BD: {db_count}")
            
            if len(users) == db_count:
                logger.info("   ✓ Sincronización equilibrada")
            else:
                logger.warning(f"   ⚠ Diferencia: {abs(len(users) - db_count)} usuarios")
        except Exception as e:
            logger.error(f"   ❌ Error consultando BD: {e}")


def cleanup_duplicates(db_manager: DatabaseManager):
    """Limpia duplicados en caché"""
    logger.info("🧹 Limpiando duplicados...")
    
    cache_data = load_user_cache()
    users = cache_data.get('users', [])
    
    seen_yt = {}
    seen_discord = {}
    cleaned = 0
    
    for user in users[:]:  # Copiar para iterar mientras se modifica
        yt_id = user.get('youtube_id')
        discord_id = user.get('discord_id')
        
        # Verificar duplicados YouTube
        if yt_id and yt_id in seen_yt:
            logger.warning(f"  🗑 Duplicado YouTube: {yt_id} - {user.get('name')}")
            users.remove(user)
            cleaned += 1
            continue
        if yt_id:
            seen_yt[yt_id] = True
        
        # Verificar duplicados Discord
        if discord_id and discord_id in seen_discord:
            logger.warning(f"  🗑 Duplicado Discord: {discord_id} - {user.get('name')}")
            users.remove(user)
            cleaned += 1
            continue
        if discord_id:
            seen_discord[discord_id] = True
    
    if cleaned > 0:
        cache_data['users'] = users
        save_user_cache(cache_data)
        logger.info(f"✓ {cleaned} duplicados removidos")
    else:
        logger.info("✓ No se encontraron duplicados")


def show_bd_info(db_manager: DatabaseManager):
    """Muestra información de la conexión a BD"""
    print("\n📡 Información de Conexión:")
    
    if db_manager.is_connected:
        print("   ✓ BD CONECTADA")
        try:
            db_info = db_manager.connection.get_server_info()
            print(f"   Servidor MySQL: {db_info}")
            
            cursor = db_manager.connection.cursor()
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            cursor.close()
            print(f"   Base de datos: {db_name}")
            
            cursor = db_manager.connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM users) as users,
                    (SELECT COUNT(*) FROM transactions) as transactions,
                    (SELECT COUNT(*) FROM sync_log) as sync_logs
            """)
            stats = cursor.fetchone()
            cursor.close()
            
            print(f"\n   📊 Estadísticas:")
            print(f"      - Usuarios: {stats['users']}")
            print(f"      - Transacciones: {stats['transactions']}")
            print(f"      - Registros de sincronización: {stats['sync_logs']}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    else:
        print("   ❌ BD NO CONECTADA")
        print(f"   Host: {db_manager.config['host']}:{db_manager.config['port']}")
        print(f"   Base de datos: {db_manager.config['database']}")


def reconnect_bd(db_manager: DatabaseManager):
    """Intenta reconectar a la BD"""
    logger.info("🔄 Intentando reconectar a BD...")
    db_manager.close()
    
    if db_manager.connect():
        logger.info("✓ Reconexión exitosa")
    else:
        logger.error("❌ No se pudo reconectar")


def generate_report(db_manager: DatabaseManager):
    """Genera un reporte de usuarios"""
    logger.info("\n📋 Reporte de Usuarios")
    logger.info("="*60)
    
    cache_data = load_user_cache()
    users = cache_data.get('users', [])
    
    total_points = 0
    youtube_users = 0
    discord_users = 0
    linked_users = 0
    
    for user in users:
        if user.get('youtube_id'):
            youtube_users += 1
        if user.get('discord_id'):
            discord_users += 1
        if user.get('youtube_id') and user.get('discord_id'):
            linked_users += 1
        total_points += float(user.get('puntos', 0))
    
    logger.info(f"Total de usuarios: {len(users)}")
    logger.info(f"Usuarios YouTube: {youtube_users}")
    logger.info(f"Usuarios Discord: {discord_users}")
    logger.info(f"Cuentas vinculadas: {linked_users}")
    logger.info(f"Puntos totales: {total_points}")
    
    # Top 5 usuarios por puntos
    logger.info("\n🏆 Top 5 Usuarios:")
    sorted_users = sorted(users, key=lambda x: x.get('puntos', 0), reverse=True)[:5]
    for i, user in enumerate(sorted_users, 1):
        logger.info(f"  {i}. {user.get('name')} - {user.get('puntos', 0)} puntos")


def main():
    """Función principal"""
    logger.info("Inicializando sincronización...")
    
    # Crear gestor de BD
    try:
        db_manager = DatabaseManager()
    except Exception as e:
        logger.error(f"❌ No se pudo inicializar BD: {e}")
        return
    
    # Menú interactivo
    while True:
        print_menu()
        option = input("Selecciona una opción (1-7): ").strip()
        
        try:
            if option == '1':
                sync_all_to_db(db_manager)
            elif option == '2':
                check_sync_status(db_manager)
            elif option == '3':
                cleanup_duplicates(db_manager)
            elif option == '4':
                show_bd_info(db_manager)
            elif option == '5':
                reconnect_bd(db_manager)
            elif option == '6':
                generate_report(db_manager)
            elif option == '7':
                logger.info("👋 ¡Hasta luego!")
                break
            else:
                logger.warning("⚠ Opción no válida")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
    
    db_manager.close()


if __name__ == '__main__':
    main()
