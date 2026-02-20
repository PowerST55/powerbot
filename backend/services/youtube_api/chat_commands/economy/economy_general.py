"""
Comandos de economía del chat de YouTube.
"""

import logging
from typing import List

from backend.managers.economy_manager import get_user_balance_by_id, get_user_balance_by_youtube_id
from backend.managers.user_lookup_manager import (
	find_user_by_global_id,
	find_user_by_youtube_channel_id,
	find_user_by_youtube_username,
)
from ...config.economy import get_youtube_economy_config
from ...send_message import send_chat_message
from ...youtube_core import YouTubeClient
from ...youtube_listener import YouTubeMessage

logger = logging.getLogger(__name__)


ECONOMY_COMMAND_ALIASES = {"puntos", "pews", "points", "balance", "pew"}


def _format_points(points: int) -> str:
	config = get_youtube_economy_config()
	currency_name = config.get_currency_name()
	currency_symbol = config.get_currency_symbol()
	return f"{points} {currency_symbol} {currency_name}".strip()


async def process_economy_command(
	command: str,
	args: List[str],
	message: YouTubeMessage,
	client: YouTubeClient,
	live_chat_id: str,
) -> bool:
	"""Procesa comandos de economía. Retorna True si se manejó el comando."""
	if command not in ECONOMY_COMMAND_ALIASES:
		return False

	# Caso 1: !puntos -> self (autor del mensaje)
	if not args:
		lookup = find_user_by_youtube_channel_id(message.author_channel_id)
		if not lookup:
			await send_chat_message(
				client,
				live_chat_id,
				f"No encontré usuario vinculado para {message.author_name}.",
			)
			return True

		balance = get_user_balance_by_youtube_id(message.author_channel_id)
		points = balance.get("global_points", 0) if balance else 0
		await send_chat_message(
			client,
			live_chat_id,
			f"{message.author_name} tiene {_format_points(points)}.",
		)
		return True

	query = " ".join(args).strip()
	if not query:
		await send_chat_message(client, live_chat_id, "Uso: !puntos, !puntos <id> o !puntos <usuario>")
		return True

	# Caso 2: !puntos <id_universal>
	if query.isdigit():
		lookup = find_user_by_global_id(int(query))
		if not lookup:
			await send_chat_message(client, live_chat_id, f"No existe usuario con id {query}.")
			return True

		balance = get_user_balance_by_id(lookup.user_id)
		points = balance.get("global_points", 0) if balance else 0

		if lookup.discord_profile and lookup.discord_profile.discord_username:
			await send_chat_message(
				client,
				live_chat_id,
				f"El usuario @{lookup.discord_profile.discord_username} (discord) tiene {_format_points(points)}.",
			)
		elif lookup.youtube_profile and lookup.youtube_profile.youtube_username:
			await send_chat_message(
				client,
				live_chat_id,
				f"El usuario @{lookup.youtube_profile.youtube_username} tiene {_format_points(points)}.",
			)
		else:
			await send_chat_message(
				client,
				live_chat_id,
				f"El usuario con id {lookup.user_id} tiene {_format_points(points)}.",
			)
		return True

	# Caso 3: !puntos <@usuario> o !puntos <usuario>
	lookup = find_user_by_youtube_username(query)
	if not lookup and query.startswith("UC"):
		lookup = find_user_by_youtube_channel_id(query)

	if not lookup:
		await send_chat_message(client, live_chat_id, f"No encontré al usuario '{query}'.")
		return True

	balance = get_user_balance_by_id(lookup.user_id)
	points = balance.get("global_points", 0) if balance else 0
	username = lookup.youtube_profile.youtube_username if lookup.youtube_profile else lookup.display_name
	await send_chat_message(
		client,
		live_chat_id,
		f"El usuario @{username} tiene {_format_points(points)}.",
	)
	return True

