#!/usr/bin/env python3
"""
Script de validación de duplicados en caché y BD
Verifica la integridad de datos y reporta cualquier inconsistencia
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from backend.database import DatabaseManager
from backend.usermanager import load_user_cache, CACHE_FILE
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def validate_cache_duplicates():
    """Valida que no haya duplicados en user_cache.json"""
    logger.info("\n" + "="*70)
    logger.info("VALIDACIÓN DE DUPLICADOS EN CACHÉ")
    logger.info("="*70)
    
    try:
        user_cache = load_user_cache()
        users = user_cache.get("users", [])
        
        logger.info(f"\n📊 Total de usuarios en caché: {len(users)}")
        
        seen_discord = {}
        seen_youtube = {}
        seen_id = {}
        duplicates = []
        
        for idx, user in enumerate(users):
            if not isinstance(user, dict):
                logger.warning(f"⚠️  Usuario {idx} no es dict: {type(user)}")
                continue
            
            user_name = user.get("name", "UNKNOWN")
            user_id = user.get("id", "?")
            
            # Verificar discord_id
            discord_id = user.get("discord_id")
            if discord_id:
                if discord_id in seen_discord:
                    msg = f"🔴 DUPLICADO discord_id={discord_id}: '{user_name}' (ID={user_id}) vs '{seen_discord[discord_id]['name']}' (ID={seen_discord[discord_id]['id']})"
                    logger.error(msg)
                    duplicates.append(msg)
                else:
                    seen_discord[discord_id] = user
            
            # Verificar youtube_id
            youtube_id = user.get("youtube_id")
            if youtube_id:
                if youtube_id in seen_youtube:
                    msg = f"🔴 DUPLICADO youtube_id={youtube_id}: '{user_name}' (ID={user_id}) vs '{seen_youtube[youtube_id]['name']}' (ID={seen_youtube[youtube_id]['id']})"
                    logger.error(msg)
                    duplicates.append(msg)
                else:
                    seen_youtube[youtube_id] = user
            
            # Verificar id universal
            uid = user.get("id")
            if uid is not None:
                if uid in seen_id:
                    msg = f"🔴 DUPLICADO id={uid}: '{user_name}' vs '{seen_id[uid]['name']}'"
                    logger.error(msg)
                    duplicates.append(msg)
                else:
                    seen_id[uid] = user
        
        if duplicates:
            logger.error(f"\n❌ {len(duplicates)} DUPLICADOS ENCONTRADOS en caché")
            return False
        else:
            logger.info("✅ Caché: SIN DUPLICADOS")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error validando caché: {e}")
        return False

def validate_bd_duplicates():
    """Valida que no haya duplicados en BD"""
    logger.info("\n" + "="*70)
    logger.info("VALIDACIÓN DE DUPLICADOS EN BD")
    logger.info("="*70)
    
    try:
        db = DatabaseManager()
        db.connect()
        
        if not db.is_connected:
            logger.warning("⚠️  No se pudo conectar a BD, saltando validación")
            return None
        
        cursor = db.connection.cursor(dictionary=True)
        
        # Contar usuarios
        cursor.execute("SELECT COUNT(*) as count FROM users")
        count = cursor.fetchone()["count"]
        logger.info(f"\n📊 Total de usuarios en BD: {count}")
        
        # Buscar duplicados por discord_id
        cursor.execute("""
            SELECT discord_id, COUNT(*) as cnt, GROUP_CONCAT(id) as ids, GROUP_CONCAT(name) as names
            FROM users
            WHERE discord_id IS NOT NULL
            GROUP BY discord_id
            HAVING cnt > 1
        """)
        
        discord_dups = cursor.fetchall()
        if discord_dups:
            logger.error(f"\n🔴 {len(discord_dups)} discord_id duplicados en BD:")
            for row in discord_dups:
                logger.error(f"   - discord_id={row['discord_id']}: IDs={row['ids']}, Nombres={row['names']}")
        
        # Buscar duplicados por youtube_id
        cursor.execute("""
            SELECT youtube_id, COUNT(*) as cnt, GROUP_CONCAT(id) as ids, GROUP_CONCAT(name) as names
            FROM users
            WHERE youtube_id IS NOT NULL
            GROUP BY youtube_id
            HAVING cnt > 1
        """)
        
        youtube_dups = cursor.fetchall()
        if youtube_dups:
            logger.error(f"\n🔴 {len(youtube_dups)} youtube_id duplicados en BD:")
            for row in youtube_dups:
                logger.error(f"   - youtube_id={row['youtube_id']}: IDs={row['ids']}, Nombres={row['names']}")
        
        cursor.close()
        db.connection.close()
        
        if not discord_dups and not youtube_dups:
            logger.info("✅ BD: SIN DUPLICADOS")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"❌ Error validando BD: {e}")
        return False

def validate_mapeo_consistency():
    """Valida que los mapeos sean consistentes"""
    logger.info("\n" + "="*70)
    logger.info("VALIDACIÓN DE CONSISTENCIA DE MAPEOS")
    logger.info("="*70)
    
    try:
        user_cache = load_user_cache()
        users = user_cache.get("users", [])
        discord_to_id = user_cache.get("discord_to_id", {})
        yt_to_id = user_cache.get("yt_to_id", {})
        
        errors = []
        
        # Verificar que discord_to_id apunte a usuarios válidos
        for discord_id, uid in discord_to_id.items():
            user_found = False
            for u in users:
                if u.get("id") == uid and u.get("discord_id") == discord_id:
                    user_found = True
                    break
            if not user_found:
                msg = f"🔴 discord_to_id[{discord_id}]={uid} apunta a usuario no existente"
                logger.error(msg)
                errors.append(msg)
        
        # Verificar que yt_to_id apunte a usuarios válidos
        for youtube_id, uid in yt_to_id.items():
            user_found = False
            for u in users:
                if u.get("id") == uid and u.get("youtube_id") == youtube_id:
                    user_found = True
                    break
            if not user_found:
                msg = f"🔴 yt_to_id[{youtube_id}]={uid} apunta a usuario no existente"
                logger.error(msg)
                errors.append(msg)
        
        # Verificar que todos los usuarios con discord_id estén en discord_to_id
        for u in users:
            discord_id = u.get("discord_id")
            if discord_id and discord_to_id.get(discord_id) != u.get("id"):
                msg = f"🔴 Usuario {u.get('name')} (discord_id={discord_id}) NO está en discord_to_id correctamente"
                logger.error(msg)
                errors.append(msg)
        
        # Verificar que todos los usuarios con youtube_id estén en yt_to_id
        for u in users:
            youtube_id = u.get("youtube_id")
            if youtube_id and yt_to_id.get(youtube_id) != u.get("id"):
                msg = f"🔴 Usuario {u.get('name')} (youtube_id={youtube_id}) NO está en yt_to_id correctamente"
                logger.error(msg)
                errors.append(msg)
        
        if errors:
            logger.error(f"\n❌ {len(errors)} INCONSISTENCIAS encontradas en mapeos")
            return False
        else:
            logger.info("✅ Mapeos: CONSISTENTES")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error validando mapeos: {e}")
        return False

def main():
    logger.info("\n🔍 INICIANDO VALIDACIÓN DE INTEGRIDAD DE DATOS")
    
    results = {
        "cache_duplicates": validate_cache_duplicates(),
        "bd_duplicates": validate_bd_duplicates(),
        "mapeo_consistency": validate_mapeo_consistency()
    }
    
    logger.info("\n" + "="*70)
    logger.info("RESUMEN DE VALIDACIÓN")
    logger.info("="*70)
    
    status = "✅ TODO OK" if all(v in [True, None] for v in results.values()) else "🔴 ERRORES DETECTADOS"
    logger.info(f"\n{status}")
    
    for check, result in results.items():
        if result is None:
            symbol = "⊘"
            status_str = "SALTADO"
        elif result:
            symbol = "✅"
            status_str = "PASS"
        else:
            symbol = "❌"
            status_str = "FAIL"
        
        check_name = check.replace("_", " ").title()
        logger.info(f"  {symbol} {check_name}: {status_str}")
    
    logger.info("\n" + "="*70)

if __name__ == '__main__':
    main()
