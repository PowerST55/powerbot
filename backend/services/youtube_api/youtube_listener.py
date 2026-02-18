"""
YouTube Listener Module
Escucha mensajes del chat en vivo de YouTube y los procesa.
"""

import asyncio
import logging
import ssl
from typing import Optional, Callable, Dict, Any, List, Set
from datetime import datetime, timezone
from googleapiclient.errors import HttpError

from .youtube_core import YouTubeClient

logger = logging.getLogger(__name__)


class YouTubeMessage:
    """Representa un mensaje del chat de YouTube."""
    
    def __init__(self, data: Dict[str, Any]):
        """
        Inicializa un mensaje desde los datos de la API.
        
        Args:
            data: Datos del mensaje de la API de YouTube
        """
        snippet = data.get("snippet", {})
        author_details = data.get("authorDetails", {})
        
        self.id: str = data.get("id", "")
        self.message: str = snippet.get("textMessageDetails", {}).get("messageText", "")
        self.author_name: str = author_details.get("displayName", "Unknown")
        self.author_channel_id: str = author_details.get("channelId", "")
        self.is_moderator: bool = author_details.get("isChatModerator", False)
        self.is_owner: bool = author_details.get("isChatOwner", False)
        self.is_sponsor: bool = author_details.get("isChatSponsor", False)
        self.published_at: str = snippet.get("publishedAt", "")
        
        # Metadata adicional útil
        self.raw_data = data
    
    def __repr__(self) -> str:
        return f"YouTubeMessage(author='{self.author_name}', message='{self.message}')"
    
    def is_privileged(self) -> bool:
        """Verifica si el autor tiene privilegios (mod, owner, sponsor)."""
        return self.is_moderator or self.is_owner or self.is_sponsor


