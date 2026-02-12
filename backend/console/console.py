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
from .commands_general import execute_command_sync

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
		
		# Configurar PromptSession según el contexto
		# En VS Code, usar input() simple es más confiable
		if _is_vscode_terminal():
			self.session = None  # Usaremos input() en lugar de PromptSession
		else:
			self.session = PromptSession(style=CONSOLE_STYLE)

	def _read_input(self, prompt: str) -> str:
		"""
		Lee input con fallback según el contexto.
		- Usa PromptSession en terminals normales
		- Usa input() en VS Code
		"""
		if self.session is not None:
			try:
				return self.session.prompt(prompt)
			except Exception:
				# Fallback a input() si falla
				sys.stdout.write(prompt)
				sys.stdout.flush()
				return sys.stdin.readline().rstrip('\n\r')
		else:
			# VS Code: usar input() directamente con flush explícito
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
		
		# Advertencia si está en VS Code
		if _is_vscode_terminal():
			console.print("\n[warning]⚠ NOTA: Terminal integrada de VS Code detectada[/warning]")
			console.print("[info]Se recomienda usar: Ctrl+` → Click dropdown → 'Select Default Profile'[/info]")
			console.print("[info]O ejecutar desde PowerShell/CMD directo en tu PC[/info]\n")
		
		console.print("Escribe 'help' para ver los comandos disponibles\n")

		try:
			# CRÍTICO: patch_stdout() solo si usamos PromptSession
			# En VS Code, input() funciona mejor sin patch_stdout()
			if self.session is not None:
				# Usar PromptSession con patch_stdout()
				with patch_stdout():
					self._run_console_loop(console)
			else:
				# Usar input() sin patch_stdout()
				self._run_console_loop(console)

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
	await loop.run_in_executor(None, console.run_sync)


if __name__ == "__main__":
	asyncio.run(start_console())
