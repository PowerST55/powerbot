"""
Punto de entrada para ejecutar el bot de Discord
Uso: python -m discordbot
"""

import os
import sys
from dotenv import load_dotenv

# Asegurar que el paquete esté en el path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Ahora importar el bot
from discordbot.dcbot import DiscordBot

# Cargar variables de entorno
env_path = os.path.join(parent_dir, 'keys/.env')
load_dotenv(env_path)

if __name__ == "__main__":
    token = os.getenv("TOKEN")
    
    if not token:
        print("[ERROR] No se encontró el token de Discord en el archivo .env")
        print("Asegúrate de que el archivo keys/.env contiene: TOKEN=tu_token_aqui")
        sys.exit(1)
    
    print("\n✅ Iniciando PowerBot - Discord Bot")
    print("=" * 50)
    
    try:
        bot = DiscordBot()
        bot.run(token)
    except KeyboardInterrupt:
        print("\n\n[INFO] Bot detenido por el usuario")
    except Exception as e:
        print(f"\n[ERROR] Error al ejecutar el bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
