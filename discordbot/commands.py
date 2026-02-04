"""
Comandos del Discord Bot
"""

import os
import json
import re
import aiohttp
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from backend.account_linking import AccountLinkingManager
from backend.transaction_logger import TransactionLogger

EMBED_COLOR = 0x0000ff  # Azul

# Inicializar logger de transacciones
transaction_logger = TransactionLogger(
    data_dir=os.path.join(os.path.dirname(__file__), '..', 'data')
)


async def get_youtube_title(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html = await response.text()
                match = re.search(r'<title>(.*?)</title>', html)
                if match:
                    title = match.group(1).replace(' - YouTube', '').strip()
                    return title
    except Exception as e:
        print(f"Error obteniendo título: {e}")
    return "Título desconocido"


class PPTView(discord.ui.View):
    """View con botones para Piedra Papel Tijeras"""
    def __init__(self, allowed_user_id: int, timeout=180):
        super().__init__(timeout=timeout)
        self.allowed_user_id = allowed_user_id
        self.choice = None
        self.timed_out = False
    
    async def on_timeout(self):
        """Se ejecuta cuando expira el timeout"""
        self.timed_out = True
        for item in self.children:
            item.disabled = True
    
    @discord.ui.button(label="Piedra", emoji="🪨", style=discord.ButtonStyle.primary)
    async def piedra_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message("❌ No puedes interactuar con este juego.", ephemeral=True)
            return
        
        self.choice = "piedra"
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Papel", emoji="📄", style=discord.ButtonStyle.success)
    async def papel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message("❌ No puedes interactuar con este juego.", ephemeral=True)
            return
        
        self.choice = "papel"
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Tijeras", emoji="✂️", style=discord.ButtonStyle.danger)
    async def tijeras_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message("❌ No puedes interactuar con este juego.", ephemeral=True)
            return
        
        self.choice = "tijeras"
        await interaction.response.defer()
        self.stop()


class PPTRematchView(discord.ui.View):
    """View con botón de revancha para Piedra Papel Tijeras"""
    def __init__(self, player1_id: int, player2_id: int, timeout=60):
        super().__init__(timeout=timeout)
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.rematch_accepted = False
        self.timed_out = False
    
    async def on_timeout(self):
        """Se ejecuta cuando expira el timeout"""
        self.timed_out = True
        for item in self.children:
            item.disabled = True
    
    @discord.ui.button(label="Revancha", emoji="🔄", style=discord.ButtonStyle.primary)
    async def rematch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Solo los jugadores pueden aceptar la revancha
        if interaction.user.id not in [self.player1_id, self.player2_id]:
            await interaction.response.send_message("❌ No participaste en este duelo.", ephemeral=True)
            return
        
        self.rematch_accepted = True
        await interaction.response.defer()
        self.stop()


def setup_commands(bot):
    """
    Configura todos los comandos del bot.
    """
    
    @bot.tree.command(name="force_youtube", description="Reproduce un video inmediatamente ignorando la cola")
    @app_commands.describe(link="El link de YouTube a forzar")
    @app_commands.checks.has_role(1456005703713165375)
    async def force_youtube(interaction: discord.Interaction, link: str):
        # Verificar si es un link de YouTube
        if "youtube.com" in link or "youtu.be" in link:
            # Cargar blacklist
            blacklist_file = os.path.join(bot.data_dir, 'blacklist.json')
            try:
                with open(blacklist_file, 'r', encoding='utf-8') as f:
                    blacklist = json.load(f)
            except FileNotFoundError:
                blacklist = []
            # Verificar si está en blacklist
            if link in blacklist:
                await interaction.response.send_message("Error: Este video está en la lista negra.")
                return
            # Obtener título
            title = await get_youtube_title(link)
            # Si hay una canción reproduciéndose, insertarla al principio de la cola para mantener prioridad
            if bot.current_song:
                bot.queue.insert(0, bot.current_song)
                bot.save_queue()
            # Enviar por WebSocket inmediatamente
            content = {"type": "youtube", "url": link, "user": interaction.user.name}
            await bot.websocket_server.send_update(content)
            bot.current_song = {"url": link, "user": interaction.user.name, "title": title}
            print(f"Video forzado: {link} por {interaction.user.name}")
            
            # Enviar mensaje al canal de notificaciones
            if bot.notification_channel:
                try:
                    channel = bot.get_channel(bot.notification_channel)
                    if channel:
                        # Verificar permisos antes de enviar
                        permissions = channel.permissions_for(channel.guild.me)
                        if permissions.send_messages:
                            await channel.send(f"🎵 **Ahora reproduciendo:**\n{link}")
                        else:
                            print(f"Sin permisos para enviar mensajes en el canal {channel.name}")
                    else:
                        print(f"Canal de notificaciones no encontrado (ID: {bot.notification_channel})")
                except Exception as e:
                    print(f"Error al enviar mensaje de reproducción: {e}")
            
            # Calcular tiempo de sesión en minutos
            session_time = (datetime.now(timezone.utc) - bot.session_start).total_seconds() / 60
            # Timestamp GMT-5
            timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
            # Agregar log
            log_entry = {
                "usuario": interaction.user.name,
                "tipo": "comando",
                "comando": "force-youtube",
                "url": link,
                "tiempo_sesion": round(session_time, 2),
                "timestamp": timestamp
            }
            bot.logs.append(log_entry)
            bot.write_session_log()
            await interaction.response.send_message(f"Video forzado en reproducción: {link}")
        else:
            await interaction.response.send_message("Error: El link no es de YouTube.")

    @bot.tree.command(name="next", description="Reproduce la siguiente canción en la cola")
    @app_commands.checks.has_role(1456005703713165375)
    async def next_song(interaction: discord.Interaction):
        if bot.queue:
            next_song = bot.queue.pop(0)
            bot.save_queue()
            content = {"type": "youtube", "url": next_song['url'], "user": next_song['user']}
            await bot.websocket_server.send_update(content)
            bot.current_song = next_song
            print(f"Siguiente canción reproducida: {next_song['url']} por {next_song['user']}")
            
            # Enviar mensaje al canal de notificaciones
            if bot.notification_channel:
                try:
                    channel = bot.get_channel(bot.notification_channel)
                    if channel:
                        # Verificar permisos antes de enviar
                        permissions = channel.permissions_for(channel.guild.me)
                        if permissions.send_messages:
                            await channel.send(f"🎵 **Ahora reproduciendo:**\n{next_song['url']}")
                        else:
                            print(f"Sin permisos para enviar mensajes en el canal {channel.name}")
                    else:
                        print(f"Canal de notificaciones no encontrado (ID: {bot.notification_channel})")
                except Exception as e:
                    print(f"Error al enviar mensaje de reproducción: {e}")
            
            # Calcular tiempo de sesión y timestamp
            session_time = (datetime.now(timezone.utc) - bot.session_start).total_seconds() / 60
            timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
            # Agregar log
            log_entry = {
                "usuario": interaction.user.name,
                "tipo": "comando",
                "comando": "next",
                "tiempo_sesion": round(session_time, 2),
                "timestamp": timestamp
            }
            bot.logs.append(log_entry)
            bot.write_session_log()
            await interaction.response.send_message(f"Reproduciendo siguiente canción: {next_song['url']}")
        else:
            await interaction.response.send_message("La cola está vacía.")

    @bot.tree.command(name="bucle", description="Activa o desactiva el bucle del video actual")
    @app_commands.checks.has_role(1456005703713165375)
    async def toggle_loop(interaction: discord.Interaction):
        bot.loop_enabled = not bot.loop_enabled
        content = {"type": "loop", "enabled": bot.loop_enabled}
        await bot.websocket_server.send_update(content)
        status = "activado" if bot.loop_enabled else "desactivado"
        # Calcular tiempo de sesión y timestamp
        session_time = (datetime.now(timezone.utc) - bot.session_start).total_seconds() / 60
        timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
        # Agregar log
        log_entry = {
            "usuario": interaction.user.name,
            "tipo": "comando",
            "comando": "bucle",
            "parametros": {"estado": status},
            "tiempo_sesion": round(session_time, 2),
            "timestamp": timestamp
        }
        bot.logs.append(log_entry)
        bot.write_session_log()
        await interaction.response.send_message(f"Bucle {status}.")

    @bot.tree.command(name="cola", description="Muestra la cola de reproducción actual")
    @app_commands.checks.has_role(1456005703713165375)
    async def show_queue(interaction: discord.Interaction):
        embed = discord.Embed(title="Cola de Reproducción", color=EMBED_COLOR)
        lines = []
        if bot.current_song:
            lines.append(f"1. {bot.current_song.get('title', bot.current_song['url'])} - (Reproduciendose) - {bot.current_song['user']}")
            if bot.queue and bot.current_song == bot.queue[0]:
                songs = bot.queue[1:]
            else:
                songs = bot.queue
            for i, song in enumerate(songs, start=2):
                lines.append(f"{i}. {song.get('title', song['url'])} - {song['user']}")
        else:
            for i, song in enumerate(bot.queue, start=1):
                lines.append(f"{i}. {song.get('title', song['url'])} - {song['user']}")
        if lines:
            embed.add_field(name="Canciones en cola", value="\n".join(lines), inline=False)
            embed.set_footer(text=f"Total en cola: {len(bot.queue)}")
        else:
            embed.description = "La cola está vacía."
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="blacklist", description="Añade el video actual a la blacklist")
    @app_commands.checks.has_role(1181253292274221267)
    async def blacklist_current(interaction: discord.Interaction):
        if bot.current_song:
            blacklist_file = os.path.join(bot.data_dir, 'blacklist.json')
            try:
                with open(blacklist_file, 'r', encoding='utf-8') as f:
                    blacklist = json.load(f)
            except FileNotFoundError:
                blacklist = []
            if bot.current_song["url"] not in blacklist:
                blacklist.append(bot.current_song["url"])
                with open(blacklist_file, 'w', encoding='utf-8') as f:
                    json.dump(blacklist, f, indent=4)
                await interaction.response.send_message(f"Video añadido a la blacklist: {bot.current_song['url']}")
            else:
                await interaction.response.send_message("Este video ya está en la blacklist.")
        else:
            await interaction.response.send_message("No hay ningún video reproduciéndose actualmente.")

    @bot.tree.command(name="borrar_cola", description="Elimina toda la cola de reproducción")
    @app_commands.checks.has_role(1456005703713165375)
    async def clear_queue(interaction: discord.Interaction):
        bot.queue = []
        bot.save_queue()
        # Calcular tiempo de sesión y timestamp
        session_time = (datetime.now(timezone.utc) - bot.session_start).total_seconds() / 60
        timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
        # Agregar log
        log_entry = {
            "usuario": interaction.user.name,
            "tipo": "comando",
            "comando": "borrar_cola",
            "tiempo_sesion": round(session_time, 2),
            "timestamp": timestamp
        }
        bot.logs.append(log_entry)
        bot.write_session_log()
        await interaction.response.send_message("Cola de reproducción eliminada.")

    @bot.tree.command(name="youtube", description="Añade un link de YouTube a la cola")
    @app_commands.describe(link="El link de YouTube a añadir")
    @app_commands.checks.has_role(1456005703713165375)
    async def youtube(interaction: discord.Interaction, link: str):
        await interaction.response.defer()  # Deferir para enviar múltiples mensajes
        # Verificar si es un link de YouTube
        if "youtube.com" in link or "youtu.be" in link:
            # Cargar blacklist
            blacklist_file = os.path.join(bot.data_dir, 'blacklist.json')
            try:
                with open(blacklist_file, 'r', encoding='utf-8') as f:
                    blacklist = json.load(f)
            except FileNotFoundError:
                blacklist = []
            # Verificar si está en blacklist
            if link in blacklist:
                await interaction.followup.send("Error: Este video está en la lista negra.")
                return
            # Obtener título
            title = await get_youtube_title(link)
            # Crear objeto de canción
            song = {"url": link, "user": interaction.user.name, "title": title}
            
            # Si no hay canción reproduciéndose, reproducirla inmediatamente (sin agregar a cola)
            if not bot.current_song:
                content = {"type": "youtube", "url": link, "user": interaction.user.name}
                await bot.websocket_server.send_update(content)
                bot.current_song = song
                print(f"Canción reproducida: {link} por {interaction.user.name}")
                
                # Enviar mensaje al canal de notificaciones
                if bot.notification_channel:
                    try:
                        channel = bot.get_channel(bot.notification_channel)
                        if channel:
                            # Verificar permisos antes de enviar
                            permissions = channel.permissions_for(channel.guild.me)
                            if permissions.send_messages:
                                await channel.send(f"🎵 **Ahora reproduciendo:**\n{link}")
                            else:
                                print(f"Sin permisos para enviar mensajes en el canal {channel.name}")
                        else:
                            print(f"Canal de notificaciones no encontrado (ID: {bot.notification_channel})")
                    except Exception as e:
                        print(f"Error al enviar mensaje de reproducción: {e}")
            else:
                # Si ya hay canción reproduciéndose, verificar si ya está en la cola
                if any(s['url'] == link for s in bot.queue):
                    await interaction.followup.send("Esta canción ya está en la cola.")
                    return
                # Agregar a la cola
                bot.queue.append(song)
                bot.save_queue()
            # Crear embed
            embed = discord.Embed(title="Canción añadida a la Cola de Reproducción", color=EMBED_COLOR)
            embed.add_field(name="Canción", value=f"```{title}```", inline=False)
            embed.add_field(name="Solicitada por", value=interaction.user.name, inline=True)
            if bot.queue:
                pending_lines = []
                if bot.current_song:
                    pending_lines.append(f"1. {bot.current_song.get('title', bot.current_song['url'])} - (reproduciendose) - {bot.current_song['user']}")
                    if bot.queue and bot.current_song == bot.queue[0]:
                        songs = bot.queue[1:]
                    else:
                        songs = bot.queue
                    for i, s in enumerate(songs, start=2):
                        pending_lines.append(f"{i}. {s.get('title', s['url'])} - {s['user']}")
                else:
                    for i, s in enumerate(bot.queue, start=1):
                        pending_lines.append(f"{i}. {s.get('title', s['url'])} - {s['user']}")
                pending = "\n".join(pending_lines)
                embed.add_field(name="Canciones en cola", value=pending, inline=False)
            embed.set_footer(text=f"Posición en cola: {len(bot.queue)}")
            await interaction.followup.send(embed=embed)
            # Enviar el link para incrustación
            await interaction.followup.send(link)
        else:
            await interaction.followup.send("Error: El link no es de YouTube.")

    @bot.tree.command(name="pause", description="Pausa el video de YouTube")
    @app_commands.checks.has_role(1456005703713165375)
    async def pause(interaction: discord.Interaction):
        # Calcular tiempo de sesión y timestamp
        session_time = (datetime.now(timezone.utc) - bot.session_start).total_seconds() / 60
        timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
        # Agregar log
        log_entry = {
            "usuario": interaction.user.name,
            "tipo": "comando",
            "comando": "pause",
            "tiempo_sesion": round(session_time, 2),
            "timestamp": timestamp
        }
        bot.logs.append(log_entry)
        bot.write_session_log()
        # Enviar comando de pausa por WebSocket
        content = {"type": "pause"}
        await bot.websocket_server.send_update(content)
        await interaction.response.send_message("Video pausado.")

    @bot.tree.command(name="play", description="Reproduce el video de YouTube")
    @app_commands.checks.has_role(1456005703713165375)
    async def play(interaction: discord.Interaction):
        # Calcular tiempo de sesión y timestamp
        session_time = (datetime.now(timezone.utc) - bot.session_start).total_seconds() / 60
        timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
        # Agregar log
        log_entry = {
            "usuario": interaction.user.name,
            "tipo": "comando",
            "comando": "play",
            "tiempo_sesion": round(session_time, 2),
            "timestamp": timestamp
        }
        bot.logs.append(log_entry)
        bot.write_session_log()
        # Enviar comando de reproducción por WebSocket
        content = {"type": "play"}
        await bot.websocket_server.send_update(content)
        await interaction.response.send_message("Video reproduciendo.")

    @bot.tree.command(name="stop", description="Detiene el video de YouTube")
    @app_commands.checks.has_role(1456005703713165375)
    async def stop(interaction: discord.Interaction):
        # Calcular tiempo de sesión y timestamp
        session_time = (datetime.now(timezone.utc) - bot.session_start).total_seconds() / 60
        timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
        # Agregar log
        log_entry = {
            "usuario": interaction.user.name,
            "tipo": "comando",
            "comando": "stop",
            "tiempo_sesion": round(session_time, 2),
            "timestamp": timestamp
        }
        bot.logs.append(log_entry)
        bot.write_session_log()
        # Enviar comando de detener por WebSocket
        content = {"type": "stop"}
        await bot.websocket_server.send_update(content)
        await interaction.response.send_message("Video detenido.")

    @bot.tree.command(name="setchannel", description="Establece el canal para notificaciones del bot")
    @app_commands.describe(channel="El canal para notificaciones")
    @app_commands.checks.has_role(1456005703713165375)
    async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        bot.notification_channel = channel
        bot.save_notification_channel()
        await interaction.response.send_message(f"Canal de notificaciones establecido a {channel.mention}")

    @bot.tree.command(name="setlogbot", description="Establece el canal para los logs del bot")
    @app_commands.describe(channel="El canal para los logs")
    @app_commands.checks.has_role(1181253292274221267)
    async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        """Establece el canal donde se enviarán todos los logs del bot."""
        bot.log_channel = channel.id
        bot.save_log_channel()
        
        embed = discord.Embed(
            title="✓ Canal de logs configurado",
            description=f"Todos los logs serán enviados a {channel.mention}",
            color=0x00ff00
        )
        embed.add_field(
            name="📋 Tipos de logs",
            value="• ✅ SUCCESS - Acciones exitosas\n• ⚠️ WARNING - Advertencias\n• ❌ ERROR - Errores\n• ℹ️ INFO - Información general",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Enviar log de confirmación
        await bot.send_log(f"Canal de logs configurado por {interaction.user.mention}", "INFO")

    @bot.tree.command(name="volumen", description="Ajusta el volumen del video de YouTube (1-10)")
    @app_commands.describe(nivel="Nivel de volumen (1-10)")
    @app_commands.checks.has_role(1456005703713165375)
    async def volumen(interaction: discord.Interaction, nivel: int):
        if 1 <= nivel <= 10:
            # Calcular tiempo de sesión y timestamp
            session_time = (datetime.now(timezone.utc) - bot.session_start).total_seconds() / 60
            timestamp = datetime.now(timezone(timedelta(hours=-5))).isoformat()
            # Agregar log
            log_entry = {
                "usuario": interaction.user.name,
                "tipo": "comando",
                "comando": "volumen",
                "parametros": {"nivel": nivel},
                "tiempo_sesion": round(session_time, 2),
                "timestamp": timestamp
            }
            bot.logs.append(log_entry)
            bot.write_session_log()
            # Convertir a escala 0-100
            volume = nivel * 10
            # Enviar comando de volumen por WebSocket
            content = {"type": "volume", "level": volume}
            await bot.websocket_server.send_update(content)
            await interaction.response.send_message(f"Volumen ajustado a {nivel}/10.")
        else:
            await interaction.response.send_message("Error: El nivel de volumen debe estar entre 1 y 10.")

    # ==================== COMANDOS DE PEWS ====================
    
    # ---- Helpers internos para manejo de usuarios ----
    async def _resolver_objetivo_desde_parametros(interaction: discord.Interaction, usuario: discord.User | None, busqueda: str | None):
        """Resuelve un usuario de la base (Discord/YouTube) a partir de discord.User o una búsqueda por ID/nombre.
        Si se pasa un usuario de Discord y no existe en caché, lo crea automáticamente.
        Retorna (user_record, target_id_for_ops, target_name)
        """
        from backend.usermanager import load_user_cache, cache_discord_user

        user_cache = load_user_cache()
        users = user_cache.get("users", [])

        # Caso 1: usuario de Discord explícito
        if usuario is not None:
            print(f"🔍 Buscando usuario de Discord: {usuario.name} (ID: {usuario.id})")
            
            # Intentar obtener de la caché
            target = None
            for u in users:
                if u.get("discord_id") == str(usuario.id):
                    target = u
                    print(f"✓ Usuario encontrado en caché: {u.get('name')} (ID: {u.get('id')})")
                    break
            
            # Si no existe en caché, crearlo
            if target is None:
                print(f"⚠ Usuario no encontrado en caché, creándolo...")
                avatar_url = usuario.avatar.url if usuario.avatar else None
                try:
                    user_id = cache_discord_user(discord_id=usuario.id, name=usuario.name, avatar_url=avatar_url)
                    print(f"✓ Usuario creado con ID: {user_id}")
                    
                    # Recargar caché
                    user_cache = load_user_cache()
                    users = user_cache.get("users", [])
                    
                    # Buscar de nuevo
                    for u in users:
                        if u.get("discord_id") == str(usuario.id):
                            target = u
                            print(f"✓ Usuario recuperado de caché después de creación: {u.get('name')}")
                            break
                except Exception as e:
                    print(f"❌ Error creando usuario: {e}")
                    return None, None, None
            
            if target is None:
                print(f"❌ No se pudo crear o encontrar el usuario")
                return None, None, None
            
            # Preferir youtube_id si existe, sino discord_id, sino id
            target_id = target.get("youtube_id") or target.get("discord_id") or str(target.get("id"))
            target_name = target.get("name", usuario.name)
            print(f"✓ Objetivo resuelto: {target_name} (target_id: {target_id})")
            return target, target_id, target_name

        # Caso 2: búsqueda por texto: similar a /id (ID exacto o nombre exacto, case-insensitive)
        if busqueda:
            print(f"🔍 Búsqueda por texto: {busqueda}")
            # Buscar por ID universal
            if busqueda.isdigit():
                for u in users:
                    if str(u.get("id")) == busqueda:
                        target_id = u.get("youtube_id") or u.get("discord_id") or str(u.get("id"))
                        print(f"✓ Encontrado por ID: {u.get('name')}")
                        return u, target_id, u.get("name", f"ID {busqueda}")
            else:
                # Buscar por nombre (case-insensitive, exacto)
                busqueda_lower = busqueda.lower()
                for u in users:
                    if u.get("name", "").lower() == busqueda_lower:
                        target_id = u.get("youtube_id") or u.get("discord_id") or str(u.get("id"))
                        print(f"✓ Encontrado por nombre: {u.get('name')}")
                        return u, target_id, u.get("name")

        print(f"❌ No se encontró objetivo")
        return None, None, None
    
    @bot.tree.command(name="add_points_channel", description="Agrega un canal a la lista de canales para ganar pews")
    @app_commands.describe(channel="El canal donde se ganarán pews")
    @app_commands.checks.has_role(1181253292274221267)
    async def add_points_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        """Agrega un canal a la lista para ganar pews por mensajes."""
        try:
            if bot.economy_manager.add_points_channel(channel.id):
                embed = discord.Embed(
                    title="✓ Canal agregado",
                    description=f"{channel.mention} ha sido agregado a la lista de canales para ganar pews.",
                    color=0x00ff00
                )
                embed.add_field(name="💰 Recompensa", value="1.0₱ (pew) por cada 5 minutos hablando", inline=False)
                embed.add_field(name="📋 Canales activos", value=f"{len(bot.economy_manager.points_channels)} canales", inline=True)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    f"⚠ El canal {channel.mention} ya está en la lista de canales para ganar pews.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error al agregar canal: {e}")
            await interaction.response.send_message(
                f"❌ Error al agregar canal: {str(e)}",
                ephemeral=True
            )

    @bot.tree.command(name="remove_points_channel", description="Remueve un canal de la lista de canales para ganar pews")
    @app_commands.describe(channel="El canal a remover")
    @app_commands.checks.has_role(1181253292274221267)
    async def remove_points_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        """Remueve un canal de la lista para ganar pews."""
        try:
            if bot.economy_manager.remove_points_channel(channel.id):
                embed = discord.Embed(
                    title="✓ Canal removido",
                    description=f"{channel.mention} ha sido removido de la lista de canales para ganar pews.",
                    color=0xff6600
                )
                embed.add_field(name="📋 Canales activos", value=f"{len(bot.economy_manager.points_channels)} canales", inline=True)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    f"⚠ El canal {channel.mention} no está en la lista de canales para ganar pews.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error al remover canal: {e}")
            await interaction.response.send_message(
                f"❌ Error al remover canal: {str(e)}",
                ephemeral=True
            )

    @bot.tree.command(name="list_points_channels", description="Muestra la lista de canales para ganar pews")
    @app_commands.checks.has_role(1181253292274221267)
    async def list_points_channels(interaction: discord.Interaction):
        """Muestra todos los canales donde se pueden ganar pews."""
        if bot.points_channels:
            channel_mentions = []
            for channel_id_str in bot.points_channels:
                channel = bot.get_channel(int(channel_id_str))
                if channel:
                    channel_mentions.append(channel.mention)
                else:
                    channel_mentions.append(f"Canal desconocido (ID: {channel_id_str})")
            
            embed = discord.Embed(
                title="📋 Canales para ganar pews",
                description="\n".join(channel_mentions),
                color=0x0099ff
            )
            embed.add_field(
                name="💰 Sistema de pews",
                value=f"• {bot.economy_manager.get_points_per_interval()}₱ por cada {bot.economy_manager.points_interval // 60} minutos\n• Se cachean automáticamente\n• Se pueden verificar con /pews",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "⚠ No hay canales configurados para ganar pews.",
                ephemeral=True
            )

    @bot.tree.command(name="config_points", description="Configura la cantidad de puntos ganados por intervalo (solo moderación)")
    @app_commands.describe(cantidad="Cantidad de pews a ganar cada 5 minutos (puede ser decimal)")
    @app_commands.checks.has_role(1181253292274221267)
    async def config_points(interaction: discord.Interaction, cantidad: str):
        """Configura cuántos pews se ganan cada 5 minutos en canales de texto y voz."""
        try:
            # Parsear cantidad (permite decimales)
            amount = float(cantidad)
            
            if amount <= 0:
                await interaction.response.send_message(
                    "❌ La cantidad debe ser mayor a 0.",
                    ephemeral=True
                )
                return
            
            # Configurar puntos
            if bot.economy_manager.set_points_per_interval(amount):
                embed = discord.Embed(
                    title="✓ Ganancia de pews configurada",
                    description=f"Cantidad de pews por intervalo actualizada correctamente",
                    color=0x00ff00
                )
                embed.add_field(
                    name="💰 Nueva ganancia",
                    value=f"**{amount}₱** cada 5 minutos",
                    inline=False
                )
                embed.add_field(
                    name="📍 Aplicable en",
                    value="• Canales de texto configurados\n• Todos los canales de voz",
                    inline=False
                )
                embed.add_field(
                    name="📊 Resumen actual",
                    value=f"• Canales: {len(bot.economy_manager.points_channels)}\n• Usuarios en voz: {len(bot.economy_manager.voice_users)}\n• Estado: {'✅ Habilitado' if bot.economy_manager.points_enabled else '❌ Deshabilitado'}",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                # Enviar log
                await bot.send_log(
                    f"Configuración de puntos actualizada por {interaction.user.mention}\n"
                    f"Nueva ganancia: **{amount}₱** por intervalo de 5 minutos",
                    "INFO"
                )
            else:
                await interaction.response.send_message(
                    "❌ Error al configurar puntos.",
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(
                f"❌ '{cantidad}' no es un número válido. Usa un número o decimal (ej: 1, 2.5, 0.5)",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error en config_points: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @bot.tree.command(name="config_points_interval", description="Configura el intervalo de tiempo para ganar puntos (solo moderación)")
    @app_commands.describe(segundos="Intervalo en segundos")
    @app_commands.checks.has_role(1181253292274221267)
    async def config_points_interval(interaction: discord.Interaction, segundos: int):
        """Configura cada cuánto tiempo se ganan puntos (canales de texto y voz)."""
        try:
            # Configurar intervalo
            if bot.economy_manager.set_points_interval(segundos):
                minutos = segundos / 60
                
                embed = discord.Embed(
                    title="⏰ Intervalo de puntos configurado",
                    description=f"El intervalo de tiempo ha sido actualizado correctamente",
                    color=0x00ff00
                )
                embed.add_field(
                    name="⏱️ Nuevo intervalo",
                    value=f"**{segundos}** segundos ({minutos:.1f} minutos)",
                    inline=False
                )
                embed.add_field(
                    name="💰 Ganancia actual",
                    value=f"**{bot.economy_manager.get_points_per_interval()}₱** cada {minutos:.1f} minutos",
                    inline=False
                )
                embed.add_field(
                    name="📍 Aplicable en",
                    value="• Canales de texto configurados\n• Todos los canales de voz",
                    inline=False
                )
                embed.add_field(
                    name="📊 Resumen",
                    value=f"• Canales texto: {len(bot.economy_manager.points_channels)}\n• Usuarios en voz: {len(bot.economy_manager.voice_users)}\n• Estado: {'✅ Habilitado' if bot.economy_manager.points_enabled else '❌ Deshabilitado'}",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                # Enviar log
                await bot.send_log(
                    f"Intervalo de puntos actualizado por {interaction.user.mention}\n"
                    f"Nuevo intervalo: **{segundos}s** ({minutos:.1f} min)",
                    "INFO"
                )
            else:
                await interaction.response.send_message(
                    "❌ Error al configurar intervalo.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error en config_points_interval: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @bot.tree.command(name="dar", description="Transfiere pews a otro usuario (Discord/YouTube)")
    @app_commands.describe(usuario="Usuario de Discord (opcional)", busqueda="ID o nombre (opcional)", cantidad="Cantidad o 'all'")
    async def dar(interaction: discord.Interaction, usuario: discord.User | None = None, busqueda: str | None = None, cantidad: str = "0"):
        from backend.usermanager import get_user_points, add_points_to_user

        # Resolver objetivo
        target, target_id, target_name = await _resolver_objetivo_desde_parametros(interaction, usuario, busqueda)
        if target is None:
            await interaction.response.send_message("❌ Objetivo no encontrado. Usa un usuario de Discord o un ID/nombre válido.", ephemeral=True)
            return

        # Obtener puntos del donante (Discord actual)
        donante = get_user_points(interaction.user.id)
        puntos_donante = donante.get("puntos", 0) if donante else 0

        # Determinar cantidad
        if cantidad.lower() == "all":
            cantidad_val = puntos_donante
        else:
            try:
                cantidad_val = float(cantidad)
            except ValueError:
                await interaction.response.send_message("❌ La cantidad debe ser un número o 'all'.", ephemeral=True)
                return

        if cantidad_val <= 0:
            await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
            return
        if cantidad_val > puntos_donante:
            await interaction.response.send_message(f"❌ No tienes suficientes pews. Tienes {puntos_donante:.1f}₱.", ephemeral=True)
            return

        # Transferir
        donor_result = add_points_to_user(interaction.user.id, -cantidad_val)
        actualizado = add_points_to_user(target_id, cantidad_val)

        if actualizado and donor_result:
            puntos_finales = actualizado.get("puntos", 0)
            donor_final = donor_result.get("puntos", 0)
            # Log transferencias
            transaction_logger.log_transaction(
                user_id=str(interaction.user.id),
                username=interaction.user.name,
                platform="discord",
                transaction_type="transfer_send",
                amount=-cantidad_val,
                balance_after=donor_final
            )
            transaction_logger.log_transaction(
                user_id=str(target_id),
                username=target_name,
                platform="discord",
                transaction_type="transfer_receive",
                amount=cantidad_val,
                balance_after=puntos_finales
            )
            embed = discord.Embed(
                title="✓ Transferencia realizada",
                description=f"Has transferido **{cantidad_val:.1f}₱** a **{target_name}**\nAhora tiene **{puntos_finales:.1f}₱**",
                color=0x00CC66
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Error al transferir pews.", ephemeral=True)

    @bot.tree.command(name="rps", description="Resta pews a un usuario (solo moderación)")
    @app_commands.checks.has_role(1445991138837135553)
    @app_commands.describe(usuario="Usuario de Discord (opcional)", busqueda="ID o nombre (opcional)", cantidad="Cantidad o 'all'")
    async def quitar(interaction: discord.Interaction, usuario: discord.User | None = None, busqueda: str | None = None, cantidad: str = "0"):
        from backend.usermanager import get_user_points, add_points_to_user, cache_discord_user

        # Si no especifica usuario ni búsqueda, usar self
        if usuario is None and busqueda is None:
            target_id = interaction.user.id
            target_name = interaction.user.name
            target = get_user_points(target_id)
        else:
            # Resolver objetivo
            target, target_id, target_name = await _resolver_objetivo_desde_parametros(interaction, usuario, busqueda)
            if target is None:
                await interaction.response.send_message("❌ Objetivo no encontrado. Usa un usuario de Discord o un ID/nombre válido.", ephemeral=True)
                return

        # Obtener puntos actuales del objetivo
        info_obj = get_user_points(target_id)
        puntos_obj = info_obj.get("puntos", 0) if info_obj else 0

        # Determinar cantidad
        if cantidad.lower() == "all":
            cantidad_val = puntos_obj
        else:
            try:
                cantidad_val = float(cantidad)
            except ValueError:
                await interaction.response.send_message("❌ La cantidad debe ser un número o 'all'.", ephemeral=True)
                return

        if cantidad_val <= 0:
            await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
            return

        actualizado = add_points_to_user(target_id, -cantidad_val)
        if actualizado:
            puntos_finales = actualizado.get("puntos", 0)
            transaction_logger.log_transaction(
                user_id=str(target_id),
                username=target_name,
                platform="discord",
                transaction_type="punishment",
                amount=-cantidad_val,
                balance_after=puntos_finales
            )
            embed = discord.Embed(
                title="⚠ Puntos removidos",
                description=(
                    f"Se han removido **{cantidad_val:.1f}₱** a **{target_name}**\n"
                    f"Puntos actuales: **{puntos_finales:.1f}₱**"
                ),
                color=0xFF6600
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Error al remover pews.", ephemeral=True)

    @bot.tree.command(name="castigar", description="Castiga a un usuario removiendo pews (solo moderación)")
    @app_commands.checks.has_role(1445991138837135553)
    @app_commands.describe(usuario="Usuario de Discord (opcional)", busqueda="ID o nombre (opcional)", cantidad="Cantidad o 'all'")
    async def castigar(interaction: discord.Interaction, usuario: discord.User | None = None, busqueda: str | None = None, cantidad: str = "0"):
        """Castiga a un usuario removiendo pews y mostrando un mensaje público de castigo."""
        from backend.usermanager import get_user_points, add_points_to_user, cache_discord_user

        # Resolver objetivo
        target, target_id, target_name = await _resolver_objetivo_desde_parametros(interaction, usuario, busqueda)
        if target is None:
            await interaction.response.send_message("❌ Objetivo no encontrado. Usa un usuario de Discord o un ID/nombre válido.", ephemeral=True)
            return

        # Obtener puntos actuales del objetivo
        info_obj = get_user_points(target_id)
        puntos_obj = info_obj.get("puntos", 0) if info_obj else 0

        # Determinar cantidad
        if cantidad.lower() == "all":
            cantidad_val = max(puntos_obj, 0)  # Si es negativo, castiga 0; si es positivo, castiga todo
        else:
            try:
                cantidad_val = float(cantidad)
            except ValueError:
                await interaction.response.send_message("❌ La cantidad debe ser un número o 'all'.", ephemeral=True)
                return

        if cantidad_val <= 0:
            await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
            return

        actualizado = add_points_to_user(target_id, -cantidad_val)
        if actualizado:
            puntos_finales = actualizado.get("puntos", 0)
            transaction_logger.log_transaction(
                user_id=str(target_id),
                username=target_name,
                platform="discord",
                transaction_type="punishment",
                amount=-cantidad_val,
                balance_after=puntos_finales
            )
            embed = discord.Embed(
                title="⚡ Usuario Castigado",
                description=(
                    f"**{target_name}** ha sido castigado 🔨\n"
                    f"Se le han restado **{cantidad_val:.1f}₱**\n"
                    f"Pews restantes: **{puntos_finales:.1f}₱**"
                ),
                color=0xFF0000
            )
            embed.set_footer(text=f"Moderador: {interaction.user.name}")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Error al castigar al usuario.", ephemeral=True)

    @bot.tree.command(name="aps", description="Añade pews a un usuario (solo moderación)")
    @app_commands.checks.has_role(1445991138837135553)
    @app_commands.describe(usuario="Usuario de Discord (opcional)", busqueda="ID o nombre (opcional)", cantidad="Cantidad o 'all'")
    async def aps(interaction: discord.Interaction, usuario: discord.User | None = None, busqueda: str | None = None, cantidad: str = "0"):
        from backend.usermanager import get_user_points, add_points_to_user

        # Si no especifica usuario ni búsqueda, usar self
        if usuario is None and busqueda is None:
            target_id = interaction.user.id
            target_name = interaction.user.name
            target = get_user_points(target_id)
        else:
            # Resolver objetivo
            target, target_id, target_name = await _resolver_objetivo_desde_parametros(interaction, usuario, busqueda)
            if target is None:
                await interaction.response.send_message("❌ Objetivo no encontrado. Usa un usuario de Discord o un ID/nombre válido.", ephemeral=True)
                return

        # Determinar cantidad
        if cantidad.lower() == "all":
            # Igual que en YouTube: usar pews del emisor como referencia
            admin_info = get_user_points(interaction.user.id)
            admin_pews = admin_info.get("puntos", 0) if admin_info else 0
            cantidad_val = admin_pews
        else:
            try:
                cantidad_val = float(cantidad)
            except ValueError:
                await interaction.response.send_message("❌ La cantidad debe ser un número o 'all'.", ephemeral=True)
                return

        if cantidad_val <= 0:
            await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
            return

        actualizado = add_points_to_user(target_id, cantidad_val)
        if actualizado:
            puntos_finales = actualizado.get("puntos", 0)
            transaction_logger.log_transaction(
                user_id=str(target_id),
                username=target_name,
                platform="discord",
                transaction_type="reward",
                amount=cantidad_val,
                balance_after=puntos_finales
            )
            embed = discord.Embed(
                title="✓ Puntos añadidos",
                description=f"Se han añadido **{cantidad_val:.1f}₱** a **{target_name}**\nAhora tiene **{puntos_finales:.1f}₱**",
                color=0x00CC66
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Error al añadir pews.", ephemeral=True)

    @bot.tree.command(name="pews", description="Muestra los pews de un usuario (por defecto el tuyo)")
    @app_commands.describe(user="El usuario del cual ver pews (opcional)")
    async def pews(interaction: discord.Interaction, user: discord.User = None):
        """Muestra los pews del usuario especificado o del que ejecuta el comando.
        
        Si no especifica usuario: muestra mensaje privado "Tienes X₱"
        Si especifica usuario: muestra mensaje público "@user tiene X₱"
        """
        from backend.usermanager import get_user_points
        
        # Si no especifica usuario, usar el actual
        target_user = user if user else interaction.user
        is_self = target_user.id == interaction.user.id
        
        user_info = get_user_points(target_user.id)
        
        # Extraer los puntos del usuario, si no existe retorna 0
        points = user_info.get("puntos", 0) if user_info else 0
        
        if is_self:
            # Mensaje privado para el usuario consultando sus propios pews
            embed = discord.Embed(
                title="💰 Tus pews",
                description=f"Tienes **{points:.1f}₱**",
                color=0xffff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Mensaje público cuando consulta pews de otro usuario
            embed = discord.Embed(
                title="💰 Pews de usuario",
                description=f"{target_user.mention} tiene **{points:.1f}₱**",
                color=0xffff00
            )
            await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="top", description="Muestra el ranking de los 10 usuarios más ricos en pews")
    async def top_ranking(interaction: discord.Interaction):
        """Muestra un top 10 de usuarios por cantidad de pews."""
        from backend.usermanager import load_user_cache
        
        user_cache = load_user_cache()
        users = user_cache.get("users", [])
        
        # Ordenar usuarios por puntos de mayor a menor
        users_sorted = sorted(users, key=lambda x: x.get("puntos", 0), reverse=True)
        
        # Tomar top 10
        top_10 = users_sorted[:10]
        
        # Encontrar posición del usuario actual
        user_position = None
        user_points = 0
        for idx, user in enumerate(users_sorted, 1):
            if user.get("discord_id") == str(interaction.user.id):
                user_position = idx
                user_points = user.get("puntos", 0)
                break
        
        # Crear embed principal con color dorado
        embed = discord.Embed(
            title="💰 Magnates del Pew 💰",
            description="━━━━━━━━━━━━━━━━━━━━━━\n**Los 10 usuarios más ricos**",
            color=0xFFD700  # Dorado
        )
        
        # Construir el ranking con formato mejorado
        ranking_lines = []
        
        for idx, user in enumerate(top_10, 1):
            name = user.get("name", "Usuario desconocido")
            user_id = user.get("id")
            points = user.get("puntos", 0)
            
            # Número de posición
            position_icon = f"`#{idx:02d}`"
            
            # Siempre priorizar Discord si está disponible (aunque tenga YouTube también)
            if user.get("discord_id"):
                discord_id = int(user.get("discord_id"))
                display_name = f"<@{discord_id}>"
            else:
                # Solo YouTube
                display_name = f"**{name}**"
            
            # Formato mejorado con separador y alineación (más espacio entre ID y pews)
            line = f"{position_icon} {display_name}\n    └─ `ID:{user_id}`  •  **{points:.1f}₱**"
            ranking_lines.append(line)
        
        embed.add_field(
            name="",
            value="\n".join(ranking_lines),
            inline=False
        )
        
        # Footer mejorado con información del usuario
        if user_position:
            if user_position <= 10:
                footer_text = f"🎉 ¡Estás en el top 10! • Posición: #{user_position} • Puntos: {user_points:.1f}₱"
            else:
                footer_text = f"Tu posición: #{user_position} • Puntos: {user_points:.1f}₱"
        else:
            footer_text = "❌ No estás en el ranking"
        
        embed.set_footer(text=footer_text)
        embed.add_field(
            name="",
            value="━━━━━━━━━━━━━━━━━━━━━━",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="gamble", description="Apuesta pews para ganar o perder. Alias: /g")
    @app_commands.describe(cantidad="Cantidad de pews a apostar o 'all'")
    async def gamble(interaction: discord.Interaction, cantidad: str):
        """Apuesta pews con posibilidad de ganar hasta 4x lo apostado."""
        from backend.usermanager import get_user_points, add_points_to_user, cache_discord_user
        from activities.Jackpot import calculate_gamble_result, validate_gamble, get_gamble_summary
        from backend.config import GAMBLE_MAX_BET
        
        # Asegurar que el usuario existe en la caché
        cache_discord_user(
            discord_id=interaction.user.id,
            name=interaction.user.name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )
        
        # Obtener puntos actuales
        user_info = get_user_points(interaction.user.id)
        puntos_actuales = user_info.get("puntos", 0) if user_info else 0
        
        # Determinar cantidad a apostar (permite decimales, 2 dígitos)
        if cantidad.lower() == "all":
            bet_amount = round(float(puntos_actuales), 2)
        else:
            try:
                bet_amount = round(float(cantidad), 2)
            except ValueError:
                await interaction.response.send_message(
                    "❌ Cantidad inválida. Usa un número o 'all'.",
                    ephemeral=True
                )
                return
        
        # Validar límite máximo de apuesta
        if bet_amount > GAMBLE_MAX_BET:
            await interaction.response.send_message(
                f"❌ El límite máximo de apuesta es **{GAMBLE_MAX_BET:,}₱**. Intentaste apostar **{bet_amount:,.2f}₱**.",
                ephemeral=True
            )
            return
        
        # Validar apuesta
        es_valido, mensaje_error = validate_gamble(puntos_actuales, bet_amount)
        if not es_valido:
            await interaction.response.send_message(mensaje_error, ephemeral=True)
            return
        
        # Calcular resultado
        roll, ganancia_neta, multiplicador, rango = calculate_gamble_result(bet_amount)
        
        # Actualizar puntos
        add_points_to_user(interaction.user.id, ganancia_neta)
        puntos_finales = round(puntos_actuales + ganancia_neta, 2)
        
        # Obtener resumen formateado
        summary = get_gamble_summary(
            username=interaction.user.name,
            bet_amount=bet_amount,
            roll=roll,
            ganancia_neta=ganancia_neta,
            multiplicador=multiplicador,
            rango=rango,
            puntos_finales=puntos_finales
        )
        
        # Determinar color del embed
        if summary["color"] == "verde":
            embed_color = 0x00FF00  # Verde
        elif summary["color"] == "amarillo":
            embed_color = 0xFFFF00  # Amarillo
        else:
            embed_color = 0xFF0000  # Rojo
        
        # Crear embed con resultado
        embed = discord.Embed(
            title=f"🎰 {summary['resultado_emoji']} Resultado del Gamble",
            color=embed_color
        )
        
        embed.add_field(
            name="🎲 Número Obtenido",
            value=f"**{roll}** / 100",
            inline=True
        )
        
        embed.add_field(
            name="💰 Apuesta",
            value=f"**{bet_amount:,.2f}₱**",
            inline=True
        )
        
        embed.add_field(
            name="📊 Multiplicador",
            value=f"**{multiplicador:.1f}x**",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Categoría",
            value=rango,
            inline=False
        )
        
        embed.add_field(
            name="💵 Ganancia/Pérdida",
            value=f"**{summary['ganancia_texto']}₱**",
            inline=True
        )
        
        embed.add_field(
            name="🏦 Saldo Final",
            value=f"**{puntos_finales:,.2f}₱**",
            inline=True
        )
        
        embed.set_footer(text=f"Jugador: {interaction.user.name}")
        embed.timestamp = datetime.now(timezone.utc)
        
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="g", description="Alias de /gamble - Apuesta pews para ganar o perder")
    @app_commands.describe(cantidad="Cantidad de pews a apostar o 'all'")
    async def g(interaction: discord.Interaction, cantidad: str):
        """Alias corto del comando gamble."""
        from backend.usermanager import get_user_points, add_points_to_user, cache_discord_user
        from activities.Jackpot import calculate_gamble_result, validate_gamble, get_gamble_summary
        from backend.config import GAMBLE_MAX_BET
        
        # Asegurar que el usuario existe en la caché
        cache_discord_user(
            discord_id=interaction.user.id,
            name=interaction.user.name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )
        
        # Obtener puntos actuales
        user_info = get_user_points(interaction.user.id)
        puntos_actuales = user_info.get("puntos", 0) if user_info else 0
        
        # Determinar cantidad a apostar (permite decimales, 2 dígitos)
        if cantidad.lower() == "all":
            bet_amount = round(float(puntos_actuales), 2)
        else:
            try:
                bet_amount = round(float(cantidad), 2)
            except ValueError:
                await interaction.response.send_message(
                    "❌ Cantidad inválida. Usa un número o 'all'.",
                    ephemeral=True
                )
                return
        
        # Validar apuesta (incluye límite máximo)
        es_valido, mensaje_error = validate_gamble(puntos_actuales, bet_amount, GAMBLE_MAX_BET)
        if not es_valido:
            await interaction.response.send_message(mensaje_error, ephemeral=True)
            return
        
        # Calcular resultado
        roll, ganancia_neta, multiplicador, rango = calculate_gamble_result(bet_amount)
        
        # Actualizar puntos
        add_points_to_user(interaction.user.id, ganancia_neta)
        puntos_finales = round(puntos_actuales + ganancia_neta, 2)
        transaction_logger.log_transaction(
            user_id=str(interaction.user.id),
            username=interaction.user.name,
            platform="discord",
            transaction_type="gamble_win" if ganancia_neta > 0 else "gamble_loss",
            amount=ganancia_neta,
            balance_after=puntos_finales
        )
        
        # Obtener resumen formateado
        summary = get_gamble_summary(
            username=interaction.user.name,
            bet_amount=bet_amount,
            roll=roll,
            ganancia_neta=ganancia_neta,
            multiplicador=multiplicador,
            rango=rango,
            puntos_finales=puntos_finales
        )
        
        # Determinar color del embed
        if summary["color"] == "verde":
            embed_color = 0x00FF00  # Verde
        elif summary["color"] == "amarillo":
            embed_color = 0xFFFF00  # Amarillo
        else:
            embed_color = 0xFF0000  # Rojo
        
        # Crear embed con resultado
        embed = discord.Embed(
            title=f"🎰 {summary['resultado_emoji']} Resultado del Gamble",
            color=embed_color
        )
        
        embed.add_field(
            name="🎲 Número Obtenido",
            value=f"**{roll}** / 100",
            inline=True
        )
        
        embed.add_field(
            name="💰 Apuesta",
            value=f"**{bet_amount:,.2f}₱**",
            inline=True
        )
        
        embed.add_field(
            name="📊 Multiplicador",
            value=f"**{multiplicador:.1f}x**",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Categoría",
            value=rango,
            inline=False
        )
        
        embed.add_field(
            name="💵 Ganancia/Pérdida",
            value=f"**{summary['ganancia_texto']}₱**",
            inline=True
        )
        
        embed.add_field(
            name="🏦 Saldo Final",
            value=f"**{puntos_finales:,.2f}₱**",
            inline=True
        )
        
        embed.set_footer(text=f"Jugador: {interaction.user.name}")
        embed.timestamp = datetime.now(timezone.utc)
        
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="tragamonedas", description="Juega a la máquina tragamonedas. Alias: /tm")
    @app_commands.describe(cantidad="Cantidad de pews a apostar o 'all'")
    async def tragamonedas(interaction: discord.Interaction, cantidad: str):
        """Juega a la máquina tragamonedas 🎰 con posibilidades de ganar hasta 5000% de tu apuesta."""
        from backend.usermanager import get_user_points, add_points_to_user, cache_discord_user
        from activities.Jackpot import spin_slots, get_slot_summary, validate_gamble, increment_user_luck_multiplier, reset_user_luck_multiplier
        from backend.config import TRAGAMONEDAS_MAX_BET
        
        # Asegurar que el usuario existe en la caché
        cache_discord_user(
            discord_id=interaction.user.id,
            name=interaction.user.name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )
        
        # Obtener puntos actuales
        user_info = get_user_points(interaction.user.id)
        puntos_actuales = user_info.get("puntos", 0) if user_info else 0
        
        # Determinar cantidad a apostar
        if cantidad.lower() == "all":
            bet_amount = int(puntos_actuales)
        else:
            try:
                bet_amount = int(float(cantidad))
            except ValueError:
                await interaction.response.send_message(
                    "❌ Cantidad inválida. Usa un número o 'all'.",
                    ephemeral=True
                )
                return
        
        # Validar apuesta (incluye límite máximo)
        es_valido, mensaje_error = validate_gamble(puntos_actuales, bet_amount, TRAGAMONEDAS_MAX_BET)
        if not es_valido:
            await interaction.response.send_message(mensaje_error, ephemeral=True)
            return
        
        # Realizar spin
        combo, ganancia_neta, multiplicador, descripcion, es_ganancia, luck_multiplier = spin_slots(bet_amount, str(interaction.user.id))
        
        # Actualizar puntos
        add_points_to_user(interaction.user.id, ganancia_neta)
        puntos_finales = puntos_actuales + ganancia_neta
        
        # Actualizar multiplicador de suerte
        if es_ganancia:
            reset_user_luck_multiplier(str(interaction.user.id))
        else:
            increment_user_luck_multiplier(str(interaction.user.id), 0.1)
        
        # Obtener resumen formateado
        summary = get_slot_summary(
            username=interaction.user.name,
            bet_amount=bet_amount,
            combo=combo,
            ganancia_neta=ganancia_neta,
            multiplicador=multiplicador,
            descripcion=descripcion,
            es_ganancia=es_ganancia,
            luck_multiplier=luck_multiplier,
            puntos_finales=puntos_finales
        )
        
        # Determinar color del embed según tipo de resultado
        if summary["color"] == "verde":
            embed_color = 0x00FF00  # Verde para X3
        elif summary["color"] == "amarillo":
            embed_color = 0xFFFF00  # Amarillo para X2 (consuelo)
        else:
            embed_color = 0xFF0000  # Rojo para pérdidas
        
        # Crear embed simple y limpio
        embed = discord.Embed(
            title="Tragamonedas",
            color=embed_color,
            description=f"{combo[0]} {combo[1]} {combo[2]}"
        )
        
        embed.add_field(
            name="Línea",
            value=summary['descripcion'],
            inline=False
        )
        
        embed.add_field(
            name="Apuesta",
            value=f"{bet_amount:,}₱",
            inline=True
        )
        
        embed.add_field(
            name=summary['ganancia_perdida_label'],
            value=summary['ganancia_perdida_texto'] + "₱",
            inline=True
        )
        
        embed.add_field(
            name="Saldo",
            value=f"{puntos_finales:,}₱",
            inline=True
        )
        
        embed.set_footer(text=f"@{interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="tm", description="Alias de /tragamonedas - Juega a la máquina tragamonedas")
    @app_commands.describe(cantidad="Cantidad de pews a apostar o 'all'")
    async def tm(interaction: discord.Interaction, cantidad: str):
        """Alias corto del comando tragamonedas."""
        from backend.usermanager import get_user_points, add_points_to_user, cache_discord_user
        from activities.Jackpot import spin_slots, get_slot_summary, validate_gamble, increment_user_luck_multiplier, reset_user_luck_multiplier
        from backend.config import TRAGAMONEDAS_MAX_BET
        
        # Asegurar que el usuario existe en la caché
        cache_discord_user(
            discord_id=interaction.user.id,
            name=interaction.user.name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )
        
        # Obtener puntos actuales
        user_info = get_user_points(interaction.user.id)
        puntos_actuales = user_info.get("puntos", 0) if user_info else 0
        
        # Determinar cantidad a apostar
        if cantidad.lower() == "all":
            bet_amount = int(puntos_actuales)
        else:
            try:
                bet_amount = int(float(cantidad))
            except ValueError:
                await interaction.response.send_message(
                    "❌ Cantidad inválida. Usa un número o 'all'.",
                    ephemeral=True
                )
                return
        
        # Validar apuesta (incluye límite máximo)
        es_valido, mensaje_error = validate_gamble(puntos_actuales, bet_amount, TRAGAMONEDAS_MAX_BET)
        if not es_valido:
            await interaction.response.send_message(mensaje_error, ephemeral=True)
            return
        
        # Realizar spin
        combo, ganancia_neta, multiplicador, descripcion, es_ganancia, luck_multiplier = spin_slots(bet_amount, str(interaction.user.id))
        
        # Actualizar puntos
        add_points_to_user(interaction.user.id, ganancia_neta)
        puntos_finales = puntos_actuales + ganancia_neta
        
        # Actualizar multiplicador de suerte
        if es_ganancia:
            reset_user_luck_multiplier(str(interaction.user.id))
        else:
            increment_user_luck_multiplier(str(interaction.user.id), 0.1)
        
        # Obtener resumen formateado
        summary = get_slot_summary(
            username=interaction.user.name,
            bet_amount=bet_amount,
            combo=combo,
            ganancia_neta=ganancia_neta,
            multiplicador=multiplicador,
            descripcion=descripcion,
            es_ganancia=es_ganancia,
            luck_multiplier=luck_multiplier,
            puntos_finales=puntos_finales
        )
        
        # Determinar color del embed según tipo de resultado
        if summary["color"] == "verde":
            embed_color = 0x00FF00  # Verde para X3
        elif summary["color"] == "amarillo":
            embed_color = 0xFFFF00  # Amarillo para X2 (consuelo)
        else:
            embed_color = 0xFF0000  # Rojo para pérdidas
        
        # Crear embed simple y limpio
        embed = discord.Embed(
            title="Tragamonedas",
            color=embed_color,
            description=f"{combo[0]} {combo[1]} {combo[2]}"
        )
        
        embed.add_field(
            name="Línea",
            value=summary['descripcion'],
            inline=False
        )
        
        embed.add_field(
            name="Apuesta",
            value=f"{bet_amount:,}₱",
            inline=True
        )
        
        embed.add_field(
            name=summary['ganancia_perdida_label'],
            value=summary['ganancia_perdida_texto'] + "₱",
            inline=True
        )
        
        embed.add_field(
            name="Saldo",
            value=f"{puntos_finales:,}₱",
            inline=True
        )
        
        embed.set_footer(text=f"@{interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    async def play_ppt_game(interaction: discord.Interaction, rival: discord.User, bet_amount: int, is_rematch: bool = False):
        """Función auxiliar que ejecuta el juego de Piedra Papel Tijeras."""
        from backend.usermanager import get_user_points, add_points_to_user, cache_discord_user
        from activities.Jackpot import validate_ppt_game, determine_ppt_winner, get_ppt_emoji
        
        # Asegurar que ambos usuarios estén en caché
        cache_discord_user(
            discord_id=interaction.user.id,
            name=interaction.user.name,
            avatar_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )
        cache_discord_user(
            discord_id=rival.id,
            name=rival.name,
            avatar_url=rival.display_avatar.url if rival.display_avatar else None
        )
        
        # Obtener puntos actuales
        player1_info = get_user_points(interaction.user.id)
        player1_points = player1_info.get("puntos", 0) if player1_info else 0
        
        player2_info = get_user_points(rival.id)
        player2_points = player2_info.get("puntos", 0) if player2_info else 0
        
        # Validar apuesta
        es_valido, mensaje_error = validate_ppt_game(player1_points, player2_points, bet_amount)
        if not es_valido:
            if is_rematch:
                await interaction.followup.send(mensaje_error, ephemeral=True)
            else:
                await interaction.response.send_message(mensaje_error, ephemeral=True)
            return
        
        # ====== FASE 1: Jugador 1 elige (privado) ======
        view_player1 = PPTView(allowed_user_id=interaction.user.id, timeout=180)
        
        embed_player1 = discord.Embed(
            title="🎮 Piedra, Papel o Tijeras",
            description=f"**Desafío contra {rival.mention}**\n\n💰 Apuesta: **{bet_amount:,}₱**\n\n🔒 Solo tú puedes ver este mensaje.\nElige tu opción:",
            color=0x5865F2
        )
        embed_player1.set_footer(text="⏱️ Tienes 3 minutos para elegir")
        
        if is_rematch:
            await interaction.followup.send(embed=embed_player1, view=view_player1, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed_player1, view=view_player1, ephemeral=True)
        
        # Esperar elección del jugador 1
        await view_player1.wait()
        
        if view_player1.timed_out or view_player1.choice is None:
            await interaction.followup.send("⏱️ **Tiempo agotado.** El juego ha sido cancelado.", ephemeral=True)
            return
        
        player1_choice = view_player1.choice
        
        # ====== FASE 2: Jugador 2 elige (público) ======
        view_player2 = PPTView(allowed_user_id=rival.id, timeout=180)
        
        embed_player2 = discord.Embed(
            title="⚔️ ¡Duelo de Piedra, Papel o Tijeras!",
            description=f"{interaction.user.mention} te ha retado a un duelo\n\n💰 **Apuesta:** {bet_amount:,}₱ cada uno\n⏱️ **Tiempo:** 3 minutos\n\n{rival.mention}, elige tu opción:",
            color=0xFEE75C
        )
        embed_player2.set_thumbnail(url=rival.display_avatar.url if rival.display_avatar else None)
        embed_player2.set_footer(text=f"Desafío iniciado por {interaction.user.name}")
        
        # Enviar mensaje público
        public_message = await interaction.followup.send(embed=embed_player2, view=view_player2, wait=True)
        
        # Esperar elección del jugador 2
        await view_player2.wait()
        
        if view_player2.timed_out or view_player2.choice is None:
            embed_timeout = discord.Embed(
                title="⏱️ Tiempo Agotado",
                description=f"{rival.mention} no respondió a tiempo.\n\nEl duelo ha sido cancelado.",
                color=0xFF6600
            )
            await public_message.edit(embed=embed_timeout, view=None)
            return
        
        player2_choice = view_player2.choice
        
        # ====== FASE 3: Re-validar puntos (anti-exploit) ======
        player1_info_final = get_user_points(interaction.user.id)
        player1_points_final = player1_info_final.get("puntos", 0) if player1_info_final else 0
        
        player2_info_final = get_user_points(rival.id)
        player2_points_final = player2_info_final.get("puntos", 0) if player2_info_final else 0
        
        if player1_points_final < bet_amount or player2_points_final < bet_amount:
            embed_error = discord.Embed(
                title="❌ Juego Anulado",
                description="Uno de los jugadores no tiene suficientes puntos.",
                color=0xFF0000
            )
            await public_message.edit(embed=embed_error, view=None)
            return
        
        # ====== FASE 4: Determinar ganador ======
        winner, resultado_texto = determine_ppt_winner(player1_choice, player2_choice)
        
        emoji1 = get_ppt_emoji(player1_choice)
        emoji2 = get_ppt_emoji(player2_choice)
        
        # ====== FASE 5: Procesar resultado ======
        if winner == 0:  # Empate
            embed_resultado = discord.Embed(
                title="🤝 ¡Empate!",
                description=f"{interaction.user.mention} y {rival.mention} han empatado su duelo\n\n{resultado_texto}",
                color=0xFEE75C
            )
            embed_resultado.add_field(
                name=f"🎯 {interaction.user.display_name}",
                value=f"{emoji1} **{player1_choice.capitalize()}**",
                inline=True
            )
            embed_resultado.add_field(
                name=f"🎯 {rival.display_name}",
                value=f"{emoji2} **{player2_choice.capitalize()}**",
                inline=True
            )
            embed_resultado.add_field(
                name="💰 Resultado",
                value=f"Cada uno conserva sus **{bet_amount:,}₱**",
                inline=False
            )
            
        elif winner == 1:  # Gana player1
            p2_result = add_points_to_user(rival.id, -bet_amount)
            p1_result = add_points_to_user(interaction.user.id, bet_amount)
            if p1_result and p2_result:
                transaction_logger.log_transaction(
                    user_id=str(rival.id),
                    username=rival.name,
                    platform="discord",
                    transaction_type="ppt_loss",
                    amount=-bet_amount,
                    balance_after=p2_result.get("puntos", 0)
                )
                transaction_logger.log_transaction(
                    user_id=str(interaction.user.id),
                    username=interaction.user.name,
                    platform="discord",
                    transaction_type="ppt_win",
                    amount=bet_amount,
                    balance_after=p1_result.get("puntos", 0)
                )
            
            embed_resultado = discord.Embed(
                title="🏆 ¡Victoria!",
                description=f"{interaction.user.mention} ha ganado el duelo contra {rival.mention}\n\n{resultado_texto}",
                color=0x57F287
            )
            embed_resultado.add_field(
                name=f"👑 {interaction.user.display_name} (Ganador)",
                value=f"{emoji1} **{player1_choice.capitalize()}**",
                inline=True
            )
            embed_resultado.add_field(
                name=f"💔 {rival.display_name}",
                value=f"{emoji2} **{player2_choice.capitalize()}**",
                inline=True
            )
            embed_resultado.add_field(
                name="💰 Recompensa",
                value=f"{interaction.user.mention} gana **+{bet_amount:,}₱**\n{rival.mention} pierde **-{bet_amount:,}₱**",
                inline=False
            )
            
        else:  # Gana player2
            p1_result = add_points_to_user(interaction.user.id, -bet_amount)
            p2_result = add_points_to_user(rival.id, bet_amount)
            if p1_result and p2_result:
                transaction_logger.log_transaction(
                    user_id=str(interaction.user.id),
                    username=interaction.user.name,
                    platform="discord",
                    transaction_type="ppt_loss",
                    amount=-bet_amount,
                    balance_after=p1_result.get("puntos", 0)
                )
                transaction_logger.log_transaction(
                    user_id=str(rival.id),
                    username=rival.name,
                    platform="discord",
                    transaction_type="ppt_win",
                    amount=bet_amount,
                    balance_after=p2_result.get("puntos", 0)
                )
            
            embed_resultado = discord.Embed(
                title="🏆 ¡Victoria!",
                description=f"{rival.mention} ha ganado el duelo contra {interaction.user.mention}\n\n{resultado_texto}",
                color=0x57F287
            )
            embed_resultado.add_field(
                name=f"👑 {rival.display_name} (Ganador)",
                value=f"{emoji2} **{player2_choice.capitalize()}**",
                inline=True
            )
            embed_resultado.add_field(
                name=f"💔 {interaction.user.display_name}",
                value=f"{emoji1} **{player1_choice.capitalize()}**",
                inline=True
            )
            embed_resultado.add_field(
                name="💰 Recompensa",
                value=f"{rival.mention} gana **+{bet_amount:,}₱**\n{interaction.user.mention} pierde **-{bet_amount:,}₱**",
                inline=False
            )
        
        embed_resultado.set_footer(text="🎮 Piedra, Papel o Tijeras")
        
        # ====== FASE 6: Ofrecer revancha ======
        # Verificar que ambos jugadores tengan puntos para la revancha
        player1_points_after = get_user_points(interaction.user.id).get("puntos", 0) if get_user_points(interaction.user.id) else 0
        player2_points_after = get_user_points(rival.id).get("puntos", 0) if get_user_points(rival.id) else 0
        
        if player1_points_after >= bet_amount and player2_points_after >= bet_amount:
            # Ambos tienen puntos, ofrecer revancha
            rematch_view = PPTRematchView(player1_id=interaction.user.id, player2_id=rival.id, timeout=60)
            embed_resultado.add_field(
                name="🔄 Revancha",
                value="¿Quieren jugar de nuevo? Cualquiera puede iniciar la revancha",
                inline=False
            )
            await public_message.edit(embed=embed_resultado, view=rematch_view)
            
            # Esperar si aceptan la revancha
            await rematch_view.wait()
            
            if rematch_view.rematch_accepted and not rematch_view.timed_out:
                # Iniciar nueva partida
                await play_ppt_game(interaction, rival, bet_amount, is_rematch=True)
            else:
                # Eliminar botón de revancha si expiró o no se aceptó
                await public_message.edit(embed=embed_resultado, view=None)
        else:
            # No tienen puntos suficientes, solo mostrar resultado
            await public_message.edit(embed=embed_resultado, view=None)

    @bot.tree.command(name="ppt", description="Piedra Papel Tijeras - Juega y apuesta pews")
    @app_commands.describe(
        rival="Usuario rival a desafiar",
        cantidad="Cantidad de pews a apostar"
    )
    async def ppt(interaction: discord.Interaction, rival: discord.User, cantidad: str):
        """Juega Piedra Papel Tijeras contra otro usuario y apuesta pews."""
        # Evitar jugar contra sí mismo
        if rival.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes jugar contra ti mismo.", ephemeral=True)
            return
        
        # Parsear cantidad
        try:
            bet_amount = int(float(cantidad))
        except ValueError:
            await interaction.response.send_message("❌ La cantidad debe ser un número.", ephemeral=True)
            return
        
        # Llamar a la función del juego
        await play_ppt_game(interaction, rival, bet_amount, is_rematch=False)

    @bot.tree.command(name="piedra_papel_tijeras", description="Piedra Papel Tijeras - Juega y apuesta pews")
    @app_commands.describe(
        rival="Usuario rival a desafiar",
        cantidad="Cantidad de pews a apostar"
    )
    async def ppt_full(interaction: discord.Interaction, rival: discord.User, cantidad: str):
        """Alias del comando /ppt"""
        # Evitar jugar contra sí mismo
        if rival.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes jugar contra ti mismo.", ephemeral=True)
            return
        
        # Parsear cantidad
        try:
            bet_amount = int(float(cantidad))
        except ValueError:
            await interaction.response.send_message("❌ La cantidad debe ser un número.", ephemeral=True)
            return
        
        # Llamar a la función del juego
        await play_ppt_game(interaction, rival, bet_amount, is_rematch=False)

    @bot.tree.command(name="id", description="Muestra tu ID o busca un usuario por ID/nombre/usuario de Discord")
    @app_commands.describe(
        usuario="Usuario de Discord para buscar (opcional)",
        busqueda="ID de usuario o nombre para buscar (opcional)"
    )
    async def id_command(interaction: discord.Interaction, usuario: discord.User = None, busqueda: str = None):
        """Muestra el ID del usuario o busca usuarios por ID/nombre/usuario de Discord.
        
        Sin parámetros: muestra tu propio ID y plataformas
        Con usuario de Discord: busca ese usuario específico de Discord
        Con ID numérico: muestra el nombre del usuario con ese ID
        Con nombre: muestra el ID del usuario con ese nombre
        """
        from backend.usermanager import load_user_cache
        
        user_cache = load_user_cache()
        users = user_cache.get("users", [])
        
        # CASO 1: Buscar por usuario de Discord específico
        if usuario:
            discord_id_str = str(usuario.id)
            usuario_encontrado = None
            
            for user in users:
                if user.get("discord_id") == discord_id_str:
                    usuario_encontrado = user
                    break
            
            if usuario_encontrado:
                user_id = usuario_encontrado.get("id")
                nombre = usuario_encontrado.get("name", "Usuario desconocido")
                
                # Determinar plataformas
                plataformas = []
                if usuario_encontrado.get("discord_id"):
                    plataformas.append("Discord")
                if usuario_encontrado.get("youtube_id"):
                    plataformas.append("YouTube")
                
                plataformas_texto = " + ".join(plataformas) if plataformas else "Ninguna"
                
                embed = discord.Embed(
                    title="🔍 Usuario encontrado",
                    description=f"**{usuario.mention}** → **{nombre}**",
                    color=0x00FF00
                )
                embed.add_field(name="🆔 ID Universal", value=f"**{user_id}**", inline=True)
                embed.add_field(name="🌐 Plataformas", value=plataformas_texto, inline=True)
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Usuario no registrado",
                    description=f"Este usuario de Discord ({usuario.mention}) aún no se encuentra registrado en el sistema.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # CASO 2: Sin parámetros - mostrar ID propio
        if not busqueda:
            discord_id_str = str(interaction.user.id)
            usuario_actual = None
            
            for user in users:
                if user.get("discord_id") == discord_id_str:
                    usuario_actual = user
                    break
            
            if usuario_actual:
                user_id = usuario_actual.get("id")
                
                # Determinar plataformas
                plataformas = []
                if usuario_actual.get("discord_id"):
                    plataformas.append("Discord")
                if usuario_actual.get("youtube_id"):
                    plataformas.append("YouTube")
                
                plataformas_texto = " + ".join(plataformas) if plataformas else "Ninguna"
                
                embed = discord.Embed(
                    title="🆔 Tu ID",
                    description=f"Tu número de ID es: **{user_id}**",
                    color=0x5865F2
                )
                embed.add_field(name="🌐 Plataformas vinculadas", value=plataformas_texto, inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="No se pudo encontrar tu ID en el sistema.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # CASO 3: Con búsqueda por ID o nombre
            usuario_encontrado = None
            
            # Verificar si es un ID (número) o nombre
            if busqueda.isdigit():
                # Buscar por ID universal
                for user in users:
                    if str(user.get("id")) == busqueda:
                        usuario_encontrado = user
                        break
                
                if usuario_encontrado:
                    nombre = usuario_encontrado.get("name", "Usuario desconocido")
                    
                    # Determinar plataformas
                    plataformas = []
                    if usuario_encontrado.get("discord_id"):
                        plataformas.append("Discord")
                    if usuario_encontrado.get("youtube_id"):
                        plataformas.append("YouTube")
                    
                    plataformas_texto = " + ".join(plataformas) if plataformas else "Ninguna"
                    
                    embed = discord.Embed(
                        title="🔍 Usuario encontrado",
                        description=f"El usuario con ID **{busqueda}** es: **{nombre}**",
                        color=0x00FF00
                    )
                    embed.add_field(name="🌐 Plataformas", value=plataformas_texto, inline=False)
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = discord.Embed(
                        title="❌ No encontrado",
                        description=f"No se encontró ningún usuario con el ID: **{busqueda}**",
                        color=0xFF0000
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # Buscar por nombre (case-insensitive)
                busqueda_lower = busqueda.lower()
                for user in users:
                    if user.get("name", "").lower() == busqueda_lower:
                        usuario_encontrado = user
                        break
                
                if usuario_encontrado:
                    user_id = usuario_encontrado.get("id")
                    nombre = usuario_encontrado.get("name")
                    
                    # Determinar plataformas
                    plataformas = []
                    if usuario_encontrado.get("discord_id"):
                        plataformas.append("Discord")
                    if usuario_encontrado.get("youtube_id"):
                        plataformas.append("YouTube")
                    
                    plataformas_texto = " + ".join(plataformas) if plataformas else "Ninguna"
                    
                    embed = discord.Embed(
                        title="🔍 Usuario encontrado",
                        description=f"El usuario **{nombre}** tiene el ID: **{user_id}**",
                        color=0x00FF00
                    )
                    embed.add_field(name="🌐 Plataformas", value=plataformas_texto, inline=False)
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = discord.Embed(
                        title="❌ No encontrado",
                        description=f"No se encontró ningún usuario con el nombre: **{busqueda}**",
                        color=0xFF0000
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="vincular", description="Vincula tu cuenta de Discord con tu cuenta de YouTube")
    async def vincular(interaction: discord.Interaction):
        """Inicia el proceso de vinculación con YouTube.
        
        Genera un código único de 10 minutos para vincular con YouTube.
        El usuario debe escribir !vincular <código> en YouTube chat.
        """
        from backend.usermanager import cache_discord_user, load_user_cache
        import os
        
        # IMPORTANTE: Cachear el usuario de Discord primero
        avatar_url = None
        if interaction.user.avatar:
            avatar_url = interaction.user.avatar.url
        
        cache_discord_user(
            discord_id=interaction.user.id,
            name=interaction.user.name,
            avatar_url=avatar_url
        )
        print(f"✓ Usuario Discord cacheado para vinculación: {interaction.user.name} ({interaction.user.id})")

        # Si ya está vinculado, avisar y no generar código nuevo
        user_cache = load_user_cache()
        existing = next(
            (u for u in user_cache.get("users", []) if u.get("discord_id") == str(interaction.user.id) and u.get("youtube_id")),
            None
        )
        if existing:
            yt_name = existing.get("name", "YouTube")
            yt_id = existing.get("youtube_id", "")
            embed = discord.Embed(
                title="🔗 Ya estás vinculado",
                description=f"Tu cuenta de Discord ya está unida a **{yt_name}** (YouTube).\nID YouTube: **{yt_id}**",
                color=0x00FF00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Usar la carpeta 'data/' común (no discordbot/data/)
        common_data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        
        # Crear instancia del AccountLinkingManager
        linking_manager = AccountLinkingManager(common_data_dir)
        
        # Generar código único
        code = linking_manager.create_pending_link(
            discord_id=interaction.user.id,
            discord_name=interaction.user.name,
            timeout_seconds=600  # 10 minutos
        )
        
        embed = discord.Embed(
            title="🔗 Vinculación de Cuentas",
            description="Sigue estos pasos para vincular tu cuenta de YouTube:",
            color=0xFF0000  # Color YouTube rojo
        )
        embed.add_field(
            name="1️⃣ Tu código único",
            value=f"```\n{code}\n```",
            inline=False
        )
        embed.add_field(
            name="2️⃣ En YouTube chat, escribe:",
            value=f"```\n!vincular {code}\n```",
            inline=False
        )
        embed.add_field(
            name="⏱️ Tiempo disponible",
            value="10 minutos",
            inline=False
        )
        embed.set_footer(text="Después de vincular, tus puntos se sumarán")
        
        # Enviar mensaje privado (efímero, solo visible para el usuario)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Enviar log al canal (sin mostrar el código)
        await bot.send_log(
            f"Usuario: {interaction.user.mention}\n"
            f"Acción: Inició vinculación con YouTube\n"
            f"Código generado: ✓\n"
            f"Válido por: 10 minutos",
            "INFO"
        )

    @bot.tree.command(name="desvincular", description="Desvincula tu cuenta de Discord de tu cuenta de YouTube")
    async def desvincular(interaction: discord.Interaction):
        """Desvincula la cuenta de Discord de la de YouTube.
        
        NUEVA LÓGICA:
        - Mantiene Discord como plataforma principal
        - Elimina la vinculación con YouTube
        - Los puntos permanecen en Discord
        """
        from backend.usermanager import unlink_account
        import os
        
        try:
            common_data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            
            # Usar la nueva función unlink_account con keep_platform='discord'
            result = unlink_account(interaction.user.id, "discord")
            
            if result:
                puntos = result.get("puntos", 0)
                youtube_name = result.get("name", "Usuario")
                
                embed = discord.Embed(
                    title="✓ Desvinculación Completada",
                    description=f"Tu cuenta de Discord se ha desvinculado de **{youtube_name}** (YouTube)",
                    color=0x00FF00
                )
                embed.add_field(
                    name="💰 Tus puntos",
                    value=f"{puntos:.1f}₱ permanecen en tu cuenta de Discord",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                print(f"✓ Desvinculación Discord: {interaction.user.name} ({interaction.user.id}) mantuvo Discord, eliminó YouTube")
                
                # Enviar log al canal
                await bot.send_log(
                    f"Usuario: {interaction.user.mention}\n"
                    f"Acción: Desvinculación completada\n"
                    f"Plataforma removida: YouTube\n"
                    f"Puntos mantenidos: {puntos:.1f}₱\n"
                    f"Plataforma principal: Discord",
                    "INFO"
                )
            else:
                embed = discord.Embed(
                    title="❌ Sin vinculación",
                    description="Tu cuenta de Discord no está vinculada con YouTube.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error desvinculando: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al desvincular tu cuenta.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="forzarvinculacion", description="Vincula forzadamente una cuenta de Discord con una de YouTube (solo moderación)")
    @app_commands.describe(
        usuario="Usuario de Discord a vincular",
        youtube_id="ID del canal de YouTube (NO usar ID de Discord)"
    )
    @app_commands.checks.has_role(1181253292274221267)
    async def forzar_vinculacion(interaction: discord.Interaction, usuario: discord.User, youtube_id: str):
        """Vincula forzadamente una cuenta de Discord con YouTube sin código de vinculación.
        
        Verifica que el youtube_id sea válido (no sea un discord_id) y vincula ambas cuentas.
        """
        from backend.usermanager import load_user_cache, link_accounts, cache_discord_user
        
        try:
            # Primero cachear el usuario de Discord si no existe
            avatar_url = usuario.avatar.url if usuario.avatar else None
            cache_discord_user(
                discord_id=usuario.id,
                name=usuario.name,
                avatar_url=avatar_url
            )
            
            # Cargar cache para validar
            user_cache = load_user_cache()
            users = user_cache.get("users", [])
            
            # El ID proporcionado es el ID universal, no el youtube_id
            # Buscar el usuario por ID universal
            target_user_id = str(youtube_id).strip()
            youtube_user = None
            youtube_channel_id = None
            
            for user in users:
                if str(user.get("id")) == target_user_id:
                    youtube_user = user
                    youtube_channel_id = user.get("youtube_id")
                    break
            
            # Verificar que el usuario exista
            if not youtube_user:
                embed = discord.Embed(
                    title="❌ Error: Usuario no encontrado",
                    description=f"No se encontró ningún usuario con el ID: `{target_user_id}`\n\nVerifica que el ID sea correcto.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Verificar que sea una cuenta de YouTube (tenga youtube_id)
            if not youtube_channel_id:
                embed = discord.Embed(
                    title="❌ Error: No es una cuenta de YouTube",
                    description=f"El usuario con ID `{target_user_id}` no tiene una cuenta de YouTube asociada.\n\nDebes proporcionar el ID de un usuario de YouTube.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Verificar que NO sea una cuenta que ya tenga Discord vinculado
            if youtube_user.get("discord_id"):
                existing_discord_id = youtube_user.get("discord_id")
                embed = discord.Embed(
                    title="❌ Error: Cuenta ya vinculada",
                    description=f"El usuario de YouTube ya tiene Discord vinculado.\n\nDiscord ID vinculado: `{existing_discord_id}`\n\nPrimero debe desvincularse antes de vincular con otra cuenta.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Realizar la vinculación usando el youtube_channel_id real
            resultado = link_accounts(usuario.id, youtube_channel_id)
            
            if resultado:
                puntos_totales = resultado.get("puntos", 0)
                youtube_user_name = youtube_user.get("name", "Usuario desconocido")
                
                embed = discord.Embed(
                    title="✓ Vinculación Forzada Completada",
                    description=f"**{usuario.mention}** ha sido vinculado con **{youtube_user_name}** (YouTube)",
                    color=0x00FF00
                )
                embed.add_field(
                    name="💰 Puntos totales",
                    value=f"{puntos_totales:.1f}₱ (suma de ambas cuentas)",
                    inline=False
                )
                embed.add_field(
                    name="🔗 IDs vinculados",
                    value=f"Discord: `{usuario.id}`\nYouTube ID Universal: `{target_user_id}`\nYouTube Canal: `{youtube_channel_id}`",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                # Enviar log
                await bot.send_log(
                    f"Usuario moderador: {interaction.user.mention}\n"
                    f"Acción: Vinculación forzada\n"
                    f"Usuario vinculado: {usuario.mention}\n"
                    f"YouTube ID Universal: {target_user_id}\n"
                    f"YouTube Canal ID: {youtube_channel_id}\n"
                    f"Nombre YouTube: {youtube_user_name}\n"
                    f"Puntos totales: {puntos_totales:.1f}₱",
                    "INFO"
                )
                
                print(f"✓ Vinculación forzada por {interaction.user.name}: {usuario.name} (Discord) <-> {youtube_user_name} (YouTube)")
            else:
                embed = discord.Embed(
                    title="❌ Error en la vinculación",
                    description="No se pudo completar la vinculación. Verifica que ambas cuentas existan en el sistema.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        
        except Exception as e:
            print(f"❌ Error en forzarvinculacion: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description=f"Ocurrió un error al forzar la vinculación: {str(e)}",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="forzardesvincular", description="Desvincula forzadamente a un usuario de Discord y YouTube (solo moderación)")
    @app_commands.describe(
        usuario="Usuario de Discord a desvincular"
    )
    @app_commands.checks.has_role(1181253292274221267)
    async def forzar_desvinculacion(interaction: discord.Interaction, usuario: discord.User):
        """Desvincula forzadamente una cuenta de Discord de YouTube eliminando la vinculación.
        
        Mantiene los puntos en Discord y elimina completamente la vinculación con YouTube.
        """
        from backend.usermanager import load_user_cache, unlink_account
        
        try:
            # Cargar cache para obtener información
            user_cache = load_user_cache()
            users = user_cache.get("users", [])
            
            # Buscar el usuario por discord_id
            discord_id_str = str(usuario.id)
            target_user = None
            
            for user in users:
                if str(user.get("discord_id")) == discord_id_str:
                    target_user = user
                    break
            
            # Verificar que el usuario exista
            if not target_user:
                embed = discord.Embed(
                    title="❌ Error: Usuario no encontrado",
                    description=f"No se encontró el usuario {usuario.mention} en el sistema de usuarios.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Verificar que tenga una vinculación con YouTube
            youtube_channel_id = target_user.get("youtube_id")
            if not youtube_channel_id:
                embed = discord.Embed(
                    title="❌ Error: No está vinculado",
                    description=f"El usuario {usuario.mention} no tiene una cuenta de YouTube vinculada.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Realizar la desvinculación manteniendo Discord como plataforma principal
            youtube_user_name = target_user.get("name", "Usuario desconocido")
            resultado = unlink_account(usuario.id, "discord")
            
            if resultado:
                puntos_totales = resultado.get("puntos", 0)
                
                embed = discord.Embed(
                    title="✓ Desvinculación Forzada Completada",
                    description=f"**{usuario.mention}** ha sido desvinculado de **{youtube_user_name}** (YouTube)",
                    color=0x00FF00
                )
                embed.add_field(
                    name="💰 Puntos mantenidos",
                    value=f"{puntos_totales:.1f}₱ en Discord",
                    inline=False
                )
                embed.add_field(
                    name="🔗 Información",
                    value=f"Discord: {usuario.mention} (`{usuario.id}`)\nYouTube ID: `{youtube_channel_id}`\nNombre YouTube: {youtube_user_name}",
                    inline=False
                )
                embed.add_field(
                    name="⚠️ Acción",
                    value="YouTube desvinculado - Discord mantenido como plataforma principal",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                # Enviar log
                await bot.send_log(
                    f"Usuario moderador: {interaction.user.mention}\n"
                    f"Acción: Desvinculación forzada\n"
                    f"Usuario desvinculado: {usuario.mention}\n"
                    f"Discord ID: {usuario.id}\n"
                    f"YouTube ID: {youtube_channel_id}\n"
                    f"Nombre YouTube: {youtube_user_name}\n"
                    f"Puntos mantenidos: {puntos_totales:.1f}₱",
                    "INFO"
                )
                
                print(f"✓ Desvinculación forzada por {interaction.user.name}: {usuario.name} (Discord) desvinculado de {youtube_user_name} (YouTube)")
            else:
                embed = discord.Embed(
                    title="❌ Error en la desvinculación",
                    description="No se pudo completar la desvinculación. Verifica que el usuario esté vinculado correctamente.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        
        except Exception as e:
            print(f"❌ Error en forzardesvincular: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description=f"Ocurrió un error al forzar la desvinculación: {str(e)}",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="limpiar_usuarios", description="Elimina usuarios huérfanos de la caché (solo moderación)")
    @app_commands.checks.has_role(1181253292274221267)
    async def limpiar_usuarios(interaction: discord.Interaction):
        """Elimina usuarios que no están vinculados a ninguna plataforma.
        
        Los usuarios huérfanos quedan cuando se desvinculan cuentas y no tienen
        ni Discord ni YouTube vinculado. Esto afecta negativamente al ranking y
        estadísticas del bot.
        """
        from backend.usermanager import load_user_cache, clean_orphaned_users
        
        await interaction.response.defer(ephemeral=True)
        
        user_cache = load_user_cache()
        users_before = len(user_cache.get("users", []))
        
        # Ejecutar limpieza
        user_cache = clean_orphaned_users(user_cache)
        users_after = len(user_cache.get("users", []))
        
        orphaned_removed = users_before - users_after
        
        embed = discord.Embed(
            title="🧹 Limpieza de usuarios completada",
            color=0x00FF00
        )
        embed.add_field(
            name="📊 Estadísticas",
            value=f"Usuarios antes: **{users_before}**\nUsuarios después: **{users_after}**\nUsuarios huérfanos eliminados: **{orphaned_removed}**",
            inline=False
        )
        
        if orphaned_removed > 0:
            embed.add_field(
                name="✅ Estado",
                value="Usuarios huérfanos eliminados exitosamente. El ranking se actualizará automáticamente.",
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Estado",
                value="No se encontraron usuarios huérfanos. La caché está limpia.",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log
        await bot.send_log(
            f"🧹 Limpieza de usuarios realizada por {interaction.user.mention}\n"
            f"Usuarios removidos: {orphaned_removed}",
            "INFO"
        )

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        print(f"Error en comando: {error}")  # Logging adicional

        async def _send_ephemeral(message: str):
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)

        if isinstance(error, app_commands.MissingRole):
            role_id = error.missing_role
            role_name = None
            if interaction.guild:
                role = interaction.guild.get_role(role_id)
                role_name = role.name if role else None
            if role_name:
                await _send_ephemeral(f"No tienes permiso. Necesitas el rol: **{role_name}**.")
            else:
                await _send_ephemeral(f"No tienes permiso. Necesitas el rol con ID: **{role_id}**.")
        elif isinstance(error, app_commands.MissingAnyRole):
            role_names = []
            if interaction.guild:
                for role_id in error.missing_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_names.append(role.name)
            if role_names:
                roles_text = ", ".join(f"**{name}**" for name in role_names)
                await _send_ephemeral(f"No tienes permiso. Necesitas uno de estos roles: {roles_text}.")
            else:
                roles_text = ", ".join(str(role_id) for role_id in error.missing_roles)
                await _send_ephemeral(f"No tienes permiso. Necesitas uno de estos roles (IDs): {roles_text}.")
        elif isinstance(error, app_commands.MissingPermissions):
            perms_text = ", ".join(error.missing_permissions)
            await _send_ephemeral(f"No tienes permiso. Te faltan permisos: **{perms_text}**.")
        else:
            await _send_ephemeral("Ocurrió un error inesperado.")

    @bot.tree.command(name="confesar", description="Envía una confesión anónima al canal de confesiones")
    @app_commands.describe(texto="Tu confesión (máximo 2000 caracteres)")
    async def confesar(interaction: discord.Interaction, texto: str):
        """Permite a los usuarios enviar confesiones anónimas"""
        try:
            # Validar longitud
            if len(texto) > 2000:
                await interaction.response.send_message(
                    "❌ Tu confesión es demasiado larga. Máximo 2000 caracteres.",
                    ephemeral=True
                )
                return
            
            if len(texto.strip()) == 0:
                await interaction.response.send_message(
                    "❌ No puedes enviar una confesión vacía.",
                    ephemeral=True
                )
                return
            
            # ID del canal de confesiones
            CONFESSIONS_CHANNEL_ID = 1171835914394271816
            confessions_channel = bot.get_channel(CONFESSIONS_CHANNEL_ID)
            
            if not confessions_channel:
                await interaction.response.send_message(
                    "❌ El canal de confesiones no está disponible.",
                    ephemeral=True
                )
                return
            
            # Crear embed anónimo
            embed = discord.Embed(
                title="🤐 Confesión Anónima",
                description=texto,
                color=discord.Color.purple(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text="Confesión anónima")
            
            # Enviar al canal de confesiones
            await confessions_channel.send(embed=embed)
            
            # Confirmar al usuario (privadamente)
            await interaction.response.send_message(
                "✅ Tu confesión ha sido enviada de forma anónima al canal de confesiones.",
                ephemeral=True
            )
            
            print(f"✓ Confesión anónima enviada por {interaction.user.name}")
            
        except Exception as e:
            print(f"❌ Error en comando confesar: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

