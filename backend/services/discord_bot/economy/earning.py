"""
Earning logic for points by chat activity.
"""
from __future__ import annotations

from typing import Dict, Optional

from backend.managers.economy_manager import award_message_points
from backend.services.discord_bot.config.economy import get_economy_config


def process_message_earning(
	discord_id: str,
	guild_id: int,
	channel_id: int,
) -> Dict[str, Optional[int]]:
	"""
	Processes a message and awards points if eligible.
	"""
	config = get_economy_config(guild_id)

	if not config.is_earning_channel(channel_id):
		return {
			"awarded": 0,
			"points_added": 0,
			"global_points": None,
		}

	amount = config.get_points_amount()
	interval = config.get_points_interval()

	return award_message_points(
		discord_id=str(discord_id),
		guild_id=guild_id,
		amount=amount,
		interval_seconds=interval,
	)
