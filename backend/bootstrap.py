"""
Bootstrap de PowerBot - Instalación de dependencias y configuración inicial.

Este módulo se encarga de:
1. Leer y parsear el pyproject.toml
2. Verificar e instalar dependencias faltantes
3. Manejar entornos virtuales
4. Proporcionar logging centralizado con colores
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass


# Lazy loading de consola para evitar problemas durante importación
_console = None
HAS_RICH = None

def _get_console():
	"""Obtiene la consola, inicializándola si es necesario."""
	global _console, HAS_RICH
	if _console is None:
		try:
			from backend.core import get_console as _get_console_impl
			_console = _get_console_impl()
			HAS_RICH = True
		except ImportError:
			HAS_RICH = False
			class SimpleConsole:
				def print(self, msg):
					print(msg)
			_console = SimpleConsole()
	return _console


@dataclass
class BootstrapConfig:
	"""Configuración del bootstrap."""
	project_root: Path
	python_version: Tuple[int, int]
	is_in_venv: bool
	verbose: bool = False


class BootstrapLogger:
	"""Logger personalizado que usa la consola centralizada."""
	
	def __init__(self, verbose: bool = False):
		self.verbose = verbose
		self.logger = logging.getLogger("powerbot.bootstrap")
		self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
		
	def debug(self, msg: str) -> None:
		"""Mensaje de depuración."""
		if self.verbose:
			console_instance = _get_console()
			if HAS_RICH is None:
				HAS_RICH_VALUE = True  # Asumir que sí después de get_console
			else:
				HAS_RICH_VALUE = HAS_RICH
			
			if HAS_RICH_VALUE:
				console_instance.print(f"[debug][DEBUG][/debug] {msg}")
			else:
				print(f"[DEBUG] {msg}")
	
	def info(self, msg: str) -> None:
		"""Mensaje de información."""
		console_instance = _get_console()
		if HAS_RICH is not False:
			console_instance.print(f"[info]{msg}[/info]")
		else:
			print(msg)
	
	def success(self, msg: str) -> None:
		"""Mensaje de éxito."""
		console_instance = _get_console()
		if HAS_RICH is not False:
			console_instance.print(f"[success]✓ {msg}[/success]")
		else:
			print(f"✓ {msg}")
	
	def warning(self, msg: str) -> None:
		"""Mensaje de advertencia."""
		console_instance = _get_console()
		if HAS_RICH is not False:
			console_instance.print(f"[warning]⚠ {msg}[/warning]")
		else:
			print(f"⚠ {msg}")
	
	def error(self, msg: str) -> None:
		"""Mensaje de error."""
		console_instance = _get_console()
		if HAS_RICH is not False:
			console_instance.print(f"[error]✗ {msg}[/error]")
		else:
			print(f"✗ {msg}")


def _get_python_version() -> Tuple[int, int]:
	"""Obtiene la versión de Python actual."""
	return (sys.version_info.major, sys.version_info.minor)


def _verify_python_version(logger: BootstrapLogger) -> bool:
	"""Verifica que Python sea 3.10 o superior."""
	major, minor = _get_python_version()
	if major < 3 or (major == 3 and minor < 10):
		logger.error(f"Se requiere Python 3.10+, tienes Python {major}.{minor}")
		return False
	logger.debug(f"Python {major}.{minor} ✓")
	return True


def _is_in_venv() -> bool:
	"""Detecta si se está ejecutando dentro de un entorno virtual."""
	return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _find_venv_python(venv_dir: str) -> Optional[str]:
	"""Encuentra el ejecutable de Python en un venv."""
	if os.name == "nt":  # Windows
		candidate = Path(venv_dir) / "Scripts" / "python.exe"
	else:  # Unix-like
		candidate = Path(venv_dir) / "bin" / "python"
	
	return str(candidate) if candidate.is_file() else None


def _reexec_in_venv(logger: Optional[BootstrapLogger] = None, venv_dir: str = ".venv") -> None:
	"""
	Reejecutar el script en el venv si no estamos ya dentro.
	
	Args:
		logger: Logger opcional para mensajes de debug
		venv_dir: Directorio del venv (por defecto .venv)
	"""
	if _is_in_venv():
		if logger:
			logger.debug("Ya estamos dentro de un venv")
		return
	
	script_dir = Path(__file__).parent
	project_dir = script_dir.parent
	
	candidates = [
		Path(venv_dir),
		project_dir / venv_dir,
		script_dir / venv_dir,
	]
	
	if logger:
		logger.debug(f"Buscando venv en: {candidates}")
	
	for candidate_dir in candidates:
		venv_python = _find_venv_python(str(candidate_dir))
		if venv_python:
			if logger:
				logger.info(f"Reejecutando en venv: {venv_python}")
			os.execv(venv_python, [venv_python, *sys.argv])
	
	if logger:
		logger.warning("No se encontró venv, continuando con el intérprete actual")


def _read_pyproject_toml(project_root: Path) -> dict:
	"""Lee y parsea el pyproject.toml."""
	pyproject_path = project_root / "pyproject.toml"
	
	if not pyproject_path.exists():
		raise FileNotFoundError(f"No encontrado: {pyproject_path}")
	
	try:
		import tomllib
	except ImportError:
		try:
			import tomli as tomllib  # type: ignore
		except ImportError:
			raise ImportError(
				"Se requiere tomli para Python < 3.11. "
				"Instálalo con: pip install tomli"
			)
	
	with open(pyproject_path, "rb") as f:
		return tomllib.load(f)


def _extract_dependencies(pyproject: dict) -> List[str]:
	"""Extrae las dependencias del pyproject.toml."""
	dependencies = pyproject.get("project", {}).get("dependencies", [])
	
	if not dependencies:
		raise ValueError("No se encontraron dependencias en [project] dependencies")
	
	return dependencies


def _normalize_package_name(requirement: str) -> str:
	"""
	Normaliza un requirement a nombre de paquete importable.
	
	Ejemplos:
		'prompt-toolkit>=3.0.36' -> 'prompt_toolkit'
		'python-dotenv' -> 'dotenv'
		'Pillow' -> 'PIL'
		'pyyaml' -> 'yaml'
		'google-auth' -> 'google.auth'
	"""
	# Eliminar versiones, extras, etc.
	name = requirement.split(";")[0].split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
	
	# Mapeos especiales conocidos
	special_mappings = {
		"pillow": "PIL",
		"pyyaml": "yaml",
		"pydantic-core": "pydantic",
		"setuptools": "setuptools",
		"wheel": "wheel",
		"google-auth": "google.auth",
		"google-auth-oauthlib": "google_auth_oauthlib",
		"google-api-python-client": "googleapiclient",
		"python-dotenv": "dotenv",
		"discord.py": "discord",
	}
	
	name_lower = name.lower()
	if name_lower in special_mappings:
		return special_mappings[name_lower]
	
	# Reemplazar guiones con guiones bajos
	return name.replace("-", "_")


def _is_package_installed(package_name: str) -> bool:
	"""Verifica si un paquete está instalado."""
	try:
		__import__(package_name)
		return True
	except ImportError:
		return False


def _find_missing_packages(dependencies: List[str], logger: BootstrapLogger) -> List[str]:
	"""Encontrar qué paquetes no están instalados."""
	missing = []
	
	for requirement in dependencies:
		package_name = _normalize_package_name(requirement)
		if _is_package_installed(package_name):
			logger.debug(f"  ✓ {requirement}")
		else:
			logger.debug(f"  ✗ {requirement}")
			missing.append(requirement)
	
	return missing


def _install_packages(packages: List[str], logger: BootstrapLogger) -> bool:
	"""Instala los paquetes especificados."""
	if not packages:
		return True
	
	logger.info(f"Instalando {len(packages)} paquete(s)...")
	
	all_success = True
	for package in packages:
		try:
			logger.debug(f"  Instalando: {package}")
			subprocess.check_call(
				[sys.executable, "-m", "pip", "install", "-q", package],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
			)
			logger.debug(f"    ✓ {package}")
		except subprocess.CalledProcessError as e:
			logger.warning(f"  Reintentando {package} con detalle...")
			try:
				subprocess.check_call(
					[sys.executable, "-m", "pip", "install", package]
				)
				logger.debug(f"    ✓ {package} (en reintentos)")
			except subprocess.CalledProcessError as e2:
				logger.error(f"  Falló al instalar {package}: {e2}")
				all_success = False
	
	return all_success


def bootstrap(verbose: bool = False) -> bool:
	"""
	Ejecuta el bootstrap de la aplicación.
	
	Retorna:
		bool: True si el bootstrap fue exitoso, False en caso contrario.
	"""
	logger = BootstrapLogger(verbose=verbose)
	
	try:
		# 1. Verificar versión de Python
		logger.info("Verificando entorno...")
		if not _verify_python_version(logger):
			return False
		
		# 2. Detectar venv
		is_in_venv = _is_in_venv()
		logger.debug(f"¿En venv?: {is_in_venv}")
		
		# 3. Obtener directorios
		script_dir = Path(__file__).parent
		project_root = script_dir.parent
		logger.debug(f"Directorio de proyecto: {project_root}")
		
		# 4. Leer pyproject.toml
		logger.info("Leyendo configuración del proyecto...")
		try:
			pyproject = _read_pyproject_toml(project_root)
		except FileNotFoundError as e:
			logger.error(str(e))
			return False
		except Exception as e:
			logger.error(f"Error al parsear pyproject.toml: {e}")
			return False
		
		# 5. Extraer dependencias
		try:
			dependencies = _extract_dependencies(pyproject)
			logger.debug(f"Dependencias encontradas: {len(dependencies)}")
		except ValueError as e:
			logger.error(str(e))
			return False
		
		# 6. Verificar paquetes instalados
		logger.info("Verificando dependencias...")
		missing_packages = _find_missing_packages(dependencies, logger)
		
		if not missing_packages:
			logger.success("Todas las dependencias ya están instaladas")
			return True
		
		logger.warning(f"{len(missing_packages)} paquete(s) faltante(s)")
		
		# 7. Instalar paquetes faltantes
		if not _install_packages(missing_packages, logger):
			logger.warning("Algunos paquetes pueden no haberse instalado correctamente")
			return False
		
		logger.success("Dependencias instaladas exitosamente")
		return True
		
	except KeyboardInterrupt:
		logger.warning("Bootstrap interrumpido por el usuario")
		return False
	except Exception as e:
		logger.error(f"Error inesperado durante bootstrap: {e}")
		if verbose:
			import traceback
			traceback.print_exc()
		return False


__all__ = ["bootstrap", "BootstrapLogger", "_reexec_in_venv"]
