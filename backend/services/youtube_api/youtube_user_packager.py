"""
YouTube User Packager
Puente entre YouTubeListener y UserManager.
Normaliza datos de YouTube a formato universal para almacenamiento.

Responsabilidades:
- Detectar nuevo usuario o actualización
- Extraer y normalizar información (nombre, ID, tipo de usuario)
- Crear/actualizar perfil YouTube en la BD
- Gestionar avatares (delegado a avatar_manager)
"""
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from backend.managers.user_manager import (
    get_or_create_discord_user,
    get_user_by_id,
    create_user,
    create_youtube_profile,
    get_youtube_profile_by_channel_id,
    update_youtube_profile,
)
from backend.managers.avatar_manager import AvatarManager
from .youtube_types import YouTubeMessage

logger = logging.getLogger(__name__)


class UserPackager:
    """
    Empaqueta datos de YouTube en formato universal.
    Actúa como adaptador entre YouTube API y UserManager.
    """
    
    # Tipos de usuario válidos
    USER_TYPES = {
        "owner": "owner",           # Dueño del canal
        "moderator": "moderator",   # Moderador del chat
        "member": "member",         # Miembro pagado
        "regular": "regular",       # Usuario regular
    }
    
    @staticmethod
    def pack_youtube(message: YouTubeMessage) -> Dict[str, Any]:
        """
        Empaqueta un mensaje de YouTube en datos normalizados.
        
        Args:
            message: YouTubeMessage del listener
            
        Returns:
            Dict con formato normalizado:
            {
                'youtube_channel_id': str,      # ID único de YouTube
                'youtube_username': str,         # Nombre de usuario (puede cambiar)
                'user_type': str,                # 'owner', 'moderator', 'member', 'regular'
                'avatar_url_remote': str,        # URL remoto del avatar (si disponible)
                'is_privileged': bool,           # Si tiene permisos especiales
                'timestamp': datetime,           # Cuándo fue visto
            }
        """
        return {
            'youtube_channel_id': message.author_channel_id,
            'youtube_username': UserPackager._normalize_username(message.author_name),
            'user_type': UserPackager._categorize_user(message),
            'avatar_url_remote': message.profile_image_url,  # URL que viene en el mensaje
            'is_privileged': message.is_privileged(),
            'timestamp': datetime.fromisoformat(message.published_at) if message.published_at else datetime.now(),
            'raw_author_name': message.author_name,  # Nombre original sin normalizar
        }
    
    @staticmethod
    def persist_youtube_user(packed_data: Dict[str, Any], client=None) -> Tuple[int, bool]:
        """
        Persiste un usuario de YouTube a la base de datos.
        Crea o actualiza según corresponda.
        Automáticamente descarga avatar si viene en packed_data.
        
        Args:
            packed_data: Datos empaquetados de pack_youtube()
            client: Ignorado (parámetro legacy)
            
        Returns:
            Tuple: (user_id, is_new_user)
                - user_id: ID universal del usuario
                - is_new_user: True si fue creado, False si fue actualizado
        """
        channel_id = packed_data['youtube_channel_id']
        username = packed_data['youtube_username']
        user_type = packed_data['user_type']
        
        # Verificar si el perfil YouTube ya existe
        existing_profile = get_youtube_profile_by_channel_id(channel_id)
        
        if existing_profile:
            # Usuario existente: actualizar información
            user_id = existing_profile.user_id

            has_profile_changes = (
                existing_profile.youtube_username != username
                or existing_profile.user_type != user_type
            )

            if has_profile_changes:
                update_youtube_profile(
                    user_id=user_id,
                    youtube_username=username,
                    user_type=user_type,
                )
                logger.debug(
                    f"YouTube usuario actualizado: {username} "
                    f"(ID: {channel_id}, Tipo: {user_type})"
                )

            avatar_url_remote = packed_data.get('avatar_url_remote')
            has_avatar_change = bool(
                avatar_url_remote
                and avatar_url_remote != existing_profile.channel_avatar_url
            )

            if has_avatar_change:
                try:
                    UserPackager._download_and_update_avatar(user_id, channel_id, avatar_url_remote)
                except Exception as e:
                    logger.warning(f"⚠️  Error descargando avatar para {channel_id}: {e}")
            
            return (user_id, False)
        
        else:
            # Usuario nuevo: crear usuario universal + perfil YouTube
            try:
                # Crear usuario universal
                user = create_user(username)
                user_id = user.user_id
                
                # Crear perfil YouTube inicialmente sin avatar
                profile = create_youtube_profile(
                    user_id=user_id,
                    youtube_channel_id=channel_id,
                    youtube_username=username,
                    user_type=user_type,
                )
                
                logger.info(
                    f"✨ Nuevo usuario YouTube creado: {username} "
                    f"(ID universal: {user_id}, YouTube ID: {channel_id}, "
                    f"Tipo: {user_type})"
                )
                
                # Intentar descargar avatar después de crear
                if packed_data.get('avatar_url_remote'):
                    try:
                        UserPackager._download_and_update_avatar(user_id, channel_id, packed_data['avatar_url_remote'])
                    except Exception as e:
                        logger.warning(f"⚠️  Error descargando avatar para {channel_id}: {e}")
                
                return (user_id, True)
                
            except Exception as e:
                logger.error(f"❌ Error creando usuario YouTube {channel_id}: {e}")
                return (None, False)
    
    @staticmethod
    def _download_and_update_avatar(user_id: int, channel_id: str, avatar_url: str = None) -> bool:
        """
        Descarga el avatar del usuario y actualiza la BD.
        Usa AvatarManager centralizado para guardar en media/yt_avatars/
        
        Args:
            user_id: ID universal del usuario
            channel_id: ID del canal de YouTube
            avatar_url: URL del avatar (viene en el mensaje del chat)
            
        Returns:
            bool: True si se descargó exitosamente
        """
        try:
            if not avatar_url:
                logger.debug(f"No hay URL de avatar para {channel_id}")
                return False
            
            # Descargar avatar usando AvatarManager centralizado
            local_path = AvatarManager.download_avatar(
                user_id=channel_id,
                avatar_url_remote=avatar_url,
                platform="youtube"
            )
            
            if local_path:
                # Actualizar BD con ruta local
                update_youtube_profile(
                    user_id=user_id,
                    channel_avatar_url=local_path,
                )

                logger.debug(f"Avatar descargado: {channel_id} → {local_path}")
                return True
            else:
                logger.warning(f"⚠️  No se pudo descargar avatar para {channel_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error en descarga de avatar {channel_id}: {e}")
            return False
    

    
    @staticmethod
    def _normalize_username(username: str) -> str:
        """
        Normaliza nombre de usuario para almacenamiento.
        - Máximo 50 caracteres
        - Solo alfanuméricos, guiones y guiones bajos
        - Minúsculas
        
        Args:
            username: Nombre original de YouTube
            
        Returns:
            Nombre normalizado
        """
        if not username:
            return "anonymous"
        
        # Convertir a minúsculas
        normalized = username.lower()
        
        # Remover caracteres especiales, mantener solo alfanuméricos, -, _
        normalized = ''.join(c if c.isalnum() or c in '-_' else '' for c in normalized)
        
        # Límite de 50 caracteres
        normalized = normalized[:50]
        
        # Si queda vacío, usar anónimo
        return normalized or "anonymous"
    
    @staticmethod
    def _categorize_user(message: YouTubeMessage) -> str:
        """
        Categoriza el tipo de usuario según privilegios.
        Jerarquía: owner > moderator > member > regular
        
        Args:
            message: YouTubeMessage con información de permisos
            
        Returns:
            String: 'owner', 'moderator', 'member' o 'regular'
        """
        if message.is_owner:
            return "owner"
        elif message.is_moderator:
            return "moderator"
        elif message.is_sponsor:
            return "member"
        else:
            return "regular"
    
    @staticmethod
    def should_persist(message: YouTubeMessage) -> bool:
        """
        Determina si un usuario debe ser guardado en BD.
        
        Criterios:
        - Siempre guardar usuarios privilegiados (owner, moderator, member)
        - Para usuarios regulares: solo si está especialmente configurado
        
        Args:
            message: YouTubeMessage a evaluar
            
        Returns:
            bool: True si debe persistirse
        """
        # Por ahora, guardar TODOS los usuarios
        # En el futuro podría configurarse para solo privilegiados
        return True
    
    @staticmethod
    def get_user_summary(user_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene un resumen del perfil YouTube de un usuario.
        
        Args:
            user_id: ID universal del usuario
            
        Returns:
            Dict con información de perfil o None
        """
        try:
            from backend.managers.user_manager import get_youtube_profile_by_id
            
            user = get_user_by_id(user_id)
            if not user:
                return None
            
            # Obtener perfil YouTube
            # Nota: get_youtube_profile_by_id busca por profile ID, no user_id
            # Necesitaríamos una función get_youtube_profile_by_user_id en user_manager
            
            return {
                'user_id': user_id,
                'username': user.username,
                'created_at': user.created_at,
                'updated_at': user.updated_at,
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen de usuario {user_id}: {e}")
            return None
