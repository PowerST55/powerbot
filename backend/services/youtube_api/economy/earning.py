"""
Earning logic for points by YouTube chat activity.
"""
from __future__ import annotations

from typing import Dict, Optional

from backend.managers.economy_manager import award_youtube_message_points
from backend.services.youtube_api.config.economy import get_youtube_economy_config


def process_message_earning(
	youtube_channel_id: str,
	live_chat_id: str,
	source_id: str | None = None,
) -> Dict[str, Optional[int]]:
	"""
	Procesa un mensaje de YouTube y otorga puntos si corresponde por cooldown.
	"""
	config = get_youtube_economy_config()
	if not config.is_earning_enabled():
		return {
			"awarded": 0,
			"points_added": 0,
			"global_points": None,
		}

	amount = config.get_points_amount()
	interval = config.get_points_interval()

	return award_youtube_message_points(
		youtube_channel_id=str(youtube_channel_id),
		chat_id=str(live_chat_id),
		amount=amount,
		interval_seconds=interval,
		source_id=source_id,
	)

