"""
Chat ID Finder Module
Gestiona la búsqueda automática y actualización del chat ID de YouTube.
"""

import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

from ..youtube_core import YouTubeClient

logger = logging.getLogger(__name__)


class ChatIdManager:
    """Gestiona la búsqueda y persistencia del chat ID activo."""

    def __init__(
        self,
        youtube_client: YouTubeClient,
        data_dir: Optional[Path] = None,
        check_interval: int = 60
    ):
        """
        Inicializa el gestor de chat ID.

        Args:
            youtube_client: Cliente de YouTube API
            data_dir: Directorio donde guardar el chat ID. 
                     Por defecto: backend/data/youtube_bot
            check_interval: Intervalo en segundos para verificar cambios (default: 60s)
        """
        self.client = youtube_client
        self.check_interval = check_interval
        
        # Configurar directorio de datos
        if data_dir is None:
            backend_dir = Path(__file__).parent.parent.parent.parent
            data_dir = backend_dir / "data" / "youtube_bot"
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.chat_file = self.data_dir / "active_chat.json"
        
        # Estado interno
        self._current_chat_id: Optional[str] = None
        self._is_monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._on_change_callback: Optional[Callable[[Optional[str], Optional[str]], None]] = None

    def get_current_chat_id(self) -> Optional[str]:
        """
        Obtiene el chat ID actual desde memoria.

        Returns:
            Chat ID actual o None
        """
        return self._current_chat_id

    def load_saved_chat_id(self) -> Optional[str]:
        """
        Carga el chat ID guardado desde el archivo.

        Returns:
            Chat ID guardado o None si no existe
        """
        try:
            if self.chat_file.exists():
                with open(self.chat_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    chat_id = data.get('live_chat_id')
                    if chat_id:
                        logger.debug("Chat ID cargado desde archivo")
                        return chat_id
        except Exception as e:
            logger.error(f"Error al cargar chat ID guardado: {e}")
        
        return None

    def save_chat_id(self, chat_id: Optional[str]) -> None:
        """
        Guarda el chat ID en el archivo.

        Args:
            chat_id: Chat ID a guardar, o None para indicar sin transmisión activa
        """
        try:
            data = {
                'live_chat_id': chat_id,
                'last_updated': datetime.utcnow().isoformat(),
                'status': 'active' if chat_id else 'inactive'
            }
            
            with open(self.chat_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            if chat_id:
                logger.debug("Chat ID guardado")
            else:
                logger.debug("Estado guardado: sin transmisión activa")
                
        except Exception as e:
            logger.error(f"Error al guardar chat ID: {e}")

    def fetch_active_chat_id(self) -> Optional[str]:
        """
        Busca el chat ID activo directamente desde YouTube API.

        Returns:
            Chat ID activo o None si no hay transmisión
        """
        try:
            chat_id = self.client.get_active_live_chat_id()
            
            if chat_id:
                logger.debug("Chat ID encontrado")
            else:
                logger.debug("No hay transmisión activa")
            
            return chat_id
            
        except Exception as e:
            logger.error(f"Error al buscar chat ID: {e}")
            return None

    def update_chat_id(self, force_fetch: bool = False) -> Optional[str]:
        """
        Actualiza el chat ID (fetch + save + notificar cambios).

        Args:
            force_fetch: Si True, busca aunque ya tengamos un chat ID

        Returns:
            Chat ID actualizado o None
        """
        # Si ya tenemos un chat ID y no forzamos fetch, usar el actual
        if self._current_chat_id and not force_fetch:
            return self._current_chat_id
        
        # Buscar chat ID activo
        new_chat_id = self.fetch_active_chat_id()
        old_chat_id = self._current_chat_id
        
        # Detectar cambio
        if new_chat_id != old_chat_id:
            logger.debug("Chat ID cambió")
            
            # Actualizar estado interno
            self._current_chat_id = new_chat_id
            
            # Guardar en archivo
            self.save_chat_id(new_chat_id)
            
            # Notificar callback
            if self._on_change_callback:
                try:
                    self._on_change_callback(old_chat_id, new_chat_id)
                except Exception as e:
                    logger.error(f"Error en callback de cambio: {e}")
        
        return new_chat_id

    def set_on_change_callback(
        self,
        callback: Callable[[Optional[str], Optional[str]], None]
    ) -> None:
        """
        Establece un callback que se ejecuta cuando cambia el chat ID.

        Args:
            callback: Función que recibe (old_chat_id, new_chat_id)
        """
        self._on_change_callback = callback

    async def start_monitoring(self) -> None:
        """
        Inicia el monitoreo automático del chat ID.
        Verifica periódicamente si hay cambios.
        """
        if self._is_monitoring:
            logger.warning("El monitoreo ya está activo")
            return
        
        self._is_monitoring = True
        
        # Hacer una primera búsqueda
        self.update_chat_id(force_fetch=True)
        
        # Iniciar tarea de monitoreo
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Monitoreo de chat ID iniciado (intervalo: {self.check_interval}s)")

    async def stop_monitoring(self) -> None:
        """Detiene el monitoreo automático."""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        logger.info("Monitoreo de chat ID detenido")

    async def _monitor_loop(self) -> None:
        """Loop de monitoreo que verifica periódicamente el chat ID."""
        while self._is_monitoring:
            try:
                await asyncio.sleep(self.check_interval)
                
                # Verificar cambios
                self.update_chat_id(force_fetch=True)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en loop de monitoreo: {e}")
                # Continuar el loop a pesar del error

    @property
    def is_monitoring(self) -> bool:
        """Indica si el monitoreo está activo."""
        return self._is_monitoring

    def get_status(self) -> dict:
        """
        Obtiene el estado actual del manager.

        Returns:
            Diccionario con el estado
        """
        return {
            'current_chat_id': self._current_chat_id,
            'is_monitoring': self._is_monitoring,
            'check_interval': self.check_interval,
            'data_file': str(self.chat_file),
            'has_active_stream': self._current_chat_id is not None
        }


# Funciones de conveniencia

def create_chat_id_manager(
    youtube_client: YouTubeClient,
    check_interval: int = 60
) -> ChatIdManager:
    """
    Crea un gestor de chat ID con configuración por defecto.

    Args:
        youtube_client: Cliente de YouTube API
        check_interval: Intervalo de verificación en segundos

    Returns:
        ChatIdManager configurado
    """
    return ChatIdManager(youtube_client, check_interval=check_interval)


if __name__ == "__main__":
    print("✓ Chat ID Finder module loaded successfully")
    print("\nUsage:")
    print("  from backend.services.youtube_api.config import ChatIdManager")
    print("  manager = ChatIdManager(youtube_client)")
    print("  await manager.start_monitoring()")
