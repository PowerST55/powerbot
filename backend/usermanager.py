import json
import os
import requests
import time
import logging

import shutil
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar gestores de BD y sincronización desde el cliente CENTRAL (PC)
try:
    from .database import DatabaseManager
    from .sync_manager import SyncManager
    DB_AVAILABLE = True
    logger.info("✓ Importando BD desde cliente central (PC)")
except ImportError as e:
    try:
        import sys
        backend_root = os.path.abspath(os.path.dirname(__file__))
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)

        from database import DatabaseManager
        from sync_manager import SyncManager
        DB_AVAILABLE = True
        logger.info("✓ Importando BD desde cliente central (PC)")
    except ImportError as e2:
        logger.warning(f"⚠ No se pudieron importar módulos de BD: {e2}")
        DB_AVAILABLE = False

# Nueva ruta base para los archivos JSON
BASE_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
if not os.path.exists(BASE_DATA_DIR):
    os.makedirs(BASE_DATA_DIR)

CACHE_FILE = os.path.join(BASE_DATA_DIR, "user_cache.json")
BAN_FILE = os.path.join(BASE_DATA_DIR, "banned_users.json")
CUSTOM_FILE = os.path.join(BASE_DATA_DIR, "custom_users.json")

# Gestores globales de BD y sincronización
db_manager = None
sync_manager = None

def init_database():
    """Inicializa el gestor de BD y sincronización
    
    Se conecta a la BD CENTRAL que está en el PC cliente
    Si falla, el sistema continúa solo con caché JSON.
    """
    global db_manager, sync_manager, DB_AVAILABLE
    
    if not DB_AVAILABLE:
        logger.warning("⚠ Módulos de BD no disponibles")
        return False
    
    try:
        logger.info("🔄 Inicializando sincronización con BD CENTRAL (PC)...")
        db_manager = DatabaseManager()
        sync_manager = SyncManager(db_manager, save_user_cache, load_user_cache)
        logger.info("✓ Sincronización con BD central iniciada (Discord Bot ↔ PC)")
        return True
    except Exception as e:
        logger.warning(f"⚠ No se pudo inicializar BD: {e}")
        logger.warning("  El sistema funcionará solo con caché JSON")
        return False

# -------------------- Gestión de usuarios --------------------

