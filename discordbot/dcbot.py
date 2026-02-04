import os
import json
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from .commands import setup_commands
import threading
import asyncio

# Importar funciones de caché de usuarios
import sys
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from backend.usermanager import cache_discord_user, add_points_to_user, get_user_points
from backend.economy import EconomyManager

env_path = os.path.join(os.path.dirname(__file__), '../keys/.env')
load_dotenv(env_path)

intents = discord.Intents.default()

class DiscordBot(commands.Bot):
    def __init__(self, websocket_server=None) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or(os.getenv("PREFIX")),
            intents=intents,
            help_command=None,
        )
        # Servidor WebSocket
        self.websocket_server = websocket_server
        # Variables para logging de sesiones
        self.session_start = None
        self.logs = []
        self.session_file = None
        # Crear carpeta data si no existe
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        # Cola de canciones
        self.queue = []
        self.queue_file = os.path.join(self.data_dir, 'queue.json')
        self.load_queue()
        # Estado de bucle
        self.loop_enabled = False
        # Canción actual
        self.current_song = None
        # Canal de notificaciones
        self.notification_channel_file = os.path.join(self.data_dir, 'notification_channel.json')
        self.notification_channel = None
        self.load_notification_channel()
        # Sistema de economía (puntos/pews)
        self.economy_manager = EconomyManager(self.data_dir)
        # Canal de logs
        self.log_channel_file = os.path.join(self.data_dir, 'log_channel.json')
        self.log_channel = None
        self.load_log_channel()

    async def setup_hook(self) -> None:
        print(f"Logged in as {self.user.name}")
        # Crear carpeta sessions si es que no existe
        sessions_dir = os.path.join(os.path.dirname(__file__), 'sessions')
        os.makedirs(sessions_dir, exist_ok=True)
        # Generar nombre de archivo de sesión
        now = datetime.now(timezone(timedelta(hours=-5)))
        self.session_file = os.path.join(sessions_dir, f"session_{now.strftime('%Y%m%d_%H%M%S')}.json")
        self.session_start = datetime.now(timezone.utc)
        # Configurar comandos ANTES de sincronizar
        setup_commands(self)
        # Configurar sistema de tienda
        from .store import setup_store_commands, ComprarPersistentView
        setup_store_commands(self)
        # Registrar la vista persistente para botones de tienda
        self.add_view(ComprarPersistentView(bot=self))
        # Sincronizar comandos slash DESPUÉS de registrarlos
        await self.tree.sync()
        # Iniciar tarea de otorgamiento de puntos de voz
        self.voice_points_task.start()
        print(f"Sesión iniciada: {self.session_file}")

    @tasks.loop(seconds=60)
    async def voice_points_task(self):
        """Tarea que otorga puntos según el intervalo configurado a usuarios en canales de voz"""
        try:
            voice_users = self.economy_manager.get_all_voice_users()
            points_amount = self.economy_manager.get_points_per_interval()
            
            for user_id in voice_users:
                # Verificar si el usuario debe ganar puntos según el intervalo configurado
                if self.economy_manager.get_voice_points_earned(user_id):
                    result = add_points_to_user(user_id, points_amount)
                    if result:
                        try:
                            member = None
                            for guild in self.guilds:
                                member = guild.get_member(user_id)
                                if member:
                                    break
                            
                            if member:
                                current_pews = result.get("puntos", 0)
                                print(f"✓ {points_amount}₱ sumado a {member.name} (voz) | Pews totales: {current_pews:.1f}₱")
                        except Exception as e:
                            print(f"⚠ Error mostrando info de puntos de voz: {e}")
        except Exception as e:
            print(f"⚠ Error en voice_points_task: {e}")
    
    @voice_points_task.before_loop
    async def before_voice_points_task(self):
        """Se ejecuta antes de iniciar la tarea, espera a que el bot esté listo"""
        await self.wait_until_ready()

    async def on_ready(self):
        """Se ejecuta cuando el bot está completamente listo"""
        print(f"\n✅ Bot listo y conectado")
        
        # Cachear miembros del servidor al estar listo
        try:
            print("👥 Cacacheando miembros del servidor...")
            for guild in self.guilds:
                for member in guild.members:
                    try:
                        avatar_url = member.avatar.url if member.avatar else None
                        cache_discord_user(
                            discord_id=member.id,
                            name=member.name,
                            avatar_url=avatar_url
                        )
                    except Exception as e:
                        print(f"⚠ Error cacacheando miembro {member.name}: {e}")
            print("✓ Miembros cacacheados correctamente\n")
        except Exception as e:
            print(f"⚠ Error al cachear miembros: {e}\n")
        
        # Recargar botones de tienda para mantener persistencia
        if hasattr(self, 'store_manager') and self.guilds:
            try:
                print("🔄 Recargando botones de tienda...")
                guild = self.guilds[0]
                
                # Obtener canal forum
                if self.store_manager.forum_channel_id:
                    forum_channel = guild.get_channel(self.store_manager.forum_channel_id)
                    if forum_channel and isinstance(forum_channel, discord.ForumChannel):
                        # Escanear items UNA SOLA VEZ
                        items = self.store_manager.scan_store_items()
                        threads_reloaded = 0
                        
                        # Recorrer todos los threads archivados y recargar los botones
                        async for thread in forum_channel.archived_threads():
                            try:
                                for item in items:
                                    if self.store_manager.item_threads.get(item['id']) == thread.id:
                                        await self.store_manager.update_item_thread(thread, item)
                                        threads_reloaded += 1
                                        break
                            except Exception as e:
                                print(f"⚠ Error recargando thread {thread.id}: {e}")
                        
                        # También procesar threads activos
                        for thread in forum_channel.threads:
                            try:
                                for item in items:
                                    if self.store_manager.item_threads.get(item['id']) == thread.id:
                                        await self.store_manager.update_item_thread(thread, item)
                                        threads_reloaded += 1
                                        break
                            except Exception as e:
                                print(f"⚠ Error recargando thread activo {thread.id}: {e}")
                        
                        print(f"✅ {threads_reloaded} botones de tienda recargados\n")
            except Exception as e:
                print(f"⚠ Error recargando tienda: {e}\n")
        
        # Actualizar tienda automáticamente al estar listo
        if hasattr(self, 'store_manager') and self.guilds:
            try:
                print("\n🔄 Actualizando tienda automáticamente...")
                guild = self.guilds[0]  # Usar el primer servidor disponible
                
                # Crear forum si no existe
                if not self.store_manager.forum_channel_id:
                    print("📋 Creando canal forum de tienda...")
                    await self.store_manager.create_store_forum(guild)
                
                # Actualizar items
                await self.store_manager.update_store(guild)
                print("✅ Tienda actualizada correctamente\n")
            except Exception as e:
                print(f"⚠ Error al actualizar tienda automáticamente: {e}\n")
    
    async def on_member_join(self, member: discord.Member):
        """Se ejecuta cuando un nuevo miembro se une al servidor"""
        try:
            print(f"👤 Nuevo miembro ingresó: {member.name}")
            avatar_url = member.avatar.url if member.avatar else None
            cache_discord_user(
                discord_id=member.id,
                name=member.name,
                avatar_url=avatar_url
            )
            print(f"✓ Miembro {member.name} cacacheado")
        except Exception as e:
            print(f"⚠ Error cacacheando nuevo miembro {member.name}: {e}")
    
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Se ejecuta cuando el estado de voz de un usuario cambia"""
        # Si el usuario es un bot, ignorar
        if member.bot:
            return
        
        try:
            # Usuario entra a canal de voz (desde ningún canal)
            if after.channel is not None and before.channel is None:
                self.economy_manager.add_voice_user(member.id)
                print(f"👤 {member.name} entró a canal de voz: {after.channel.name}")
            
            # Usuario sale de canal de voz (a ningún canal)
            elif after.channel is None and before.channel is not None:
                self.economy_manager.remove_voice_user(member.id)
                print(f"👤 {member.name} salió de canal de voz: {before.channel.name}")
            
            # Usuario se mueve entre canales (importante para bots de crear salas)
            elif after.channel is not None and before.channel is not None and after.channel.id != before.channel.id:
                # Mantener el tracking continuo, simplemente actualizar el timestamp
                # para evitar que pierda progreso al moverse
                print(f"🔄 {member.name} se movió de {before.channel.name} a {after.channel.name}")
                # No hacer nada especial, el usuario sigue en voz
        
        except Exception as e:
            print(f"⚠ Error en on_voice_state_update: {e}")

    def load_queue(self):
        """Carga la cola desde el archivo JSON."""
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                self.queue = json.load(f)
        except FileNotFoundError:
            self.queue = []

    def save_queue(self):
        """Guarda la cola al archivo JSON."""
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(self.queue, f, indent=4, ensure_ascii=False)

    def load_notification_channel(self):
        """Carga el canal de notificaciones desde el archivo JSON."""
        try:
            with open(self.notification_channel_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.notification_channel = data.get('channel_id')
        except FileNotFoundError:
            self.notification_channel = None

    def save_notification_channel(self):
        """Guarda el canal de notificaciones al archivo JSON."""
        data = {'channel_id': self.notification_channel.id if self.notification_channel else None}
        with open(self.notification_channel_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def load_log_channel(self):
        """Carga el canal de logs desde el archivo JSON."""
        try:
            with open(self.log_channel_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.log_channel = data.get('channel_id')
        except FileNotFoundError:
            self.log_channel = None

    def save_log_channel(self):
        """Guarda el canal de logs al archivo JSON."""
        data = {'channel_id': self.log_channel}
        with open(self.log_channel_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    async def send_log(self, log_message: str, log_type: str = "INFO"):
        """Envía un mensaje de log al canal configurado como embed.
        
        Args:
            log_message: Mensaje a enviar (puede contener saltos de línea)
            log_type: Tipo de log (INFO, WARNING, ERROR, SUCCESS)
        """
        if not self.log_channel:
            return
        
        try:
            channel = self.get_channel(self.log_channel)
            if channel:
                # Mapeo de colores y emojis
                log_config = {
                    "INFO": {
                        "color": 0x0099ff,
                        "emoji": "ℹ️",
                        "title": "Información"
                    },
                    "WARNING": {
                        "color": 0xffaa00,
                        "emoji": "⚠️",
                        "title": "Advertencia"
                    },
                    "ERROR": {
                        "color": 0xff3333,
                        "emoji": "❌",
                        "title": "Error"
                    },
                    "SUCCESS": {
                        "color": 0x00ff00,
                        "emoji": "✅",
                        "title": "Éxito"
                    }
                }
                
                config = log_config.get(log_type, log_config["INFO"])
                timestamp = datetime.now(timezone(timedelta(hours=-5))).strftime("%Y-%m-%d %H:%M:%S")
                
                # Crear embed
                embed = discord.Embed(
                    title=f"{config['emoji']} {config['title']}",
                    description=log_message,
                    color=config['color'],
                    timestamp=datetime.now(timezone.utc)
                )
                
                embed.set_footer(text=f"PowerBot Log • {timestamp}")
                
                await channel.send(embed=embed)
        except Exception as e:
            print(f"⚠ Error enviando log: {e}")

    def write_session_log(self):
        """Escribe los logs de la sesión al archivo JSON."""
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(self.logs, f, indent=4, ensure_ascii=False)

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user or message.author.bot:
            return
        
        # Cachear usuario de Discord
        try:
            avatar_url = message.author.avatar.url if message.author.avatar else None
            cache_discord_user(
                discord_id=message.author.id,
                name=message.author.name,
                avatar_url=avatar_url
            )
        except Exception as e:
            print(f"⚠ Error cacacheando usuario en on_message: {e}")
        
        # Sistema de ganancia de puntos por canal
        channel_id_str = str(message.channel.id)
        if channel_id_str in self.economy_manager.points_channels:
            try:
                # Procesar mensaje y determinar si gana puntos
                if self.economy_manager.process_message(message.author.id):
                    points_amount = self.economy_manager.get_points_per_interval()
                    result = add_points_to_user(message.author.id, points_amount)
                    if result:
                        current_pews = result.get("puntos", 0)
                        print(f"✓ {points_amount}₱ sumado a {message.author.name} | Tu cantidad de Pews es: {current_pews:.1f}₱")
            except Exception as e:
                print(f"⚠ Error procesando ganancia de puntos: {e}")
        
        await self.process_commands(message)


# Variable global para almacenar la instancia del bot
discord_bot_instance = None
bot_thread = None
bot_loop = None

def _run_bot_in_thread(websocket_server):
    """Ejecuta el bot de Discord en un thread separado con su propio event loop."""
    global discord_bot_instance, bot_loop
    
    try:
        # Crear un nuevo event loop para este thread
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        
        discord_bot_instance = DiscordBot(websocket_server=websocket_server)
        print("Bot de Discord iniciado en thread separado...")
        
        # Ejecutar el bot en el event loop de este thread
        bot_loop.run_until_complete(discord_bot_instance.start(os.getenv("TOKEN")))
    except Exception as e:
        print(f"Error al ejecutar el bot de Discord en thread: {e}")
        discord_bot_instance = None
        if bot_loop:
            bot_loop.close()
            bot_loop = None

def start_discord_bot(websocket_server):
    """Inicia el bot de Discord en un thread separado."""
    global discord_bot_instance, bot_thread
    
    if discord_bot_instance is not None:
        print("El bot de Discord ya está en ejecución.")
        return
    
    try:
        # Crear y iniciar thread para el bot
        bot_thread = threading.Thread(
            target=_run_bot_in_thread,
            args=(websocket_server,),
            daemon=True
        )
        bot_thread.start()
        print("Iniciando bot de Discord en background...")
    except Exception as e:
        print(f"Error al iniciar el bot de Discord: {e}")
        discord_bot_instance = None

def stop_discord_bot():
    """Detiene el bot de Discord."""
    global discord_bot_instance, bot_loop, bot_thread
    
    if discord_bot_instance is not None:
        print("Deteniendo bot de Discord...")
        try:
            # Cerrar el bot usando su event loop
            if bot_loop and bot_loop.is_running():
                # Programar el cierre en el event loop del bot
                future = asyncio.run_coroutine_threadsafe(
                    discord_bot_instance.close(),
                    bot_loop
                )
                future.result(timeout=5)
            
            discord_bot_instance = None
            bot_loop = None
            bot_thread = None
            print("Bot de Discord detenido correctamente.")
        except Exception as e:
            print(f"Error al detener el bot: {e}")
            discord_bot_instance = None
            bot_loop = None
            bot_thread = None
    else:
        print("El bot de Discord no está en ejecución.")

async def _play_next_song_async():
    """Reproduce la siguiente canción de la cola (ejecutable en el event loop del bot)."""
    if discord_bot_instance and discord_bot_instance.queue:
        next_song = discord_bot_instance.queue.pop(0)
        discord_bot_instance.save_queue()
        
        # Enviar por WebSocket
        content = {"type": "youtube", "url": next_song['url'], "user": next_song['user']}
        await discord_bot_instance.websocket_server.send_update(content)
        
        discord_bot_instance.current_song = next_song
        print(f"[DISCORD BOT] Siguiente canción en cola: {next_song['url']} por {next_song['user']}")
        
        # Enviar mensaje al canal de notificaciones
        if discord_bot_instance.notification_channel:
            try:
                channel = discord_bot_instance.get_channel(discord_bot_instance.notification_channel)
                if channel:
                    # Verificar permisos antes de enviar
                    permissions = channel.permissions_for(channel.guild.me)
                    if permissions.send_messages:
                        await channel.send(f"🎵 **Ahora reproduciendo:**\n{next_song['url']}")
                    else:
                        print(f"[DISCORD BOT] Sin permisos para enviar mensajes en el canal {channel.name}")
                else:
                    print(f"[DISCORD BOT] Canal de notificaciones no encontrado (ID: {discord_bot_instance.notification_channel})")
            except Exception as e:
                print(f"[DISCORD BOT] Error al enviar mensaje de reproducción: {e}")
        
        # Registrar en log
        session_time = (datetime.now(timezone.utc) - discord_bot_instance.session_start).total_seconds() / 60
        timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
        log_entry = {
            "usuario": "Sistema",
            "tipo": "evento",
            "evento": "video_ended_next",
            "url": next_song['url'],
            "tiempo_sesion": round(session_time, 2),
            "timestamp": timestamp
        }
        discord_bot_instance.logs.append(log_entry)
        discord_bot_instance.write_session_log()
    elif discord_bot_instance:
        print("[DISCORD BOT] Cola vacía, no hay siguientes canciones.")

def play_next_song():
    """Reproduce la siguiente canción desde un contexto síncrono (puede llamarse desde main.py)."""
    global discord_bot_instance, bot_loop
    
    if discord_bot_instance is None:
        print("[DISCORD BOT] El bot no está en ejecución.")
        return
    
    if not discord_bot_instance.queue:
        print("[DISCORD BOT] No hay canciones en la cola.")
        return
    
    try:
        if bot_loop and bot_loop.is_running():
            # Ejecutar la función async en el event loop del bot
            future = asyncio.run_coroutine_threadsafe(
                _play_next_song_async(),
                bot_loop
            )
            future.result(timeout=10)
        else:
            print("[DISCORD BOT] Event loop del bot no está disponible.")
    except Exception as e:
        print(f"[DISCORD BOT] Error al reproducir siguiente canción: {e}")

# Solo ejecutar como script directo
if __name__ == "__main__":
    bot = DiscordBot()
    bot.run(os.getenv("TOKEN"))
