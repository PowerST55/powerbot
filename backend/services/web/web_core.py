from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import uvicorn
from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PowerBot Web", version="1.0.0")
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_index_path() -> Path | None:
	"""Resuelve el index principal a servir en /."""
	candidates = [
		os.getenv("WEB_INDEX_FILE", "").strip(),
		"fronted/index.html",
		"frontend/index.html",
	]

	for candidate in candidates:
		if not candidate:
			continue
		path = Path(candidate)
		if not path.is_absolute():
			path = PROJECT_ROOT / candidate
		if path.exists() and path.is_file():
			return path
	return None


def _default_mounts() -> Iterable[tuple[str, Path]]:
	"""Montajes base útiles del proyecto."""
	return (
		("/fronted", PROJECT_ROOT / "fronted"),
		("/frontend", PROJECT_ROOT / "frontend"),
		("/media", PROJECT_ROOT / "media"),
	)


def _parse_custom_mounts() -> Iterable[tuple[str, Path]]:
	"""
	Parsea WEB_STATIC_MOUNTS con formato:
		"/ui=fronted;/assets=media;/docs=C:/ruta/absoluta"
	"""
	raw = os.getenv("WEB_STATIC_MOUNTS", "").strip()
	if not raw:
		return ()

	parsed: list[tuple[str, Path]] = []
	for chunk in raw.split(";"):
		chunk = chunk.strip()
		if not chunk or "=" not in chunk:
			continue
		url_prefix, path_value = chunk.split("=", 1)
		url_prefix = url_prefix.strip()
		path_value = path_value.strip()
		if not url_prefix.startswith("/"):
			url_prefix = f"/{url_prefix}"
		path = Path(path_value)
		if not path.is_absolute():
			path = PROJECT_ROOT / path_value
		parsed.append((url_prefix, path))

	return parsed


def _mount_static_dirs() -> None:
	mounted_prefixes: set[str] = set()

	for url_prefix, directory in [*_default_mounts(), *_parse_custom_mounts()]:
		if url_prefix in mounted_prefixes:
			continue
		if directory.exists() and directory.is_dir():
			app.mount(url_prefix, StaticFiles(directory=str(directory)), name=url_prefix.strip("/"))
			mounted_prefixes.add(url_prefix)


_mount_static_dirs()


@app.get("/", response_model=None)
async def root() -> Response:
	index_file = _resolve_index_path()
	if index_file:
		return FileResponse(index_file)
	return JSONResponse(
		{
			"service": "PowerBot Web",
			"status": "ok",
			"message": "No se encontró index.html. Define WEB_INDEX_FILE o usa /health.",
		}
	)


@app.get("/health")
async def health() -> dict:
	return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
	await ws.accept()
	try:
		while True:
			message = await ws.receive_text()
			await ws.send_text(f"echo: {message}")
	except WebSocketDisconnect:
		return


def run() -> None:
	host = os.getenv("WEB_HOST", "0.0.0.0")
	port = int(os.getenv("WEB_PORT", "19131"))
	uvicorn.run("backend.services.web.web_core:app", host=host, port=port, reload=False)


if __name__ == "__main__":
	run()
