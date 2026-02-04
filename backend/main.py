# -*- coding: utf-8 -*-
import threading
import os
import subprocess
import asyncio
import logging
import sys

# Asegura que la carpeta raíz esté en sys.path para importaciones absolutas
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from backend import config
from activities.poll import resetpoll

from websocket_server import WebSocketServer
from usermanager import (
    load_user_cache, save_user_cache, cache_user_info,
    load_banned_users, save_banned_users,
    ban_user_by_name, unban_user_by_name, show_ban_list
)
from youtube_api import authenticate_youtube_api, get_live_chat_id, send_message, send_message_async
#from activities.spin import add_users_to_roulette, aggrul
#from activities.poll import resetpoll
from adminconsole import console_input
from youtube_cmds_listener import youtube_listener
from discordbot.dcbot import play_next_song, start_discord_bot


# Configuración de logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOG_FILE = os.path.join(LOG_DIR, "powerbot.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Variables globales mínimas

# Arranque del servidor HTTP
def start_http_server():
    navegador_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'navegador'))
    with open(os.devnull, 'w') as devnull:
        subprocess.run(
            ['python', '-m', 'http.server', '8000', '--directory', navegador_dir],
            stdout=devnull, stderr=devnull
        )

http_thread = threading.Thread(target=start_http_server, daemon=True)
http_thread.start()


# Cargar cachés y baneados (nuevo formato)
user_cache_data = load_user_cache()
banned_users = load_banned_users()

# Instanciar servidor WebSocket
server = WebSocketServer()

# Iniciar bot de Discord automáticamente
start_discord_bot(server)
print("Bot de Discord iniciado automáticamente en background...")

# Listener de WebSocket
async def websocket_listener():
    max_reintentos = 2
    intentos = 0
    while intentos < max_reintentos:
        try:
            message = await server.get_messages()
            if not isinstance(message, dict):
                await asyncio.sleep(0.1)  # Cede el control al event loop
                continue
            
            # Detectar fin de video y reproducir siguiente canción
            if message.get("type") == "video_ended":
                print("Mensaje recibido: {\"type\":\"video_ended\"}")
                print("Reproduciendo siguiente canción de la cola...")
                play_next_song()
            
            if message.get("type") == "resetpoll":
                print("Soy un resetpoll XD")
                resetpoll(config)
            if message.get("type") == "winnerspin":
                print(f"El Ganador de la ruleta es: {message.get('data')}")
                if config.isyappi:
                    send_message(config.youtube, f"El Ganador de la ruleta es: {message.get('data')}")
            intentos = 0
        except Exception as e:
            intentos += 1
            logging.error(f"Error en websocket_listener: {e} (Intento {intentos}/{max_reintentos})")
            await asyncio.sleep(1)
    print("websocket_listener: Se alcanzó el número máximo de reintentos. Se detiene la escucha.")

# Función principal
async def main():
    # Esperar un momento a que el bot de Discord se inicie y tenga store_manager
    await asyncio.sleep(3)
    
    # Obtener store_manager del bot de Discord
    from discordbot.dcbot import discord_bot_instance
    store_manager = None
    if discord_bot_instance and hasattr(discord_bot_instance, 'store_manager'):
        store_manager = discord_bot_instance.store_manager
        print("✓ store_manager disponible para YouTube")
    else:
        print("⚠ store_manager no disponible - las compras de YouTube estarán deshabilitadas")
    
    # Crear tareas asíncronas
    tasks = [
        asyncio.create_task(server.start()),
        asyncio.create_task(websocket_listener()),
        asyncio.create_task(
            youtube_listener(
                server,
                send_message_async,
                config.votos,
                config.waittime,
                cache_user_info,
                store_manager
            )
        ),
        asyncio.to_thread(console_input, server), 
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())