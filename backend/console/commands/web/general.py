"""
Comandos de consola para controlar el servidor web.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from backend.services.web.config.toggle_on_off import create_web_toggle_manager

_console = None
_web_process: Optional[subprocess.Popen] = None
_web_config_manager = None


def _get_console():
	"""Obtiene la consola global."""
	global _console
	if _console is None:
		from backend.core import get_console
		_console = get_console()
	return _console


def _get_config_manager():
	"""Obtiene el manager de configuración del web toggle."""
	global _web_config_manager
	if _web_config_manager is None:
		_web_config_manager = create_web_toggle_manager()
	return _web_config_manager


def _is_web_running() -> bool:
	"""Verifica si el proceso web lanzado por la consola sigue activo."""
	global _web_process
	return _web_process is not None and _web_process.poll() is None


def _get_access_urls() -> tuple[str, str, str]:
	"""Devuelve bind host/puerto y URL recomendada para navegador."""
	host = os.getenv("WEB_HOST", "0.0.0.0")
	port = os.getenv("WEB_PORT", "19131")
	browser_host = "127.0.0.1" if host == "0.0.0.0" else host
	browser_url = f"http://{browser_host}:{port}"
	return host, port, browser_url if browser_url else f"http://127.0.0.1:{port}"


async def _start_web_process() -> tuple[bool, str]:
	"""Inicia el servidor web en un subproceso."""
	global _web_process

	if _is_web_running():
		return True, "El servidor web ya está encendido"

	project_root = Path(__file__).resolve().parents[4]
	env = os.environ.copy()
	pythonpath = env.get("PYTHONPATH", "")
	root_str = str(project_root)
	if root_str not in pythonpath:
		env["PYTHONPATH"] = f"{root_str}{os.pathsep}{pythonpath}" if pythonpath else root_str

	try:
		_web_process = subprocess.Popen(
			[sys.executable, "-m", "backend.services.web.web_core"],
			cwd=str(project_root),
			env=env,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
		)
		await asyncio.sleep(0.8)
		if _web_process.poll() is not None:
			code = _web_process.returncode
			_web_process = None
			return False, f"No se pudo iniciar el servidor web (exit code: {code})"
		return True, "Servidor web encendido"
	except Exception as exc:
		_web_process = None
		return False, f"Error iniciando servidor web: {exc}"


def _stop_web_process() -> tuple[bool, str]:
	"""Detiene el servidor web si está activo."""
	global _web_process

	if not _is_web_running():
		_web_process = None
		return True, "El servidor web ya está apagado"

	try:
		_web_process.terminate()
		_web_process.wait(timeout=5)
	except Exception:
		try:
			_web_process.kill()
		except Exception:
			pass
	finally:
		_web_process = None

	return True, "Servidor web apagado"


async def cmd_web(ctx: Any) -> None:
	"""
	Comando principal para encender/apagar el servidor web.

	Uso:
	  web            -> alterna on/off
	  web on         -> enciende
	  web off        -> apaga
	  web status     -> muestra estado
	  web help       -> ayuda
	"""
	manager = _get_config_manager()
	action = ctx.args[0].lower() if ctx.args else "toggle"

	if action in {"help", "-h", "--help"}:
		ctx.print("Comandos web disponibles:")
		ctx.print("  web             - Alterna ON/OFF")
		ctx.print("  web on          - Enciende el servidor web")
		ctx.print("  web off         - Apaga el servidor web")
		ctx.print("  web status      - Estado actual del servidor web")
		return

	if action == "status":
		is_running = _is_web_running()
		cfg = manager.get_status()
		host, port, browser_url = _get_access_urls()
		ctx.print("Estado del servidor web:")
		ctx.print(f"  • Proceso: {'ON' if is_running else 'OFF'}")
		ctx.print(f"  • Config persistida: {'ON' if cfg.get('web_enabled') else 'OFF'}")
		ctx.print(f"  • Bind: http://{host}:{port}")
		ctx.print(f"  • Abrir en navegador: {browser_url}")
		ctx.print("  • Nota: 0.0.0.0 no se usa directamente en navegador")
		ctx.print(f"  • Archivo config: {cfg.get('config_file')}")
		return

	if action in {"toggle", "switch"}:
		if _is_web_running() or manager.is_enabled():
			action = "off"
		else:
			action = "on"

	if action in {"on", "start", "1", "true"}:
		ok, message = await _start_web_process()
		if ok:
			manager.set_enabled(True)
			ctx.success(message)
			_, _, browser_url = _get_access_urls()
			ctx.print(f"Abre: {browser_url}")
			ctx.print("(No uses http://0.0.0.0 en el navegador)")
		else:
			manager.set_enabled(False)
			ctx.error(message)
		return

	if action in {"off", "stop", "0", "false"}:
		ok, message = _stop_web_process()
		manager.set_enabled(False)
		if ok:
			ctx.success(message)
		else:
			ctx.error(message)
		return

	ctx.error(f"Subcomando desconocido: 'web {action}'")
	ctx.print("Usa 'web help' para ver comandos disponibles")


WEB_COMMANDS = {
	"web": cmd_web,
	"on": cmd_web,
	"off": cmd_web,
	"status": cmd_web,
	"help": cmd_web,
}

