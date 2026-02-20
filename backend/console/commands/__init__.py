"""
Módulo de comandos de consola para PowerBot.
"""

from .commands_general import execute_command_sync, set_command_event_loop, COMMANDS
from .youtube import YOUTUBE_COMMANDS

__all__ = ["execute_command_sync", "set_command_event_loop", "COMMANDS", "YOUTUBE_COMMANDS"]
