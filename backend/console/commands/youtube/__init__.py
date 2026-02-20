"""
Comandos de YouTube para la consola interactiva.
Combina comandos generales y de configuración.
"""

from .config import YOUTUBE_CONFIG_COMMANDS
from .general import YOUTUBE_COMMANDS as YOUTUBE_GENERAL_COMMANDS

YOUTUBE_COMMANDS = {
    **YOUTUBE_GENERAL_COMMANDS,
    **YOUTUBE_CONFIG_COMMANDS,
}

__all__ = ["YOUTUBE_COMMANDS", "YOUTUBE_GENERAL_COMMANDS", "YOUTUBE_CONFIG_COMMANDS"]
