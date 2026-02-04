#!/usr/bin/env python3
"""
Inicio del bot de Discord para Teramont VPS
"""

import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

# Cargar variables de entorno
env_path = os.path.join(os.path.dirname(__file__), 'keys/.env')
load_dotenv(env_path)

def main():
    """Inicia el bot de Discord"""
    try:
        from discordbot.dcbot import DiscordBot
        
        token = os.getenv("TOKEN")
        
        if not token:
            print("[ERROR] TOKEN no encontrado en keys/.env")
            sys.exit(1)
        
        print("\n[OK] Iniciando PowerBot en Teramont")
        print("=" * 50)
        print(f"Token configurado: {token[:10]}...")
        print("=" * 50 + "\n")
        
        bot = DiscordBot()
        bot.run(token)
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Bot detenido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
