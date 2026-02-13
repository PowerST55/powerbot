"""
Configuración del bot de Discord.
"""
from .channels import get_channels_config, ChannelsConfig
from .economy import get_economy_config, EconomyConfig

__all__ = ["get_channels_config", "ChannelsConfig", "get_economy_config", "EconomyConfig"]