class YouTubeListener:
    """
    Escucha mensajes del chat en vivo de YouTube.
    Proporciona una base para procesar comandos y eventos.
    """
    
    def __init__(self, client: YouTubeClient, live_chat_id: str):
        """
        Inicializa el listener.
        
        Args:
            client: Cliente de YouTube autenticado
            live_chat_id: ID del chat en vivo
        """
        self.client = client
        self.live_chat_id = live_chat_id
        self.is_running = False
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        
        # Control de mensajes ya procesados
        self._processed_messages: Set[str] = set()
        self._next_page_token: Optional[str] = None
        
        # Configuración de polling
        self.poll_interval_ms = 2000  # Intervalo de polling en milisegundos
        
        # Callbacks para procesar mensajes
        self._message_handlers: List[Callable[[YouTubeMessage], None]] = []
        
        logger.info(f"YouTubeListener initialized for chat: {live_chat_id}")
    
    def add_message_handler(self, handler: Callable[[YouTubeMessage], None]) -> None:
        """
        Agrega un handler para procesar mensajes.
        
        Args:
            handler: Función que recibe un YouTubeMessage
        """
        self._message_handlers.append(handler)
        logger.debug(f"Added message handler: {handler.__name__}")
    
    def remove_message_handler(self, handler: Callable[[YouTubeMessage], None]) -> None:
        """
        Remueve un handler de mensajes.
        
        Args:
            handler: Handler a remover
        """
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)
            logger.debug(f"Removed message handler: {handler.__name__}")
    
    async def start(self) -> None:
        """Inicia el listener en background."""
        if self.is_running:
            logger.warning("Listener already running")
            return

        if not self._message_handlers:
            # Fallback: imprimir mensajes en consola si no hay handlers registrados
            self.add_message_handler(console_message_handler)
        
        self.is_running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("YouTubeListener started")
    
    async def stop(self) -> None:
        """Detiene el listener."""
        if not self.is_running:
            return
        
        self.is_running = False
        self._stop_event.set()
        
        if self._task:
            await self._task
            self._task = None
        
        logger.info("YouTubeListener stopped")
    
    async def _listen_loop(self) -> None:
        """Loop principal que obtiene mensajes continuamente."""
        logger.info("Listener loop started")
        
        # Primer fetch: solo guarda IDs existentes sin procesarlos
        # (evita procesar mensajes históricos)
        await self._fetch_and_skip_existing()
        
        while self.is_running and not self._stop_event.is_set():
            try:
                await self._fetch_and_process_messages()
                
                # Esperar el intervalo de polling
                poll_interval_seconds = self.poll_interval_ms / 1000.0
                await asyncio.sleep(poll_interval_seconds)
                
            except HttpError as e:
                logger.error(f"HTTP error fetching messages: {e}")
                # Si es un error 403/401, probablemente las credenciales expiraron
                if e.resp.status in [403, 401]:
                    logger.error("Authentication error - stopping listener")
                    break
                # Esperar un poco más en caso de error
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.exception(f"Unexpected error in listener loop: {e}")
                await asyncio.sleep(5)
        
        logger.info("Listener loop ended")
    
    async def _fetch_and_skip_existing(self) -> None:
        """Primera llamada: solo marca mensajes existentes como procesados."""
        try:
            response = await asyncio.to_thread(
                self._fetch_messages_sync
            )
            
            if response:
                items = response.get("items", [])
                for item in items:
                    msg_id = item.get("id")
                    if msg_id:
                        self._processed_messages.add(msg_id)
                
                # Guardar el page token para el siguiente fetch
                self._next_page_token = response.get("nextPageToken")
                self.poll_interval_ms = response.get("pollingIntervalMillis", 2000)
                
                logger.info(f"Skipped {len(items)} existing messages")
        
        except Exception as e:
            logger.error(f"Error skipping existing messages: {e}")
    
    async def _fetch_and_process_messages(self) -> None:
        """Obtiene y procesa nuevos mensajes."""
        try:
            response = await asyncio.to_thread(
                self._fetch_messages_sync
            )
            
            if not response:
                return
            
            items = response.get("items", [])
            new_messages = []
            
            for item in items:
                msg_id = item.get("id")
                
                # Filtrar mensajes ya procesados
                if msg_id and msg_id not in self._processed_messages:
                    self._processed_messages.add(msg_id)
                    
                    # Crear objeto mensaje
                    message = YouTubeMessage(item)
                    new_messages.append(message)
            
            # Procesar nuevos mensajes
            for message in new_messages:
                await self._process_message(message)
            
            # Actualizar configuración de polling
            self._next_page_token = response.get("nextPageToken")
            self.poll_interval_ms = response.get("pollingIntervalMillis", 2000)
            
            # Limpiar mensajes antiguos del set (mantener solo los últimos 1000)
            if len(self._processed_messages) > 1000:
                # Convertir a lista, mantener los últimos 500
                msg_list = list(self._processed_messages)
                self._processed_messages = set(msg_list[-500:])
                logger.debug("Cleaned up processed messages cache")
        
        except Exception as e:
            logger.exception(f"Error fetching and processing messages: {e}")
    
    def _fetch_messages_sync(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene mensajes de la API de forma sincrónica.
        
        Returns:
            Response de la API o None si hay error
        """
        try:
            request = self.client.service.liveChatMessages().list(
                liveChatId=self.live_chat_id,
                part="snippet,authorDetails",
                pageToken=self._next_page_token
            )
            return request.execute()
        except ssl.SSLError as e:
            logger.warning(f"SSL error in sync fetch: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in sync fetch: {e}")
            return None
    
    async def _process_message(self, message: YouTubeMessage) -> None:
        """
        Procesa un mensaje nuevo.
        
        Args:
            message: Mensaje a procesar
        """
        # Llamar a todos los handlers registrados
        for handler in self._message_handlers:
            try:
                # Si el handler es async
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.exception(f"Error in message handler {handler.__name__}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del listener.
        
        Returns:
            Diccionario con estadísticas
        """
        return {
            "is_running": self.is_running,
            "live_chat_id": self.live_chat_id,
            "poll_interval_ms": self.poll_interval_ms,
            "processed_messages_count": len(self._processed_messages),
            "registered_handlers": len(self._message_handlers),
        }


# ============================================================================
# HANDLERS DE EJEMPLO
# ============================================================================

def console_message_handler(message: YouTubeMessage) -> None:
    """
    Handler de ejemplo que imprime mensajes en consola con Rich.
    """
    try:
        from backend.core import get_console
        console = get_console()
        
        # Iconos según privilegios
        icon = ""
        if message.is_owner:
            icon = "👑"
        elif message.is_moderator:
            icon = "🛡️"
        elif message.is_sponsor:
            icon = "💎"
        
        # Estilo según privilegios
        style = "bold red" if message.is_owner else "bold yellow" if message.is_moderator else "cyan"
        
        # Imprimir con formato
        console.print(
            f"[{style}]{icon} {message.author_name}[/{style}]: {message.message}"
        )
        
    except Exception as e:
        # Fallback a print simple
        print(f"{message.author_name}: {message.message}")


async def command_processor_handler(
    message: YouTubeMessage,
    client: Optional[YouTubeClient] = None,
    live_chat_id: Optional[str] = None,
) -> None:
    """
    Handler para procesar comandos del chat.
    """
    # Verificar si el mensaje comienza con un prefijo de comando
    if message.message.startswith("!"):
        command_text = message.message[1:].strip()
        parts = command_text.split()
        
        if not parts:
            return
        
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        logger.info(f"Command detected: {command} with args: {args} from {message.author_name}")

        if not client or not live_chat_id:
            logger.warning("No client/live_chat_id provided for command processing")
            return

        try:
            from .chat_commands.general_cmds import process_general_command
            await process_general_command(command, args, message, client, live_chat_id)
        except Exception as exc:
            logger.error(f"Error procesando comando de chat: {exc}")
