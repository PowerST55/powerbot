"""
Web toggle config manager.
Gestiona el estado on/off persistente del servidor web.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WebToggleConfigManager:
	"""Gestiona la persistencia del estado de encendido del servidor web."""

	def __init__(self, data_dir: Optional[Path] = None):
		if data_dir is None:
			backend_dir = Path(__file__).resolve().parents[3]
			data_dir = backend_dir / "data" / "web"

		self.data_dir = Path(data_dir)
		self.data_dir.mkdir(parents=True, exist_ok=True)
		self.config_file = self.data_dir / "toggle_on_off.json"

	def _default_config(self) -> dict:
		return {
			"web_enabled": False,
			"last_updated": datetime.utcnow().isoformat(),
			"status": "off",
		}

	def load_config(self) -> dict:
		"""Carga la configuración persistida, con fallback por defecto."""
		try:
			if self.config_file.exists():
				with open(self.config_file, "r", encoding="utf-8") as file:
					data = json.load(file)
					if isinstance(data, dict):
						return {
							"web_enabled": bool(data.get("web_enabled", False)),
							"last_updated": data.get("last_updated", datetime.utcnow().isoformat()),
							"status": "on" if bool(data.get("web_enabled", False)) else "off",
						}
		except Exception as exc:
			logger.error(f"Error cargando config web: {exc}")

		return self._default_config()

	def save_config(self, enabled: bool) -> None:
		"""Guarda el estado on/off del servidor web."""
		payload = {
			"web_enabled": bool(enabled),
			"last_updated": datetime.utcnow().isoformat(),
			"status": "on" if enabled else "off",
		}

		try:
			with open(self.config_file, "w", encoding="utf-8") as file:
				json.dump(payload, file, indent=2, ensure_ascii=False)
		except Exception as exc:
			logger.error(f"Error guardando config web: {exc}")

	def is_enabled(self) -> bool:
		"""Indica si la configuración persistida está en ON."""
		return bool(self.load_config().get("web_enabled", False))

	def set_enabled(self, enabled: bool) -> None:
		"""Actualiza y persiste el estado ON/OFF."""
		self.save_config(bool(enabled))

	def get_status(self) -> dict:
		"""Obtiene estado completo de la configuración web."""
		cfg = self.load_config()
		cfg["config_file"] = str(self.config_file)
		return cfg


def create_web_toggle_manager() -> WebToggleConfigManager:
	"""Factory de conveniencia para el manager de toggle web."""
	return WebToggleConfigManager()

