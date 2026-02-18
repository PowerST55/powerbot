"""
Helpers para enviar mensajes al chat de YouTube.
"""

import asyncio
import logging
import ssl
import time

from .youtube_core import YouTubeClient

logger = logging.getLogger(__name__)


def send_chat_message_sync(
	client: YouTubeClient,
	live_chat_id: str,
	message: str,
	retries: int = 2,
	base_delay: float = 0.6,
) -> bool:
	"""Envia un mensaje al chat de forma sincrona con reintentos."""
	for attempt in range(retries + 1):
		try:
			response = client.send_message(live_chat_id, message)
			if isinstance(response, dict) and response.get("ssl_error"):
				logger.warning("SSL al enviar; no se pudo confirmar, continuando")
				return True
			if not response:
				logger.warning("No se pudo confirmar el envio del mensaje")
				return False
			return True
		except ssl.SSLError as exc:
			# Errores SSL intermitentes: reintentar sin bloquear demasiado
			if attempt >= retries:
				logger.warning(f"Error SSL enviando mensaje: {exc}")
				return False
			time.sleep(base_delay * (attempt + 1))
		except Exception as exc:
			logger.error(f"Error enviando mensaje al chat: {exc}")
			return False


async def send_chat_message(
	client: YouTubeClient,
	live_chat_id: str,
	message: str,
) -> bool:
	"""Envia un mensaje al chat usando un thread para la llamada sync."""
	return await asyncio.to_thread(send_chat_message_sync, client, live_chat_id, message)

