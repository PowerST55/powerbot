"""
PowerBot Discord - Bot básico de Discord

Ejecutar directamente para pruebas:
    python backend/services/discord_bot/bot_core.py
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import discord
from discord.ext import commands


class PowerBotDiscord(commands.Bot):
    """Bot de Discord para PowerBot"""
    
    def __init__(self, prefix: str = "!"):
        # Configurar intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=prefix,
            intents=intents,
            help_command=None
        )
        
        self.start_time = None
    
    async def setup_hook(self):
        """Se ejecuta al inicializar el bot (antes de on_ready)"""
        print(f"🔧 Configurando {self.user.name}...")
        
        # Registrar comandos de admin
        from backend.services.discord_bot.commands.admin import setup_admin_commands
        setup_admin_commands(self)
        
        # Registrar comandos sociales
        from backend.services.discord_bot.commands.social import setup_social_commands
        setup_social_commands(self)
        
        # Sincronizar comandos slash
        try:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} comandos sincronizados")
        except Exception as e:
            print(f"⚠️ Error sincronizando: {e}")
    
    async def on_ready(self):
        """Se ejecuta cuando el bot está completamente listo"""
        from datetime import datetime
        self.start_time = datetime.now()
        
        print(f"✅ {self.user.name} está conectado")
        print(f"   Servidores: {len(self.guilds)}")
        print()


def create_bot(token: str = None, prefix: str = "!") -> PowerBotDiscord:
    """
    Crea una instancia del bot con configuración básica.
    
    Args:
        token: Token de Discord (opcional, se carga de .env si no se proporciona)
        prefix: Prefix de comandos
    
    Returns:
        PowerBotDiscord: Instancia del bot
    """
    # Cargar variables de entorno
    env_path = Path(__file__).parent.parent.parent / "keys" / ".env"
    load_dotenv(env_path)
    
    if token is None:
        token = os.getenv("DISCORD_TOKEN")
    
    if not token or token == "TU_TOKEN_AQUI":
        raise ValueError("❌ Token de Discord no configurado en keys/.env")
    
    # Obtener prefix de .env si existe
    env_prefix = os.getenv("DISCORD_PREFIX", prefix)
    
    bot = PowerBotDiscord(prefix=env_prefix)
    
    return bot


async def start_bot(token: str = None, prefix: str = "!"):
    """
    Inicia el bot de Discord.
    
    Args:
        token: Token de Discord (opcional)
        prefix: Prefix de comandos
    """
    bot = create_bot(token, prefix)
    
    try:
        await bot.start(token or os.getenv("DISCORD_TOKEN"))
    except KeyboardInterrupt:
        print("\n⚠️ Deteniendo bot...")
        await bot.close()
    except Exception as e:
        print(f"❌ Error al iniciar bot: {e}")
        raise


# Ejecución directa para pruebas
if __name__ == "__main__":
    # Asegurar que el directorio raíz esté en el path
    root_dir = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(root_dir))
    
    print("🤖 PowerBot Discord - Modo de prueba")
    print("=" * 50)
    
    try:
        asyncio.run(start_bot())
    except ValueError as e:
        print(f"\n{e}")
        print("\n📝 Configura tu token en: backend/keys/.env")
        print("   DISCORD_TOKEN=tu_token_aqui")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Bot detenido")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        sys.exit(1)
