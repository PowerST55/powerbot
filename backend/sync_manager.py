import json
import logging
from datetime import datetime
from typing import Dict, Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar DatabaseManager (relativo o absoluto)
try:
    from .database import DatabaseManager
except ImportError:
    try:
        from database import DatabaseManager
    except ImportError as e:
        logger.warning(f"⚠ No se pudo importar DatabaseManager: {e}")
        DatabaseManager = None


class SyncManager:
    """Gestor híbrido de sincronización entre caché JSON y BD MySQL
    
    Evita duplicaciones y desfases usando:
    - Timestamps de sincronización
    - IDs únicos para deduplicación
    - Logs de sincronización
    - Manejo de conflictos por últimas escrituras
    """
    
    def __init__(self, db_manager: DatabaseManager, cache_save_func, cache_load_func):
        """
        Args:
            db_manager: Instancia de DatabaseManager
            cache_save_func: Función para guardar caché (save_user_cache)
            cache_load_func: Función para cargar caché (load_user_cache)
        """
        self.db = db_manager
        self.save_cache = cache_save_func
        self.load_cache = cache_load_func
        self.last_full_sync = None
    
    def sync_user_bidirectional(self, user_dict: Dict, source: str = 'local') -> Dict:
        """Sincroniza un usuario en ambos sistemas de forma bidireccional
        
        Args:
            user_dict: Diccionario del usuario
            source: 'local' (JSON) o 'remote' (BD MySQL)
            
        Returns:
            Dict: Usuario sincronizado (fusionado si hay cambios en ambos lados)
        """
        youtube_id = user_dict.get('youtube_id')
        discord_id = user_dict.get('discord_id')
        
        # Identifiers válidos
        if not youtube_id and not discord_id:
            logger.warning(f"⚠ Usuario sin identificadores: {user_dict.get('name')}")
            return user_dict
        
        # Obtener versión de BD si está disponible
        user_db = None
        if self.db.is_connected:
            if youtube_id:
                user_db = self.db.get_user_by_youtube_id(youtube_id)
            elif discord_id:
                user_db = self.db.get_user_by_discord_id(discord_id)
        
        # Si no hay versión en BD, simplemente guardar en ambos lados
        if not user_db:
            self._save_both_systems(user_dict)
            return user_dict
        
        # Resolver conflictos por timestamp (gana la versión más reciente)
        merged_user = self._merge_users(user_dict, user_db, source)
        self._save_both_systems(merged_user)
        
        return merged_user
    
    def _merge_users(self, user_local: Dict, user_db: Dict, source: str) -> Dict:
        """Fusiona dos versiones de usuario, manteniendo los datos más recientes
        
        Reglas:
        - Campo actualizado más recientemente gana
        - Si ambos tienen mismo timestamp, gana la versión local (caché JSON)
        - Los puntos se suman si están desfasados
        """
        merged = user_local.copy()

        local_updated_raw = user_local.get('updated_at')
        db_updated_raw = user_db.get('updated_at')

        local_updated = self._normalize_timestamp(local_updated_raw)
        db_updated = self._normalize_timestamp(db_updated_raw)
        
        # Si la BD tiene datos más recientes, usar esos
        if db_updated > local_updated:
            logger.info(f"  → Usando datos de BD para {user_local.get('name')} "
                       f"(BD: {db_updated.isoformat()} > Local: {local_updated.isoformat()})")
            
            # Copiar campos de BD (excepto puntos que requiere lógica especial)
            for key in ['name', 'avatar_url', 'avatar_discord_url', 'is_moderator', 'is_member']:
                if key in user_db:
                    merged[key] = user_db[key]
        
        # Manejar puntos especialmente (fusión en lugar de sobrescribir)
        local_points = float(user_local.get('puntos', 0))
        db_points = float(user_db.get('puntos', 0))
        
        if local_points != db_points:
            logger.warning(f"  ⚠ Desfase de puntos en {user_local.get('name')}: "
                          f"Local={local_points}, BD={db_points}")
            # Mantener el valor más alto para evitar pérdida
            merged['puntos'] = max(local_points, db_points)
            logger.info(f"     → Manteniendo máximo: {merged['puntos']}")
        
        # Fusionar plataformas
        local_platforms = set(user_local.get('platform_sources', []))
        db_platforms = set(user_db.get('platform_sources', []))
        merged['platform_sources'] = list(local_platforms | db_platforms)
        
        return merged

    @staticmethod
    def _normalize_timestamp(value) -> datetime:
        """Convierte timestamps variados a datetime para comparaciones seguras."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except (OSError, ValueError):
                return datetime.min
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                # Intentar formato común MySQL: 'YYYY-MM-DD HH:MM:SS'
                try:
                    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return datetime.min
        return datetime.min
    
    def _save_both_systems(self, user_dict: Dict) -> bool:
        """Guarda un usuario en ambos sistemas (JSON + BD)
        
        Returns:
            bool: True si se guardó en ambos, False si solo en caché
        """
        # Siempre guardar en JSON (respaldo principal)
        user_cache = self.load_cache()
        users = user_cache.get('users', [])
        
        # Buscar y actualizar o agregar
        found = False
        for u in users:
            if u.get('youtube_id') == user_dict.get('youtube_id') or \
               (u.get('discord_id') == user_dict.get('discord_id') and user_dict.get('discord_id')):
                # Actualizar timestamp de cambio local
                user_dict['updated_at'] = datetime.now().isoformat()
                u.update(user_dict)
                found = True
                break
        
        if not found:
            user_dict['updated_at'] = datetime.now().isoformat()
            users.append(user_dict)
        
        user_cache['users'] = users
        self.save_cache(user_cache)
        
        # Intentar guardar en BD
        synced_to_db = False
        if self.db.is_connected:
            synced_to_db = self.db.sync_user_from_cache(user_dict)
        
        if synced_to_db:
            logger.debug(f"✓ {user_dict.get('name')} sincronizado a ambos sistemas")
            return True
        else:
            logger.debug(f"⚠ {user_dict.get('name')} solo en caché local (BD no disponible)")
            return False
    
    def get_user_merged(self, user_id: str, by: str = 'discord') -> Optional[Dict]:
        """Obtiene un usuario, preferentemente desde BD, fallback a caché
        
        Args:
            user_id: Discord ID o YouTube ID
            by: 'discord' o 'youtube'
            
        Returns:
            Dict: Usuario fusionado de ambas fuentes
        """
        user_db = None
        user_cache = None
        
        # Intentar obtener de BD primero (datos frescos)
        if self.db.is_connected:
            if by == 'discord':
                user_db = self.db.get_user_by_discord_id(user_id)
            else:
                user_db = self.db.get_user_by_youtube_id(user_id)
        
        # Obtener de caché
        cache_data = self.load_cache()
        for u in cache_data.get('users', []):
            if by == 'discord' and u.get('discord_id') == user_id:
                user_cache = u
                break
            elif by == 'youtube' and u.get('youtube_id') == user_id:
                user_cache = u
                break
        
        # Retornar lo que esté disponible (preferencia: BD > caché)
        if user_db:
            if user_cache:
                return self._merge_users(user_cache, user_db, 'hybrid')
            return user_db
        return user_cache
    
    def force_sync_all_to_db(self) -> int:
        """Sincroniza todos los usuarios del caché a BD
        
        Útil después de restaurar desde respaldo o cuando BD vuelve a estar disponible
        
        Returns:
            int: Número de usuarios sincronizados
        """
        if not self.db.is_connected:
            logger.warning("⚠ BD no conectada, no se puede sincronizar")
            return 0
        
        cache_data = self.load_cache()
        synced = 0
        errors = 0
        
        logger.info(f"🔄 Sincronizando {len(cache_data.get('users', []))} usuarios a BD...")
        
        for user in cache_data.get('users', []):
            if self.db.sync_user_from_cache(user):
                synced += 1
            else:
                errors += 1
        
        logger.info(f"✓ Sincronización completada: {synced} exitosos, {errors} errores")
        return synced
    
    def get_sync_status(self) -> Dict:
        """Retorna estado actual de sincronización
        
        Returns:
            Dict con información de estado
        """
        cache_data = self.load_cache()
        
        return {
            'db_connected': self.db.is_connected,
            'cache_users': len(cache_data.get('users', [])),
            'last_full_sync': self.last_full_sync,
            'timestamp': datetime.now().isoformat()
        }
    
    def cleanup_duplicates(self) -> int:
        """Limpia usuarios duplicados en caché basado en IDs únicos
        
        Returns:
            int: Número de duplicados removidos
        """
        cache_data = self.load_cache()
        users = cache_data.get('users', [])
        
        seen_yt = {}
        seen_discord = {}
        cleaned = 0
        
        for user in users[:]:  # Copiar lista para iterar mientras se modifica
            yt_id = user.get('youtube_id')
            discord_id = user.get('discord_id')
            
            # Verificar duplicados por YouTube
            if yt_id and yt_id in seen_yt:
                logger.warning(f"🗑 Removiendo duplicado YouTube: {yt_id}")
                users.remove(user)
                cleaned += 1
                continue
            if yt_id:
                seen_yt[yt_id] = user.get('name')
            
            # Verificar duplicados por Discord
            if discord_id and discord_id in seen_discord:
                logger.warning(f"🗑 Removiendo duplicado Discord: {discord_id}")
                users.remove(user)
                cleaned += 1
                continue
            if discord_id:
                seen_discord[discord_id] = user.get('name')
        
        if cleaned > 0:
            cache_data['users'] = users
            self.save_cache(cache_data)
            logger.info(f"✓ {cleaned} duplicados removidos")
        
        return cleaned
