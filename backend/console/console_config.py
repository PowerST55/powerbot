"""
Configuración centralizada de colores y consola para toda la aplicación.

Esta solución robusta y escalable permite usar colores en todos los módulos
sin necesidad de configurar manualmente cada uno.
"""

import os
import sys
from rich.console import Console
from rich.theme import Theme


def _init_windows_ansi_support() -> None:
	"""Habilita soporte ANSI en Windows para colores en consola."""
	if os.name == "nt":  # Windows
		try:
			import ctypes
			kernel32 = ctypes.windll.kernel32
			handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
			mode = ctypes.c_ulong()
			kernel32.GetConsoleMode(handle, ctypes.byref(mode))
			# Habilitar ENABLE_VIRTUAL_TERMINAL_PROCESSING
			mode.value |= 0x0004
			kernel32.SetConsoleMode(handle, mode)
		except Exception:
			# Si falla, intentar con colorama como fallback
			try:
				import colorama
				colorama.init(autoreset=True, convert=True)
			except ImportError:
				pass


# Inicializar soporte ANSI en Windows
_init_windows_ansi_support()

# Crear tema personalizado
POWERBOT_THEME = Theme({
	"info": "white",
	"success": "bold green",
	"warning": "bold yellow",
	"error": "bold red",
	"header": "bold cyan",
})

# Consola global configurada para toda la aplicación
console = Console(
	theme=POWERBOT_THEME,
	force_terminal=True,  # Forzar modo terminal (habilita colores)
	force_interactive=False,
	soft_wrap=True,
	highlight=False,  # Desactivar highlight automático para evitar procesamiento doble
	legacy_windows=False,
)


def get_console() -> Console:
	"""Obtiene la consola global configurada.
	
	Uso en cualquier módulo:
		from backend.console.console_config import get_console
		console = get_console()
		console.print("[error]Error[/error]")
	"""
	return console


__all__ = ["console", "get_console", "POWERBOT_THEME"]
