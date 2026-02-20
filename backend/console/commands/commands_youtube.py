"""
Compatibilidad con importaciones antiguas de comandos YouTube.

Módulo legado: backend.console.commands.commands_youtube
Nueva estructura: backend.console.commands.youtube
"""

from .youtube import YOUTUBE_COMMANDS
from .youtube.config import YOUTUBE_CONFIG_COMMANDS
from .youtube.general import *  # noqa: F401,F403
from .youtube.general import _get_listener, _get_youtube, _load_config, _set_listener, _set_youtube

__all__ = [
	"YOUTUBE_COMMANDS",
	"YOUTUBE_CONFIG_COMMANDS",
	"_load_config",
	"_set_youtube",
	"_get_youtube",
	"_set_listener",
	"_get_listener",
]
