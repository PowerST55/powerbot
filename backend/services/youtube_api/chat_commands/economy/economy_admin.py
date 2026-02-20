"""
Comandos administrativos de economía para chat de YouTube.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from backend.database import get_connection
from backend.managers import economy_manager
from backend.managers.economy_manager import get_user_balance_by_id
from backend.managers.user_lookup_manager import (
	UserLookupResult,
	find_user_by_global_id,
	find_user_by_youtube_channel_id,
	find_user_by_youtube_username,
)

from ...send_message import send_chat_message
from ...youtube_core import YouTubeClient
from ...youtube_listener import YouTubeMessage

logger = logging.getLogger(__name__)


ADMIN_ECONOMY_COMMAND_ALIASES = {"aps", "rps", "pewset"}


async def process_admin_economy_command(
	command: str,
	args: List[str],
	message: YouTubeMessage,
	client: YouTubeClient,
	live_chat_id: str,
) -> bool:
	"""Procesa comandos administrativos de economía. Retorna True si se manejó."""
	if command not in ADMIN_ECONOMY_COMMAND_ALIASES:
		return False

	if not (message.is_moderator or message.is_owner):
		await send_chat_message(
			client,
			live_chat_id,
			"Solo moderadores pueden usar este comando.",
		)
		return True

	if len(args) < 2:
		await send_chat_message(
			client,
			live_chat_id,
			f"Uso: !{command} <@usuario o id> <cantidad{_amount_hint_for_command(command)}>",
		)
		return True

	amount_token = args[-1]
	query = " ".join(args[:-1]).strip()

	if not query:
		await send_chat_message(
			client,
			live_chat_id,
			f"Uso: !{command} <@usuario o id> <cantidad{_amount_hint_for_command(command)}>",
		)
		return True

	lookup = _resolve_lookup(query)
	if not lookup:
		await send_chat_message(client, live_chat_id, f"No encontré al usuario '{query}'.")
		return True

	balance = get_user_balance_by_id(lookup.user_id)
	current_points = int(balance.get("global_points", 0)) if balance else 0

	if command == "aps":
		amount = _parse_positive_int(amount_token)
		if amount is None:
			await send_chat_message(client, live_chat_id, "La cantidad debe ser un entero mayor a 0.")
			return True

		new_points = _apply_balance_delta(lookup.user_id, amount, "admin_add_points", message)
		await send_chat_message(
			client,
			live_chat_id,
			f"✅ +{amount} puntos a {_format_user_label(lookup)}. Nuevo balance: {new_points}.",
		)
		return True

	if command == "rps":
		if amount_token.strip().lower() == "all":
			if current_points <= 0:
				await send_chat_message(client, live_chat_id, "El usuario no tiene puntos para remover.")
				return True
			amount = current_points
		else:
			amount = _parse_positive_int(amount_token)
			if amount is None:
				await send_chat_message(client, live_chat_id, "La cantidad debe ser un entero mayor a 0 o 'all'.")
				return True

		if amount > current_points:
			amount = current_points

		if amount <= 0:
			await send_chat_message(client, live_chat_id, "El usuario no tiene puntos para remover.")
			return True

		new_points = _apply_balance_delta(lookup.user_id, -amount, "admin_remove_points", message)
		await send_chat_message(
			client,
			live_chat_id,
			f"⚠️ -{amount} puntos a {_format_user_label(lookup)}. Nuevo balance: {new_points}.",
		)
		return True

	if command == "pewset":
		amount = _parse_non_negative_int(amount_token)
		if amount is None:
			await send_chat_message(client, live_chat_id, "La cantidad debe ser un entero mayor o igual a 0.")
			return True

		delta = amount - current_points
		new_points = _apply_balance_delta(lookup.user_id, delta, "admin_set_points", message)
		await send_chat_message(
			client,
			live_chat_id,
			f"🎯 Balance fijado para {_format_user_label(lookup)} en {new_points} puntos.",
		)
		return True

	return False


def _resolve_lookup(query: str) -> Optional[UserLookupResult]:
	raw = str(query).strip()
	if not raw:
		return None

	if raw.isdigit():
		by_id = find_user_by_global_id(int(raw))
		if by_id:
			return by_id

	candidate = raw.lstrip("@")
	if not candidate:
		return None

	by_youtube_username = find_user_by_youtube_username(candidate)
	if by_youtube_username:
		return by_youtube_username

	if candidate.startswith("UC"):
		by_channel = find_user_by_youtube_channel_id(candidate)
		if by_channel:
			return by_channel

	conn = get_connection()
	try:
		row = conn.execute(
			"""
			SELECT user_id
			FROM discord_profile
			WHERE LOWER(discord_username) = LOWER(?)
			LIMIT 1
			""",
			(candidate,),
		).fetchone()
		if row:
			return find_user_by_global_id(int(row["user_id"]))
	finally:
		conn.close()

	return None


def _parse_positive_int(raw: str) -> Optional[int]:
	value = str(raw).strip()
	if not value.isdigit():
		return None
	amount = int(value)
	return amount if amount > 0 else None


def _parse_non_negative_int(raw: str) -> Optional[int]:
	value = str(raw).strip()
	if not value.isdigit():
		return None
	amount = int(value)
	return amount if amount >= 0 else None


def _amount_hint_for_command(command: str) -> str:
	return " o all" if command == "rps" else ""


def _format_user_label(lookup: UserLookupResult) -> str:
	if lookup.discord_profile and lookup.discord_profile.discord_username:
		return f"@{lookup.discord_profile.discord_username} (id {lookup.user_id})"
	if lookup.youtube_profile and lookup.youtube_profile.youtube_username:
		return f"@{lookup.youtube_profile.youtube_username} (id {lookup.user_id})"
	return f"id {lookup.user_id}"


def _apply_balance_delta(user_id: int, delta: int, reason: str, message: YouTubeMessage) -> int:
	conn = get_connection()
	try:
		economy_manager._ensure_wallet_tables(conn)
		conn.execute("BEGIN IMMEDIATE")

		now_iso = datetime.utcnow().isoformat()
		conn.execute(
			"INSERT INTO wallets (user_id, balance, created_at, updated_at) VALUES (?, 0, ?, ?) "
			"ON CONFLICT(user_id) DO NOTHING",
			(user_id, now_iso, now_iso),
		)

		conn.execute(
			"UPDATE wallets SET balance = balance + ?, updated_at = ? WHERE user_id = ?",
			(delta, now_iso, user_id),
		)

		conn.execute(
			"""
			INSERT INTO wallet_ledger (user_id, amount, reason, platform, guild_id, channel_id, source_id, created_at)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?)
			""",
			(
				user_id,
				delta,
				reason,
				"youtube",
				None,
				None,
				f"yt_admin:{message.id}:{reason}",
				now_iso,
			),
		)

		row = conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
		conn.commit()
		return int(row["balance"]) if row else 0
	finally:
		conn.close()
