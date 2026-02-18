"""
Sistema de consola interactivo con prompt_toolkit integrado con asyncio.

Arquitectura elegida: Thread separado + sincrónico con patch_stdout
- Razón: prompt_toolkit necesita patch_stdout para evitar conflictos de output
- Solución: Ejecutar el loop de input en thread separado de forma sincrónica
- Ventaja: Compatible con Rich y prompt_toolkit sin conflictos
"""

import asyncio
import os
import re
import sys
import subprocess
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style as PromptStyle
from prompt_toolkit.patch_stdout import patch_stdout
from .commands import execute_command_sync, set_command_event_loop

# Lazy loading de consola para evitar problemas de inicialización
_rich_console = None

def _get_rich_console():
	"""Obtiene la consola, inicializándola si es necesario."""
	global _rich_console
	if _rich_console is None:
		from backend.core import get_console
		_rich_console = get_console()
	return _rich_console


CONSOLE_STYLE = PromptStyle.from_dict({
	"prompt": "ansiwhite bold",
	"input": "ansiblue",
})


def _is_vscode_terminal() -> bool:
	"""Detecta si se ejecuta en la terminal integrada de VS Code."""
	return os.environ.get("TERM_PROGRAM") == "vscode" or "VSCODE" in os.environ


def _is_interactive_terminal() -> bool:
	"""Detecta si stdin/stdout son interactivos."""
	return sys.stdin.isatty() and sys.stdout.isatty()


def _get_version() -> str:
	"""Lee la versión desde pyproject.toml."""
	try:
		project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
		pyproject_path = os.path.join(project_dir, "pyproject.toml")
		
		if os.path.isfile(pyproject_path):
			with open(pyproject_path, "r", encoding="utf-8") as f:
				content = f.read()
				match = re.search(r'version\s*=\s*"([^"]+)"', content)
				if match:
					return match.group(1)
	except Exception:
		pass
	
	return "0.0.0"


class ConsoleManager:
	"""Gestor de la consola interactiva."""

	def __init__(self):
		self.running = True
		self.command_count = 0
		self.version = _get_version()
		
		# Usar PromptSession siempre para evitar interferencias con el prompt
		self.session = PromptSession(style=CONSOLE_STYLE)

	def _read_input(self, prompt: str) -> str:
		"""
		Lee input con fallback según el contexto.
		- Usa PromptSession en terminals normales
		- Usa input() en VS Code
		"""
		try:
			return self.session.prompt(prompt)
		except Exception:
			# Fallback a input() si falla
			sys.stdout.write(prompt)
			sys.stdout.flush()
			return sys.stdin.readline().rstrip('\n\r')

	def run_sync(self) -> None:
		"""
		Bucle principal sincrónico de la consola.
		Este método se ejecuta en un thread separado para no bloquear asyncio.
		"""
		console = _get_rich_console()
		console.print("\n" + "=" * 50)
		console.print(f"[header]PowerBot v{self.version}[/header]")
		console.print("=" * 50)
		
		# Mantener mensaje de ayuda sin forzar salida de VS Code
		console.print("Escribe 'help' para ver los comandos disponibles\n")

		try:
			# CRÍTICO: patch_stdout() evita que el prompt se mezcle con prints
			# (mensajes de YouTube u otros hilos)
			from backend.core import set_console_output
			from prompt_toolkit.formatted_text import ANSI
			from prompt_toolkit.shortcuts import print_formatted_text

			class _PromptToolkitOutput:
				"""Salida compatible con prompt_toolkit que interpreta ANSI."""
				def write(self, data: str) -> None:
					if not data:
						return
					print_formatted_text(ANSI(data), end="")

				def flush(self) -> None:
					return

				def isatty(self) -> bool:
					return True

				@property
				def encoding(self) -> str:
					return sys.stdout.encoding or "utf-8"

			with patch_stdout():
				set_console_output(_PromptToolkitOutput())
				try:
					self._run_console_loop(console)
				finally:
					set_console_output(sys.__stdout__)

		except Exception as e:
			console.print(f"[error][ERROR] Error en la consola: {e}[/error]")
			raise
		finally:
			console.print("[success][CLOSE] Consola cerrada.[/success]")

	def _run_console_loop(self, console) -> None:
		"""Loop interno de la consola."""
		while self.running:
			try:
				# Leer comando de forma sincrónica
				command_line = self._read_input("PowerBot> ")
				
				# Ejecutar comando de forma sincrónica
				ctx, should_exit = execute_command_sync(command_line)
				
				if ctx:
					ctx.render()
				
				if should_exit:
					self.running = False

			except (KeyboardInterrupt, EOFError):
				console.print("\n[success][EXIT] Hasta luego![/success]")
				self.running = False
				break


async def start_console() -> None:
	"""Punto de entrada de la consola."""
	console = ConsoleManager()
	
	# Ejecutar el loop de la consola en un thread separado
	# Esto evita bloquear el event loop de asyncio
	loop = asyncio.get_event_loop()
	set_command_event_loop(loop)
	await loop.run_in_executor(None, console.run_sync)


if __name__ == "__main__":
	asyncio.run(start_console())
