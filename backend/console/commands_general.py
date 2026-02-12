"""
Comandos generales del sistema de consola.
"""
from typing import Dict, Callable, Any, Optional
import sys
import os
import subprocess
import asyncio

# Lazy loading de consola para evitar problemas de inicialización
_console = None

def _get_console():
	"""Obtiene la consola, inicializándola si es necesario."""
	global _console
	if _console is None:
		from backend.core import get_console
		_console = get_console()
	return _console


class CommandContext:
	"""Contexto de ejecución de un comando."""
	def __init__(self, args: list[str]):
		self.args = args
		self.output = []

	def print(self, message: str) -> None:
		"""Agregar mensaje al output."""
		self.output.append(("info", message))

	def error(self, message: str) -> None:
		"""Agregar error al output (rojo)."""
		self.output.append(("error", message))

	def warning(self, message: str) -> None:
		"""Agregar advertencia al output (amarillo)."""
		self.output.append(("warning", message))

	def success(self, message: str) -> None:
		"""Agregar éxito al output (verde)."""
		self.output.append(("success", message))
	
	def render(self) -> None:
		"""Renderiza todos los mensajes con colores usando la consola global."""
		console_instance = _get_console()
		for msg_type, message in self.output:
			if msg_type == "error":
				console_instance.print(f"[error][ERROR][/error] {message}")
			elif msg_type == "warning":
				console_instance.print(f"[warning][WARNING][/warning] {message}")
			elif msg_type == "success":
				console_instance.print(f"[success][SUCCESS][/success] {message}")
			else:
				console_instance.print(f"[info]{message}[/info]")





async def cmd_test(ctx: CommandContext) -> None:
	"""Comando test - imprime 'Hola mundo'"""
	ctx.print("Hola mundo")


async def cmd_colortest(ctx: CommandContext) -> None:
	"""Comando colortest - prueba todos los colores disponibles"""
	console_instance = _get_console()
	
	# Mostrar encabezado
	console_instance.print("\n" + "="*60)
	console_instance.print("[header]═══════════════════════════════════════════════════════[/header]")
	console_instance.print("[header]           PRUEBA DE COLORES - POWERBOT               [/header]")
	console_instance.print("[header]═══════════════════════════════════════════════════════[/header]")
	
	# Colores del tema personalizado
	console_instance.print("\n[header]Colores del Tema:[/header]")
	console_instance.print("[info]   ✓ INFO    [/info]  - Información general")
	console_instance.print("[success] ✓ SUCCESS  [/success] - Operación exitosa")
	console_instance.print("[warning] ⚠ WARNING  [/warning] - Advertencia")
	console_instance.print("[error]   ✗ ERROR    [/error]  - Error crítico")
	console_instance.print("[header]  HEADER   [/header] - Encabezado")
	console_instance.print("[debug]   DEBUG    [/debug]  - Información de depuración")
	console_instance.print("[muted]   MUTED    [/muted]  - Texto atenuado")
	
	# Colores estándar de Rich
	console_instance.print("\n[header]Colores Estándar de Rich:[/header]")
	colores_standard = [
		("red", "Rojo"),
		("green", "Verde"),
		("yellow", "Amarillo"),
		("blue", "Azul"),
		("magenta", "Magenta"),
		("cyan", "Cian"),
		("white", "Blanco"),
	]
	
	for color, nombre in colores_standard:
		console_instance.print(f"[bold {color}]■ {nombre:<15}[/bold {color}]", end="  ")
		console_instance.print(f"[{color}]■ {nombre} (bold)[/{color}]")
	
	# Combinaciones especiales
	console_instance.print("\n[header]Combinaciones Especiales:[/header]")
	console_instance.print("[bold green]✓ Éxito con énfasis[/bold green]")
	console_instance.print("[bold yellow]⚠ Advertencia con énfasis[/bold yellow]")
	console_instance.print("[bold red]✗ Error con énfasis[/bold red]")
	console_instance.print("[dim]Texto atenuado (dim)[/dim]")
	console_instance.print("[bold]Texto en negrita[/bold]")
	console_instance.print("[italic]Texto en itálica[/italic]")
	console_instance.print("[underline]Texto subrayado[/underline]")
	
	console_instance.print("\n[header]═══════════════════════════════════════════════════════[/header]")
	console_instance.print("[info]Fin de la prueba de colores[/info]\n")


