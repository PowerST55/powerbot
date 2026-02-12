"""
Gestor centralizado de consola y colores para toda la aplicación.

Este módulo configura Rich para funcionar correctamente en todas las plataformas,
especialmente Windows, y proporciona una consola global que puede ser usada
desde cualquier parte de la aplicación.

Uso:
    from backend.core import get_console
    console = get_console()
    console.print("[error]Mensaje de error[/error]")
"""

import os
import sys
import io
from rich.console import Console
from rich.theme import Theme


def _configure_windows_terminal() -> None:
	"""
	Configura la terminal de Windows para soportar colores ANSI.
	
	En Windows, los códigos ANSI no se renderizan por defecto. Esta función
	habilita el soporte usando la API de Windows.
	"""
	if os.name != "nt":
		return  # No es Windows, nada que hacer
	
	try:
		import ctypes
		
		# Obtener el handle de salida estándar
		kernel32 = ctypes.windll.kernel32
		handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE = -11
		
		# Obtener el modo actual
		mode = ctypes.c_ulong()
		if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
			return
		
		# Habilitar ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
		# Esto activa el soporte para códigos ANSI escape
		mode.value |= 0x0004
		
		if not kernel32.SetConsoleMode(handle, mode):
			return
			
	except Exception as e:
		# Si falla, intentar con colorama como alternativa
		try:
			import colorama
			colorama.init(autoreset=False, convert=True, wrap=False)
		except Exception:
			pass


def _create_configured_console() -> Console:
	"""Crea e configura la instancia global de consola."""
	
	# Primero, intentar configurar Windows
	_configure_windows_terminal()
	
	# Definir el tema personalizado con colores consistentes
	theme = Theme({
		"info": "white",
		"success": "bold green",
		"warning": "bold yellow",
		"error": "bold red",
		"header": "bold cyan",
		"debug": "dim white",
		"muted": "dim",
	})
	
	# Crear consola con configuración robusta
	# file=sys.stdout: Escribir directamente a stdout (no redirigir)
	# force_terminal=True: Forzar tratamiento como terminal (activa colores)
	# force_interactive: False para evitar problemas en pipes
	# width: Ancho fijo para evitar cambios por resize
	console_instance = Console(
		file=sys.stdout,
		theme=theme,
		force_terminal=True,
		force_interactive=False,
		no_color=False,  # Explícitamente NO desactivar colores
		highlight=False,  # No procesar markdown por defecto (evitar doble procesamiento)
		soft_wrap=True,
		width=120,
		legacy_windows=False,
	)
	
	return console_instance


# Crear la instancia global de consola una sola vez
_global_console = _create_configured_console()


def get_console() -> Console:
	"""
	Obtiene la consola global configurada.
	
	Esta consola está pre-configurada para:
	- Renderizar colores correctamente en Windows
	- Usar un tema consistente en toda la aplicación
	- Evitar procesamiento doble de marcas de color
	
	Returns:
	    Console: Instancia global de consola configurada
	
	Example:
	    from backend.core import get_console
	    console = get_console()
	    console.print("[error]Error[/error]")
	    console.print("[success]Success[/success]")
	    console.print("[warning]Warning[/warning]")
	"""
	return _global_console


# Alias corto para acceso directo
console = _global_console


__all__ = ["console", "get_console"]
