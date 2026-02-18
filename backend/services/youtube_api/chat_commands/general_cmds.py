"""
Comandos generales del chat de YouTube.
"""

import logging
from typing import List

from ..send_message import send_chat_message
from ..youtube_core import YouTubeClient
from ..youtube_listener import YouTubeMessage

logger = logging.getLogger(__name__)


async def process_general_command(
	command: str,
	args: List[str],
	message: YouTubeMessage,
	client: YouTubeClient,
	live_chat_id: str,
) -> bool:
	"""Procesa comandos generales. Retorna True si se manejo el comando."""
	if command == "ping":
		await send_chat_message(client, live_chat_id, "pong!")
		return True

	return False