async def cmd_help(ctx: CommandContext) -> None:
	"""Comando help - muestra los comandos disponibles"""
	ctx.print("Comandos disponibles:")
	ctx.print("  test           - Comando de prueba que imprime 'Hola mundo'")
	ctx.print("  colortest      - Prueba todos los colores disponibles")
	ctx.print("  clean          - Limpia la consola")
	ctx.print("  restart (rst)  - Reinicia el programa completamente")
	ctx.print("  help           - Muestra esta ayuda")
	ctx.print("  exit           - Salir del programa")


async def cmd_clean(ctx: CommandContext) -> None:
	"""Comando clean - limpia la consola."""
	# Limpiar la consola usando el método nativo del SO
	os.system('cls' if os.name == 'nt' else 'clear')
	ctx.print("Consola limpiada")


async def cmd_restart(ctx: CommandContext) -> None:
	"""Comando restart - cierra y reinicia el programa completamente."""
	ctx.print("Reiniciando PowerBot...")
	
	# Obtener el path del script principal
	script_dir = os.path.dirname(os.path.abspath(__file__))
	project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
	app_path = os.path.join(project_root, "backend", "app.py")
	
	try:
		# Iniciar nueva instancia
		subprocess.Popen([sys.executable, app_path])
		ctx.print("Nueva instancia iniciada")
		# Señal para salir
		await cmd_exit(ctx)
	except Exception as e:
		ctx.error(f"Error al reiniciar: {e}")


async def cmd_exit(ctx: CommandContext) -> None:
	"""Comando exit - señal para salir"""
	ctx.print("Saliendo...")


# Registro de comandos con alias
_COMMAND_FUNCTIONS: Dict[str, Callable[[CommandContext], Any]] = {
	"test": cmd_test,
	"colortest": cmd_colortest,
	"clean": cmd_clean,
	"restart": cmd_restart,
	"help": cmd_help,
	"exit": cmd_exit,
}

# Definir alias para comandos
_COMMAND_ALIASES = {
	"rst": "restart",
	"cls": "clean",
	"clear": "clean",
	"limpiar": "clean",
	"e": "exit",
	"salir": "exit",
}

# Construir el dict COMMANDS con comandos y alias
COMMANDS: Dict[str, Callable[[CommandContext], Any]] = {}
for cmd_name, cmd_func in _COMMAND_FUNCTIONS.items():
	COMMANDS[cmd_name] = cmd_func

for alias, cmd_name in _COMMAND_ALIASES.items():
	if cmd_name in _COMMAND_FUNCTIONS:
		COMMANDS[alias] = _COMMAND_FUNCTIONS[cmd_name]


async def execute_command(command_line: str) -> tuple[Any, bool]:
	"""
	Ejecuta un comando y retorna (ctx, should_exit).
	
	Args:
		command_line: Línea completa del comando
	
	Returns:
		(CommandContext, should_exit: bool)
	"""
	parts = command_line.strip().split()
	if not parts:
		return None, False

	cmd_name = parts[0].lower()
	args = parts[1:]

	if cmd_name not in COMMANDS:
		ctx = CommandContext(args)
		ctx.error(f"Comando desconocido: '{cmd_name}'. Usa 'help' para ver los comandos disponibles.")
		return ctx, False

	try:
		ctx = CommandContext(args)
		await COMMANDS[cmd_name](ctx)
		should_exit = cmd_name == "exit"
		return ctx, should_exit
	except Exception as e:
		ctx = CommandContext(args)
		ctx.error(f"Error ejecutando comando '{cmd_name}': {str(e)}")
		return ctx, False


def execute_command_sync(command_line: str) -> tuple[Any, bool]:
	"""
	Versión sincrónica de execute_command.
	Ejecuta comandos async usando asyncio.run().
	
	Args:
		command_line: Línea completa del comando
	
	Returns:
		(CommandContext, should_exit: bool)
	"""
	parts = command_line.strip().split()
	if not parts:
		return None, False

	cmd_name = parts[0].lower()
	args = parts[1:]

	if cmd_name not in COMMANDS:
		ctx = CommandContext(args)
		ctx.error(f"Comando desconocido: '{cmd_name}'. Usa 'help' para ver los comandos disponibles.")
		return ctx, False

	try:
		ctx = CommandContext(args)
		# Ejecutar el comando async usando asyncio.run()
		asyncio.run(COMMANDS[cmd_name](ctx))
		should_exit = cmd_name == "exit"
		return ctx, should_exit
	except Exception as e:
		ctx = CommandContext(args)
		ctx.error(f"Error ejecutando comando '{cmd_name}': {str(e)}")
		return ctx, False