def _download_avatar(url: str, save_path: str, name: str, is_discord: bool = False, max_retries: int = 3):
    """Descarga un avatar con reintentos automáticos y headers apropiados.
    
    Args:
        url: URL del avatar
        save_path: Ruta donde guardar el archivo
        name: Nombre del usuario (para logging)
        is_discord: Si es avatar de Discord (para mejor handling)
        max_retries: Número máximo de intentos
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            # Usar timeout más largo para Discord CDN
            timeout = 15 if is_discord else 10
            response = requests.get(url, timeout=timeout, headers=headers)
            
            if response.status_code == 200:
                with open(save_path, "wb") as img_file:
                    img_file.write(response.content)
                if is_discord:
                    print(f"✓ Avatar de Discord descargado: {name}")
                else:
                    print(f"✓ Avatar descargado: {name}")
                return True
            elif response.status_code == 404:
                print(f"⚠ Avatar no encontrado (404): {name} - {url}")
                return False
            elif response.status_code == 429:
                # Rate limiting - esperar y reintentar
                if attempt < max_retries - 1:
                    print(f"⚠ Rate limit de Discord CDN, reintentando en 2s... ({attempt + 1}/{max_retries})")
                    time.sleep(2)
                    continue
            else:
                if attempt < max_retries - 1:
                    print(f"⚠ Error HTTP {response.status_code}, reintentando... ({attempt + 1}/{max_retries})")
                    time.sleep(1)
                    continue
                else:
                    print(f"⚠ No se pudo descargar avatar de {name} (HTTP {response.status_code}): {url}")
                    return False
                    
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"⚠ Timeout descargando avatar, reintentando... ({attempt + 1}/{max_retries})")
                time.sleep(1)
                continue
            else:
                print(f"⚠ Timeout al descargar avatar de {name} después de {max_retries} intentos")
                return False
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                print(f"⚠ Error de conexión descargando avatar, reintentando... ({attempt + 1}/{max_retries})")
                time.sleep(1)
                continue
            else:
                print(f"⚠ Error de conexión al descargar avatar de {name}")
                return False
        except Exception as e:
            print(f"⚠ Error inesperado descargando avatar de {name}: {type(e).__name__}: {e}")
            return False
    
    return False


def clean_orphaned_users(user_cache):
    """Elimina usuarios huérfanos SOLO si están completamente vacíos (sin IDs, puntos, ni nombre válido)."""
    users = user_cache.get("users", [])
    original_count = len(users)

    cleaned_users = []
    orphaned_count = 0

    for user in users:
        has_discord = user.get("discord_id") is not None
        has_youtube = user.get("youtube_id") is not None
        has_points = user.get("puntos", 0) > 0
        has_valid_name = bool(user.get("name")) and user.get("name") != "Unknown"
        
        # ✅ PROTECCIÓN: Solo eliminar si está COMPLETAMENTE vacío
        if has_discord or has_youtube or has_points or has_valid_name:
            cleaned_users.append(user)
        else:
            orphaned_count += 1
            print(f"🗑️ Eliminando usuario COMPLETAMENTE vacío: ID {user.get('id')} (sin IDs, sin puntos, sin nombre)")

    # Actualizar caché con usuarios limpios
    user_cache["users"] = cleaned_users

    # Reconstruir mapeos sin residuos
    user_cache["yt_to_id"] = {}
    user_cache["discord_to_id"] = {}

    for user in cleaned_users:
        uid = user.get("id")
        yt_id = user.get("youtube_id")
        dc_id = user.get("discord_id")
        if yt_id:
            user_cache["yt_to_id"][str(yt_id)] = uid
        if dc_id:
            user_cache["discord_to_id"][str(dc_id)] = uid

    # Ajustar next_id para evitar colisiones al crear nuevos usuarios
    max_id = max((u.get("id", 0) or 0 for u in cleaned_users), default=0)
    user_cache["next_id"] = max_id + 1 if max_id >= 0 else 1

    if orphaned_count > 0:
        print(
            f"✓ Limpieza completada: {orphaned_count} usuario(s) huérfano(s) eliminado(s) "
            f"({original_count} → {len(cleaned_users)}), next_id={user_cache['next_id']}"
        )
        save_user_cache(user_cache)

    return user_cache


def load_user_cache():
    """Carga la caché de usuarios desde el archivo JSON (nuevo formato)."""
    if not os.path.exists(CACHE_FILE):
        print(f"⚠️ ADVERTENCIA: No existe {CACHE_FILE}, creando nuevo cache vacío")
        return {"users": [], "yt_to_id": {}, "discord_to_id": {}, "next_id": 1}
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and "users" in data:
                # ✅ PROTECCIÓN: Limpieza deshabilitada para evitar pérdida de datos
                # Solo ejecutar manualmente cuando sea necesario con clean_orphaned_users()
                # data = clean_orphaned_users(data)
                
                # Asegurar que existen todos los campos necesarios
                if "discord_to_id" not in data:
                    data["discord_to_id"] = {}
                if "yt_to_id" not in data:
                    data["yt_to_id"] = {}
                if "next_id" not in data:
                    data["next_id"] = 1
                
                return data
            # Migración automática desde formato antiguo (dict de channel_id)
            if isinstance(data, dict):
                users = []
                yt_to_id = {}
                next_id = 1
                for yt_id, info in data.items():
                    user = {
                        "id": next_id,
                        "youtube_id": yt_id,
                        "name": info.get("name", ""),
                        "avatar_url": info.get("avatar_url", ""),
                        "avatar_local": info.get("avatar_local", ""),
                        "isModerator": info.get("isModerator", False),
                        "isMember": info.get("isMember", False),
                        "puntos": info.get("puntos", 0)
                    }
                    users.append(user)
                    yt_to_id[yt_id] = next_id
                    next_id += 1
                return {"users": users, "yt_to_id": yt_to_id, "next_id": next_id}
            return {"users": [], "yt_to_id": {}, "next_id": 1}
    except FileNotFoundError as e:
        print(f"⚠️ ERROR: Archivo no encontrado {CACHE_FILE}: {e}")
        print("   Creando nuevo cache vacío...")
        return {"users": [], "yt_to_id": {}, "discord_to_id": {}, "next_id": 1}
    except json.JSONDecodeError as e:
        print(f"🔴 ERROR CRÍTICO: JSON corrupto en {CACHE_FILE}: {e}")
        print(f"   Línea {e.lineno}, Columna {e.colno}")
        # Crear respaldo del archivo corrupto
        corrupted_backup = CACHE_FILE.replace('.json', f'_CORRUPTO_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        try:
            shutil.copy2(CACHE_FILE, corrupted_backup)
            print(f"   ✓ Respaldo del archivo corrupto guardado en: {corrupted_backup}")
        except Exception:
            pass
        return {"users": [], "yt_to_id": {}, "discord_to_id": {}, "next_id": 1}
    except Exception as e:
        print(f"🔴 ERROR INESPERADO al cargar cache: {type(e).__name__}: {e}")
        return {"users": [], "yt_to_id": {}, "discord_to_id": {}, "next_id": 1}

def save_user_cache(user_cache):
    """Guarda la caché de usuarios en el archivo JSON (nuevo formato) con respaldo automático."""
    
    # ✅ PROTECCIÓN: Crear respaldo antes de sobrescribir
    if os.path.exists(CACHE_FILE):
        try:
            # Mantener últimos 10 respaldos
            backup_dir = os.path.join(BASE_DATA_DIR, 'backups')
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            backup_file = os.path.join(backup_dir, f'user_cache_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            shutil.copy2(CACHE_FILE, backup_file)
            
            # Limpiar respaldos antiguos (mantener solo los últimos 10)
            backups = sorted([f for f in os.listdir(backup_dir) if f.startswith('user_cache_backup_')])
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    try:
                        os.remove(os.path.join(backup_dir, old_backup))
                    except Exception:
                        pass
        except Exception as e:
            print(f"⚠️ No se pudo crear respaldo automático: {e}")
    
    # ✅ PROTECCIÓN: Validar datos antes de guardar
    if not isinstance(user_cache, dict):
        print(f"🔴 ERROR: Intentando guardar user_cache inválido (no es dict): {type(user_cache)}")
        return
    
    if "users" not in user_cache or not isinstance(user_cache["users"], list):
        print(f"🔴 ERROR: user_cache no tiene lista 'users' válida")
        return
    
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_cache, f, indent=4, ensure_ascii=False)
        print(f"✓ Cache guardado exitosamente: {len(user_cache.get('users', []))} usuarios")
    except Exception as e:
        print(f"🔴 ERROR CRÍTICO al guardar {CACHE_FILE}: {e}")
        raise


def cache_user_info(youtube_id, name, avatar_url, is_moderator=False, is_member=False, skip_save=False):
    """Agrega o actualiza la información del usuario en la caché y descarga su avatar."""
    user_cache = load_user_cache()
    users = user_cache.get("users", [])
    yt_to_id = user_cache.get("yt_to_id", {})
    discord_to_id = user_cache.get("discord_to_id", {})
    next_id = user_cache.get("next_id", 1)

    # Buscar si ya existe el usuario por youtube_id
    user_id = yt_to_id.get(youtube_id)
    user = None
    for u in users:
        if u.get("youtube_id") == youtube_id:
            user = u
            break

    # Si no existe, crear uno nuevo
    if not user:
        user = {
            "id": next_id,
            "youtube_id": youtube_id,
            "discord_id": None,  # Para vincular en el futuro
            "name": name,
            "avatar_url": avatar_url,
            "avatar_local": f"avatars/{youtube_id}.jpg",
            "avatar_discord_url": None,  # Avatar de Discord
            "avatar_discord_local": None,  # Avatar guardado de Discord
            "isModerator": bool(is_moderator),
            "isMember": bool(is_member),
            "puntos": 0,
            "platform_sources": ["youtube"]  # Plataformas desde donde viene
        }
        users.append(user)
        yt_to_id[youtube_id] = next_id
        user_cache["next_id"] = next_id + 1
    else:
        # Actualizar datos
        user["name"] = name
        user["avatar_url"] = avatar_url
        user["isModerator"] = bool(is_moderator)
        user["isMember"] = bool(is_member)
        if "platform_sources" not in user:
            user["platform_sources"] = ["youtube"]

    # Descargar avatar si es necesario
    raiz_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    avatars_dir = os.path.join(raiz_dir, "navegador", "avatars")
    if not os.path.exists(avatars_dir):
        os.makedirs(avatars_dir)
    avatar_path = os.path.join(avatars_dir, f"{youtube_id}.jpg")
    need_download = (
        not os.path.exists(avatar_path) or user.get("avatar_url") != avatar_url
    )
    if need_download:
        _download_avatar(avatar_url, avatar_path, name, is_discord=False)

    user_cache["users"] = users
    user_cache["yt_to_id"] = yt_to_id
    if "discord_to_id" not in user_cache:
        user_cache["discord_to_id"] = {}
    
    # Solo guardar si skip_save es False (modo normal)
    if not skip_save:
        save_user_cache(user_cache)
    
    return user_cache


def cache_discord_user(discord_id, name, avatar_url=None):
    """Agrega o actualiza la información del usuario de Discord en la caché.
    
    Args:
        discord_id: ID de Discord del usuario (int o str)
        name: Nombre del usuario en Discord
        avatar_url: URL del avatar de Discord (opcional)
    """
    user_cache = load_user_cache()
    users = user_cache.get("users", [])
    discord_to_id = user_cache.get("discord_to_id", {})
    yt_to_id = user_cache.get("yt_to_id", {})
    next_id = user_cache.get("next_id", 1)
    
    discord_id_str = str(discord_id)
    
    # Buscar si ya existe el usuario por discord_id
    user_id = discord_to_id.get(discord_id_str)
    user = None
    for u in users:
        if u.get("discord_id") == discord_id_str:
            user = u
            break
    
    # Si no existe, crear uno nuevo
    if not user:
        user = {
            "id": next_id,
            "youtube_id": None,  # Para vincular en el futuro
            "discord_id": discord_id_str,
            "name": name,
            "avatar_url": None,  # YouTube avatar
            "avatar_local": None,  # YouTube avatar local
            "avatar_discord_url": avatar_url,
            "avatar_discord_local": f"avatars/discord_{discord_id_str}.jpg",
            "isModerator": False,
            "isMember": False,
            "puntos": 0,
            "platform_sources": ["discord"]
        }
        users.append(user)
        discord_to_id[discord_id_str] = next_id
        user_cache["next_id"] = next_id + 1
        logger.info(f"✓ Nuevo usuario Discord cacacheado: {name} (ID: {discord_id})")
    else:
        # Actualizar datos
        if user["name"] != name:
            user["name"] = name
        if avatar_url and user.get("avatar_discord_url") != avatar_url:
            user["avatar_discord_url"] = avatar_url
        # Asegurar que Discord está en las plataformas
        if "platform_sources" not in user:
            user["platform_sources"] = []
        if "discord" not in user["platform_sources"]:
            user["platform_sources"].append("discord")
            logger.info(f"✓ Plataforma Discord agregada a usuario: {name}")
    
    # Descargar avatar de Discord si es necesario
    if avatar_url:
        raiz_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        avatars_dir = os.path.join(raiz_dir, "navegador", "avatars")
        if not os.path.exists(avatars_dir):
            os.makedirs(avatars_dir)
        
        avatar_path = os.path.join(avatars_dir, f"discord_{discord_id_str}.jpg")
        need_download = (
            not os.path.exists(avatar_path) or user.get("avatar_discord_url") != avatar_url
        )
        
        if need_download:
            _download_avatar(avatar_url, avatar_path, name, is_discord=True)
    
    user_cache["users"] = users
    user_cache["yt_to_id"] = yt_to_id
    user_cache["discord_to_id"] = discord_to_id
    save_user_cache(user_cache)
    
    # Sincronizar a BD si está disponible
    if sync_manager:
        sync_manager.sync_user_bidirectional(user, source='local')
    
    return user["id"]  # Retornar el ID único del usuario para futuro uso


def get_user_by_discord_id(discord_id):
    """Obtiene un usuario por su ID de Discord."""
    user_cache = load_user_cache()
    discord_id_str = str(discord_id)
    
    for user in user_cache.get("users", []):
        if user.get("discord_id") == discord_id_str:
            return user
    return None


def get_user_by_id(user_id):
    """Obtiene un usuario por su ID único."""
    user_cache = load_user_cache()
    
    for user in user_cache.get("users", []):
        if user.get("id") == user_id:
            return user
    return None


def add_points_to_user(user_id, points: float):
    """Suma puntos a un usuario (por discord_id, youtube_id, o ID universal).
    
    Sincroniza automáticamente con BD si está disponible.
    
    Args:
        user_id: ID del usuario (discord_id, youtube_id, o ID universal)
        points: Cantidad de puntos a sumar (permite decimales)
        
    Returns:
        dict: Usuario actualizado o None si no existe
    """
    user_cache = load_user_cache()
    users = user_cache.get("users", [])
    
    user_id_str = str(user_id)
    user = None
    
    # Buscar por discord_id
    for u in users:
        if u.get("discord_id") == user_id_str:
            user = u
            break
    
    # Si no encontró por discord_id, buscar por youtube_id
    if not user:
        for u in users:
            if u.get("youtube_id") == user_id_str:
                user = u
                break
    
    # Si aún no encontró, buscar por ID universal
    if not user:
        for u in users:
            if str(u.get("id")) == user_id_str:
                user = u
                break
    
    # Si encontró el usuario, sumar puntos
    if user:
        user["puntos"] = user.get("puntos", 0) + points
        user["last_tx_at"] = datetime.now().isoformat()
        user_cache["users"] = users
        save_user_cache(user_cache)
        
        # Sincronizar con BD si está disponible
        if sync_manager:
            sync_manager.sync_user_bidirectional(user, source='local')
        elif db_manager and db_manager.is_connected:
            db_manager.add_points(user.get('id'), points, source='local')
        
        logger.info(f"✓ Se añadieron {points} puntos a {user.get('name')}")
        return user
    
    return None


def subtract_points_from_user(user_id, points: float):
    """Resta puntos a un usuario (por discord_id, youtube_id, o ID universal).
    
    Sincroniza automáticamente con BD si está disponible.
    
    Args:
        user_id: ID del usuario (discord_id, youtube_id, o ID universal)
        points: Cantidad de puntos a restar (permite decimales)
        
    Returns:
        dict: Usuario actualizado o None si no existe o no tiene suficientes puntos
    """
    user_cache = load_user_cache()
    users = user_cache.get("users", [])
    
    user_id_str = str(user_id)
    user = None
    
    # Buscar por discord_id
    for u in users:
        if u.get("discord_id") == user_id_str:
            user = u
            break
    
    # Si no encontró por discord_id, buscar por youtube_id
    if not user:
        for u in users:
            if u.get("youtube_id") == user_id_str:
                user = u
                break
    
    # Si aún no encontró, buscar por ID universal
    if not user:
        for u in users:
            if str(u.get("id")) == user_id_str:
                user = u
                break
    
    # Si encontró el usuario, verificar y restar puntos
    if user:
        current_points = user.get("puntos", 0)
        if current_points >= points:
            user["puntos"] = current_points - points
            user["last_tx_at"] = datetime.now().isoformat()
            user_cache["users"] = users
            save_user_cache(user_cache)
            
            # Sincronizar con BD si está disponible
            if sync_manager:
                sync_manager.sync_user_bidirectional(user, source='local')
            elif db_manager and db_manager.is_connected:
                db_manager.subtract_points(user.get('id'), points, source='local')
            
            logger.info(f"✓ Se restaron {points} puntos a {user.get('name')}")
            return user
        else:
            # No tiene suficientes puntos
            logger.warning(f"⚠ Usuario {user.get('name')} no tiene suficientes puntos ({current_points}/{points})")
            return None
    
    return None


def get_user_points(user_id):
    """Obtiene los puntos de un usuario (por discord_id, youtube_id, o ID universal).
    
    Args:
        user_id: ID del usuario (discord_id, youtube_id, o ID universal)
        
    Returns:
        dict: Información del usuario o None si no existe
    """
    user_cache = load_user_cache()
    users = user_cache.get("users", [])
    
    user_id_str = str(user_id)
    
    # Buscar por discord_id
    for user in users:
        if user.get("discord_id") == user_id_str:
            return user
    
    # Buscar por youtube_id
    for user in users:
        if user.get("youtube_id") == user_id_str:
            return user
    
    # Buscar por ID universal
    for user in users:
        if str(user.get("id")) == user_id_str:
            return user
    
    return None


def link_accounts(discord_id, youtube_id) -> dict:
    """Vincula una cuenta de Discord con una de YouTube
    
    Args:
        discord_id: ID de Discord (int o str)
        youtube_id: ID de YouTube (canal ID, str)
        
    Returns:
        dict: Usuario unificado o None si hubo error
    """
    user_cache = load_user_cache()
    users = user_cache.get("users", [])
    
    discord_id_str = str(discord_id)
    youtube_id_str = str(youtube_id)
    
    print(f"🔍 Buscando usuarios para vincular:")
    print(f"   Discord ID: {discord_id_str}")
    print(f"   YouTube ID: {youtube_id_str}")
    
    # Buscar usuarios
    discord_user = None
    youtube_user = None
    
    for user in users:
        # Buscar usuario de Discord (por discord_id)
        if user.get("discord_id") == discord_id_str:
            discord_user = user
            print(f"   ✓ Usuario Discord encontrado: {user.get('name')} (ID universal: {user.get('id')})")
        # Buscar usuario de YouTube (por youtube_id)
        if user.get("youtube_id") == youtube_id_str:
            youtube_user = user
            print(f"   ✓ Usuario YouTube encontrado: {user.get('name')} (ID universal: {user.get('id')})")
    
    # Si no existen ambos, no se puede vincular
    if not discord_user:
        print(f"   ❌ Usuario de Discord NO encontrado con discord_id={discord_id_str}")
        print(f"   📋 Usuarios en cache: {len(users)}")
        for u in users[:5]:  # Mostrar primeros 5 para debug
            print(f"      - {u.get('name')}: discord_id={u.get('discord_id')}, youtube_id={u.get('youtube_id')}")
    if not youtube_user:
        print(f"   ❌ Usuario de YouTube NO encontrado con youtube_id={youtube_id_str}")
    
    if not discord_user or not youtube_user:
        print(f"⚠ Error: No se encontraron ambos usuarios para vincular")
        return None
    
    # Si ya están vinculados (mismo ID universal), retornar
    if discord_user.get("id") == youtube_user.get("id"):
        print(f"⚠ Las cuentas ya están vinculadas (mismo ID universal: {discord_user.get('id')})")
        return discord_user
    
    # Sumar puntos: YouTube suma los de Discord
    puntos_discord = discord_user.get("puntos", 0)
    puntos_youtube = youtube_user.get("puntos", 0)
    youtube_user["puntos"] = puntos_youtube + puntos_discord
    
    print(f"💰 Sumando puntos: Discord({discord_user.get('name')})={puntos_discord:.1f} + YouTube({youtube_user.get('name')})={puntos_youtube:.1f} = {youtube_user['puntos']:.1f}")
    
    # Vincular información de Discord a YouTube user
    youtube_user["discord_id"] = discord_id_str
    youtube_user["avatar_discord_url"] = discord_user.get("avatar_discord_url")
    youtube_user["avatar_discord_local"] = discord_user.get("avatar_discord_local")
    
    # Agregar Discord a las plataformas
    if "platform_sources" not in youtube_user:
        youtube_user["platform_sources"] = []
    if "discord" not in youtube_user["platform_sources"]:
        youtube_user["platform_sources"].append("discord")
    
    # Eliminar el usuario de Discord (fusionarlo en YouTube)
    users.remove(discord_user)
    
    # Actualizar caché
    user_cache["users"] = users
    
    # Actualizar mapeos: discord_id ahora apunta al usuario unificado (YouTube)
    discord_to_id = user_cache.get("discord_to_id", {})
    discord_to_id[discord_id_str] = youtube_user.get("id")
    user_cache["discord_to_id"] = discord_to_id
    
    yt_to_id = user_cache.get("yt_to_id", {})
    yt_to_id[youtube_id_str] = youtube_user.get("id")
    user_cache["yt_to_id"] = yt_to_id
    
    save_user_cache(user_cache)
    
    print(f"✓ Cuentas vinculadas exitosamente: {discord_user.get('name')} (Discord) con {youtube_user.get('name')} (YouTube)")
    return youtube_user


def unlink_account(user_id, keep_platform: str) -> dict:
    """Desvincula cuentas y mantiene la plataforma especificada como principal
    
    NUEVA LÓGICA:
    - Si keep_platform='discord': mantiene Discord (puntos ahí), elimina YouTube
    - Si keep_platform='youtube': mantiene YouTube (puntos ahí), elimina Discord
    
    Args:
        user_id: ID del usuario (puede ser discord_id o youtube_id)
        keep_platform: Plataforma a mantener ('discord' o 'youtube')
        
    Returns:
        dict: Usuario actualizado o None si hubo error
    """
    user_cache = load_user_cache()
    users = user_cache.get("users", [])
    
    user_id_str = str(user_id)
    
    # Buscar usuario por discord_id o youtube_id
    user_found = None
    for user in users:
        if user.get("discord_id") == user_id_str or user.get("youtube_id") == user_id_str:
            user_found = user
            break
    
    if not user_found:
        return None
    
    # Verificar que el usuario tiene ambas plataformas vinculadas
    has_discord = user_found.get("discord_id") is not None
    has_youtube = user_found.get("youtube_id") is not None
    
    if not (has_discord and has_youtube):
        print(f"⚠ Usuario no tiene ambas plataformas vinculadas")
        return None
    
    # Desvincular según la plataforma a mantener
    if keep_platform.lower() == "discord":
        # Mantener Discord, eliminar YouTube
        print(f"✓ Manteniendo Discord ({user_found.get('discord_id')}), eliminando YouTube ({user_found.get('youtube_id')})")
        
        # Eliminar datos de YouTube
        user_found.pop("youtube_id", None)
        user_found.pop("avatar_url", None)
        user_found.pop("avatar_local", None)
        
        # Actualizar platform_sources
        if "platform_sources" in user_found and "youtube" in user_found["platform_sources"]:
            user_found["platform_sources"].remove("youtube")
        
        # El ID principal se mantiene (ya estaba vinculado)
        
    elif keep_platform.lower() == "youtube":
        # Mantener YouTube, eliminar Discord
        print(f"✓ Manteniendo YouTube ({user_found.get('youtube_id')}), eliminando Discord ({user_found.get('discord_id')})")
        
        discord_id_to_remove = user_found.get("discord_id")
        
        # Eliminar datos de Discord
        user_found.pop("discord_id", None)
        user_found.pop("avatar_discord_url", None)
        user_found.pop("avatar_discord_local", None)
        
        # Actualizar platform_sources
        if "platform_sources" in user_found and "discord" in user_found["platform_sources"]:
            user_found["platform_sources"].remove("discord")
        
        # Actualizar mapeos
        if "discord_to_id" in user_cache and discord_id_to_remove in user_cache["discord_to_id"]:
            del user_cache["discord_to_id"][discord_id_to_remove]
    
    # Guardar cambios
    user_cache["users"] = users
    save_user_cache(user_cache)
    
    platform_removed = "YouTube" if keep_platform.lower() == "discord" else "Discord"
    print(f"✓ {platform_removed} desvinculado, puntos mantenidos en {keep_platform.capitalize()}")
    return user_found


# -------------------- Gestión de baneos --------------------

def load_banned_users():
    """Carga la lista de usuarios baneados desde el archivo JSON."""
    try:
        with open(BAN_FILE, 'r') as f:
            banned_users = json.load(f)
            if not isinstance(banned_users, dict):
                print("El archivo de usuarios baneados no es un diccionario. Inicializando como vacío.")
                return {}
            return banned_users
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_banned_users(banned_users):
    """Guarda la lista de usuarios baneados en el archivo JSON."""
    with open(BAN_FILE, 'w') as f:
        json.dump(banned_users, f, indent=4)

def ban_user_by_name(name):
    """Busca al usuario por nombre en la caché y lo banea."""
    user_cache = load_user_cache()
    banned_users = load_banned_users()
    for user in user_cache.get("users", []):
        if not isinstance(user, dict):
            continue
        if user.get("name") == name:
            banned_users[str(user["id"])] = user
            save_banned_users(banned_users)
            print(f"Usuario baneado: {name} (ID: {user['id']})")
            return
    print(f"Error: El usuario '{name}' no está en la caché y no es válido para banear.")

def unban_user_by_name(name):
    """Desbanea al usuario por nombre."""
    banned_users = load_banned_users()
    for user_id, user_info in list(banned_users.items()):
        if user_info.get("name") == name:
            del banned_users[user_id]
            save_banned_users(banned_users)
            print(f"Usuario desbaneado: {name} (ID: {user_id})")
            return
    print(f"No se encontró al usuario con el nombre '{name}' en la lista de baneados.")

def show_ban_list():
    """Muestra la lista de usuarios baneados."""
    banned_users = load_banned_users()
    if banned_users:
        print("Usuarios baneados:")
        for user_id, user_info in banned_users.items():
            print(f"- {user_info['name']} (ID: {user_id})")
    else:
        print("No hay usuarios baneados.")

# -------------------- Gestión de usuarios custom --------------------

def load_custom_users():
    """Carga la lista de usuarios custom desde el archivo JSON."""
    try:
        with open(CUSTOM_FILE, 'r', encoding='utf-8') as f:
            custom_users = json.load(f)
            if not isinstance(custom_users, dict):
                print("El archivo de usuarios custom no es un diccionario. Inicializando como vacío.")
                return {}
            return custom_users
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_custom_users(custom_users):
    """Guarda la lista de usuarios custom en el archivo JSON."""
    with open(CUSTOM_FILE, 'w', encoding='utf-8') as f:
        json.dump(custom_users, f, indent=4, ensure_ascii=False)

def add_custom_user_by_name(name):
    """Busca al usuario por nombre en la caché y lo agrega como custom."""
    user_cache = load_user_cache()
    custom_users = load_custom_users()
    for user in user_cache.get("users", []):
        if not isinstance(user, dict):
            continue
        if user.get("name") == name:
            user_id = str(user["id"])
            if user_id in custom_users:
                print(f"El usuario '{name}' ya está en la lista de custom.")
                return
            custom_users[user_id] = {
                "name": user.get("name"),
                "avatar_url": user.get("avatar_url"),
                "avatar_local": user.get("avatar_local"),
                "custom_message": "¡Eres un usuario especial!"
            }
            save_custom_users(custom_users)
            print(f"Usuario custom agregado: {name} (ID: {user_id})")
            return
    print(f"Error: El usuario '{name}' no está en la caché. Primero debe escribir en el chat.")

def delete_custom_user_by_name(name):
    """Elimina al usuario custom por nombre."""
    custom_users = load_custom_users()
    for user_id, user_info in list(custom_users.items()):
        if not isinstance(user_info, dict):
            continue
        if user_info.get("name") == name:
            del custom_users[user_id]
            save_custom_users(custom_users)
            print(f"Usuario custom eliminado: {name} (ID: {user_id})")
            return
    print(f"No se encontró al usuario con el nombre '{name}' en la lista de custom.")

def show_custom_list():
    """Muestra la lista de usuarios custom."""
    custom_users = load_custom_users()
    if custom_users:
        print("Usuarios custom:")
        for user_id, user_info in custom_users.items():
            if user_id == "_info" or not isinstance(user_info, dict):
                continue
            print(f"- {user_info.get('name', 'Sin nombre')} (ID: {user_id})")
    else:
        print("No hay usuarios custom.")


# -------------------- Funciones de recuperación de emergencia --------------------

def list_backups():
    """Lista todos los respaldos disponibles del user_cache."""
    backup_dir = os.path.join(BASE_DATA_DIR, 'backups')
    if not os.path.exists(backup_dir):
        print("⚠️ No existe directorio de respaldos")
        return []
    
    backups = sorted([f for f in os.listdir(backup_dir) if f.startswith('user_cache_backup_')], reverse=True)
    if backups:
        print(f"✓ {len(backups)} respaldo(s) disponible(s):")
        for i, backup in enumerate(backups, 1):
            filepath = os.path.join(backup_dir, backup)
            size = os.path.getsize(filepath)
            print(f"  {i}. {backup} ({size} bytes)")
    else:
        print("⚠️ No hay respaldos disponibles")
    
    return backups


def restore_from_backup(backup_name=None):
    """Restaura el user_cache desde un respaldo.
    
    Args:
        backup_name: Nombre del archivo de respaldo. Si es None, usa el más reciente.
    
    Returns:
        bool: True si se restauró exitosamente, False en caso contrario.
    """
    backup_dir = os.path.join(BASE_DATA_DIR, 'backups')
    
    if not os.path.exists(backup_dir):
        print("❌ No existe directorio de respaldos")
        return False
    
    backups = sorted([f for f in os.listdir(backup_dir) if f.startswith('user_cache_backup_')], reverse=True)
    
    if not backups:
        print("❌ No hay respaldos disponibles")
        return False
    
    # Si no se especifica, usar el más reciente
    if not backup_name:
        backup_name = backups[0]
        print(f"📦 Usando respaldo más reciente: {backup_name}")
    
    backup_path = os.path.join(backup_dir, backup_name)
    
    if not os.path.exists(backup_path):
        print(f"❌ No existe el respaldo: {backup_name}")
        return False
    
    try:
        # Validar que el respaldo es un JSON válido
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        if not isinstance(backup_data, dict) or "users" not in backup_data:
            print(f"❌ El respaldo no tiene formato válido")
            return False
        
        # Crear respaldo del archivo actual antes de sobrescribir
        if os.path.exists(CACHE_FILE):
            current_backup = CACHE_FILE.replace('.json', f'_PRE_RESTORE_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            shutil.copy2(CACHE_FILE, current_backup)
            print(f"✓ Respaldo del archivo actual guardado en: {os.path.basename(current_backup)}")
        
        # Restaurar
        shutil.copy2(backup_path, CACHE_FILE)
        print(f"✅ Cache restaurado exitosamente desde: {backup_name}")
        print(f"   Usuarios restaurados: {len(backup_data.get('users', []))}")
        
        # Forzar sincronización con BD si está disponible
        if sync_manager:
            synced = sync_manager.force_sync_all_to_db()
            print(f"   ✓ {synced} usuarios sincronizados a BD")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al restaurar respaldo: {e}")
        return False


# ===== INICIALIZACIÓN AUTOMÁTICA =====
# Inicializar BD al importar el módulo
init_database()