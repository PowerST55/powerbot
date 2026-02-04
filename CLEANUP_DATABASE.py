#!/usr/bin/env python3
"""
Script de limpieza completa de BD y caché
Reinicia todas las IDs desde 1 y elimina duplicados
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Agregar backend al path
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import DatabaseManager
from backend.config import *

def backup_file(filepath):
    """Crea backup de un archivo antes de limpiarlo"""
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = filepath.replace('.json', f'_BACKUP_{timestamp}.json')
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(data)
            print(f"✅ Backup creado: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"❌ Error creando backup: {e}")
            return None
    return None

def cleanup_database():
    """Limpia la tabla users en BD"""
    try:
        db = DatabaseManager()
        db.connect()
        
        if not db.is_connected:
            print("❌ No se pudo conectar a la BD")
            return False
        
        cursor = db.connection.cursor()
        
        # Desactivar chequeo de claves foráneas
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        
        # TRUNCATE elimina todos los registros y reinicia AUTO_INCREMENT
        cursor.execute("TRUNCATE TABLE users")
        cursor.execute("TRUNCATE TABLE transactions")
        
        # Reactivar chequeo de claves foráneas
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        
        db.connection.commit()
        print("✅ Tablas users y transactions limpiadas")
        print("✅ AUTO_INCREMENT reiniciado a 1")
        
        # Verificar que esté vacía
        cursor.execute("SELECT COUNT(*) as count FROM users")
        count = cursor.fetchone()[0]
        print(f"✅ Registros en BD: {count}")
        
        cursor.close()
        db.connection.close()
        return True
        
    except Exception as e:
        print(f"❌ Error limpiando BD: {e}")
        return False

def cleanup_cache():
    """Limpia los archivos de caché JSON"""
    cache_files = {
        'data/user_cache.json': {'users': [], 'discord_to_id': {}, 'yt_to_id': {}, 'next_id': 1},
        'data/active_users.json': {},
        'discordbot/data/blacklist.json': {},
        'discordbot/data/leaderboard_channel.json': {},
        'discordbot/data/log_channel.json': {},
        'discordbot/data/notification_channel.json': {},
        'discordbot/data/queue.json': {},
        'discordbot/data/store_config.json': {},
        'discordbot/data/points_config.json': {},
    }
    
    for cache_file, default_content in cache_files.items():
        filepath = os.path.join(os.path.dirname(__file__), cache_file)
        
        # Backup si existe
        if os.path.exists(filepath):
            backup_file(filepath)
        
        # Crear archivo con estructura correcta (NO lista vacía)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(default_content, f, indent=2, ensure_ascii=False)
            print(f"✅ Limpiado: {cache_file}")
        except Exception as e:
            print(f"❌ Error limpiando {cache_file}: {e}")

def verify_cleanup():
    """Verifica que la limpieza fue exitosa"""
    print("\n" + "="*60)
    print("VERIFICACIÓN DE LIMPIEZA")
    print("="*60)
    
    # Verificar BD
    try:
        db = DatabaseManager()
        db.connect()
        if db.is_connected:
            cursor = db.connection.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            count = cursor.fetchone()[0]
            cursor.execute("SELECT AUTO_INCREMENT FROM information_schema.TABLES WHERE TABLE_NAME='users'")
            auto_inc = cursor.fetchone()
            
            print(f"\n📊 BASE DE DATOS:")
            print(f"  • Registros en users: {count}")
            print(f"  • AUTO_INCREMENT: {auto_inc[0] if auto_inc else 'N/A'}")
            
            cursor.close()
            db.connection.close()
    except Exception as e:
        print(f"❌ Error verificando BD: {e}")
    
    # Verificar caché
    cache_path = os.path.join(os.path.dirname(__file__), 'data/user_cache.json')
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        
        print(f"\n💾 CACHÉ JSON (user_cache.json):")
        print(f"  • Usuarios: {len(cache.get('users', []))}")
        print(f"  • next_id: {cache.get('next_id', 'N/A')}")
        print(f"  • discord_to_id: {len(cache.get('discord_to_id', {}))}")
        print(f"  • yt_to_id: {len(cache.get('yt_to_id', {}))}")
    except Exception as e:
        print(f"❌ Error leyendo caché: {e}")

def main():
    print("\n" + "="*60)
    print("LIMPIEZA COMPLETA DE BD Y CACHÉ")
    print("="*60)
    print("\n⚠️  ADVERTENCIA: Esto eliminará TODOS los usuarios y datos!")
    response = input("\n¿Estás seguro? (escribe 'SI' para confirmar): ")
    
    if response.upper() != 'SI':
        print("❌ Operación cancelada")
        return
    
    print("\n🧹 Iniciando limpieza...")
    
    # Limpiar BD
    print("\n1️⃣  Limpiando Base de Datos...")
    if cleanup_database():
        print("   ✅ BD limpiada exitosamente")
    else:
        print("   ❌ Error limpiando BD")
        return
    
    # Limpiar caché
    print("\n2️⃣  Limpiando caché JSON...")
    cleanup_cache()
    print("   ✅ Caché limpiada")
    
    # Verificar
    verify_cleanup()
    
    print("\n" + "="*60)
    print("✅ LIMPIEZA COMPLETADA")
    print("="*60)
    print("\nEl sistema está listo para empezar de nuevo con IDs desde 1")
    print("Reinicia el bot con: python start.py")

if __name__ == '__main__':
    main()
