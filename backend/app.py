"""
PowerBot - Sistema de consola interactivo asincrónico.

Frontend principal que enseña mejor el flujo de la aplicación:
1. Bootstrap: Instala dependencias y verifica el entorno
2. Consola: Inicia la interfaz interactiva
"""

import asyncio
import sys
import logging
from pathlib import Path

# Configurar logging (usando la consola centralizada de colores)
logging.basicConfig(
	level=logging.INFO,
	format="%(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> int:
	"""
	Función principal de PowerBot.
	
	Retorna:
		int: Código de salida (0 = éxito, 1 = error)
	"""
	from backend.bootstrap import bootstrap, _reexec_in_venv
	
	# Obtener la consola configurada
	try:
		from backend.core import get_console
		console = get_console()
	except Exception:
		# Fallback si la consola no está disponible
		class SimpleConsole:
			def print(self, msg):
				print(msg)
		console = SimpleConsole()  # type: ignore
	
	try:
		# 1. Reejecutar en venv si es necesario (solo al inicio)
		bootstrap_verbose = "--verbose" in sys.argv
		_reexec_in_venv(None, ".venv")  # type: ignore
		
		# 2. Ejecutar bootstrap
		if not bootstrap(verbose=bootstrap_verbose):
			console.print("[error]✗ Bootstrap falló[/error]")
			return 1
		
		# 3. Importar e iniciar la consola interactiva
		from backend.console.console import start_console
		
		console.print("[header]PowerBot iniciado[/header]")
		await start_console()
		
		return 0
		
	except KeyboardInterrupt:
		console.print("\n[warning]⚠ Aplicación detenida por el usuario[/warning]")
		return 130  # Código estándar para interrupción por Ctrl+C
	except Exception as e:
		console.print(f"[error]✗ Error fatal: {e}[/error]")
		if "--verbose" in sys.argv:
			import traceback
			traceback.print_exc()
		return 1


if __name__ == "__main__":
	# Asegurar que estamos en el directorio correcto
	backend_dir = Path(__file__).parent
	sys.path.insert(0, str(backend_dir.parent))
	
	# Ejecutar el programa
	try:
		exit_code = asyncio.run(main())
		sys.exit(exit_code)
	except Exception as e:
		# Intentar usar la consola con colores si está disponible
		try:
			from backend.core import get_console
			console = get_console()
			console.print(f"[error]✗ Error crítico: {e}[/error]")
		except Exception:
			print(f"✗ Error crítico: {e}")
		
		if "--verbose" in sys.argv:
			import traceback
			traceback.print_exc()
		sys.exit(1)

