"""
Sistema de Tienda para Discord Bot
Lee items de la carpeta store/ y los publica en un canal forum
"""
import os
import json
import traceback
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord import ui, Embed, Interaction, File, Forbidden, ForumChannel, Thread
from discord.errors import InteractionResponded

# Asegurar acceso al módulo backend.config
import sys
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from backend import config
from backend.usermanager import cache_discord_user, get_user_by_discord_id, get_user_points, subtract_points_from_user

STORE_DATA_FILE = "data/store_config.json"

class ComprarPersistentView(ui.View):
    """Vista persistente para botones de compra - se mantiene durante toda la sesión del bot"""
    def __init__(self, bot=None):
        super().__init__(timeout=None)  # timeout=None para que sea persistente
        self.bot = bot

class ComprarButton(ui.Button):
    """Botón para comprar un item"""
    def __init__(self, item_id: str, item_name: str, item_price: float, websocket_server=None, bot=None, store_manager=None):
        super().__init__(label="🛍 Comprar", style=discord.ButtonStyle.green, custom_id=f"buy_{item_id}")
        self.item_id = item_id
        self.item_name = item_name
        self.item_price = item_price
        self.websocket_server = websocket_server
        self.bot = bot
        self.store_manager = store_manager
    
    async def callback(self, interaction: discord.Interaction):
        try:
            print(f"\n{'='*60}")
            print(f"🔔 CALLBACK INICIADO")
            print(f"{'='*60}")
            print(f"Usuario: {interaction.user.name} (ID: {interaction.user.id})")
            print(f"Item: {self.item_name} (ID: {self.item_id})")
            print(f"Timestamp: {discord.utils.utcnow()}")
            print(f"Respondido: {interaction.response.is_done()}")
            print(f"WebSocket Server: {'✓ Disponible' if self.websocket_server else '❌ None'}")
            print(f"{'='*60}\n")
            
            # IMPORTANTE: Diferir la respuesta para obtener más tiempo (15 minutos en lugar de 3 segundos)
            await interaction.response.defer(ephemeral=True)
            print("✓ Respuesta diferida (15 minutos de tiempo)")
            
            # Fase 0: Cachear usuario de Discord
            print(f"👤 Cacacheando usuario de Discord...")
            try:
                avatar_url = interaction.user.avatar.url if interaction.user.avatar else None
                user_id = cache_discord_user(
                    discord_id=interaction.user.id,
                    name=interaction.user.name,
                    avatar_url=avatar_url
                )
                print(f"✓ Usuario cacacheado exitosamente (User ID: {user_id})")
            except Exception as e:
                print(f"⚠ Error cacacheando usuario: {type(e).__name__}: {e}")
            
            # Verificar si la tienda está habilitada
            store_enabled = getattr(config, 'store_enabled', True)
            print(f"Estado de tienda: {'✓ Habilitada' if store_enabled else '❌ Deshabilitada'}")
            
            if not store_enabled:
                print("⚠ Tienda deshabilitada, enviando mensaje de rechazo...")
                await interaction.followup.send(
                    "⚠ La tienda está desactivada temporalmente. Las compras no están disponibles.",
                    ephemeral=True
                )
                print("✓ Mensaje de rechazo enviado correctamente")
                return
            
            # Fase 1: Verificar puntos disponibles
            print(f"\n{'='*60}")
            print(f"💳 VERIFICANDO SALDO")
            print(f"{'='*60}")
            print(f"Usuario: {interaction.user.name} (ID: {interaction.user.id})")
            print(f"Item: {self.item_name} (ID: {self.item_id})")
            print(f"Precio: {self.item_price:.1f}₱")
            print(f"{'='*60}\n")
            
            # Obtener puntos del usuario
            user_data = get_user_points(interaction.user.id)
            if not user_data:
                print(f"⚠ Usuario no encontrado en sistema de puntos")
                await interaction.followup.send(
                    f"❌ No se encontró tu cuenta en el sistema. Intenta interactuar primero con el bot.",
                    ephemeral=True
                )
                return
            
            current_points = user_data.get("puntos", 0)
            print(f"💰 Saldo actual: {current_points:.1f}₱")
            
            if current_points < self.item_price:
                deficit = self.item_price - current_points
                print(f"❌ Saldo insuficiente. Falta: {deficit:.1f}₱")
                await interaction.followup.send(
                    f"❌ **Saldo insuficiente**\n\n"
                    f"• Precio: **{self.item_price:.1f}₱**\n"
                    f"• Tu saldo: **{current_points:.1f}₱**\n"
                    f"• Te faltan: **{deficit:.1f}₱**",
                    ephemeral=True
                )
                
                # Enviar log de intento fallido
                if self.bot:
                    try:
                        log_msg = (
                            f"🚫 **Compra rechazada - Saldo insuficiente**\n"
                            f"• Usuario: {interaction.user.mention} ({interaction.user.name})\n"
                            f"• Item: **{self.item_name}** (ID: `{self.item_id}`)\n"
                            f"• Precio: {self.item_price:.1f}₱\n"
                            f"• Saldo actual: {current_points:.1f}₱\n"
                            f"• Faltante: {deficit:.1f}₱"
                        )
                        await self.bot.send_log(log_msg, "WARNING")
                        print(f"✓ Log de compra rechazada enviado")
                    except Exception as log_error:
                        print(f"⚠ Error enviando log de compra rechazada: {log_error}")
                
                return
            
            # Cobrar puntos
            print(f"💸 Cobrando {self.item_price:.1f}₱...")
            result = subtract_points_from_user(interaction.user.id, int(self.item_price))
            if not result:
                print(f"❌ Error al cobrar puntos")
                await interaction.followup.send(
                    f"❌ Error al procesar el pago. Intenta de nuevo.",
                    ephemeral=True
                )
                return
            
            new_balance = result.get("puntos", 0)
            print(f"✓ Puntos cobrados exitosamente. Nuevo saldo: {new_balance:.1f}₱")
            
            # Fase 2: Enviar notificación por WebSocket
            ws_error = None
            if self.websocket_server:
                try:
                    print(f"📡 Intentando enviar notificación por WebSocket...")
                    notification_data = {
                        "type": "notification",
                        "notificationId": self.item_id,
                        "userId": interaction.user.id,
                        "itemName": self.item_name,
                        "timestamp": str(discord.utils.utcnow())
                    }
                    print(f"   Datos a enviar: {notification_data}")
                    
                    await self.websocket_server.send_update(notification_data)
                    print(f"✓ Notificación enviada por WebSocket exitosamente")
                except AttributeError as e:
                    ws_error = f"WebSocket no tiene método send_update: {e}"
                    print(f"❌ {ws_error}")
                except Exception as e:
                    ws_error = f"Error enviando notificación: {type(e).__name__}: {e}"
                    print(f"❌ {ws_error}")
            else:
                print(f"⚠ WebSocket Server es None, notificación no se enviará")
            
            # Fase 2.5: Registrar venta en el sistema
            if self.store_manager:
                try:
                    print(f"📈 Registrando venta...")
                    self.store_manager.record_sale(self.item_id)
                    print(f"✓ Venta registrada correctamente")
                    
                    # Intentar actualizar el thread para reflejar la nueva inflación
                    try:
                        if self.store_manager.forum_channel_id and self.item_id in self.store_manager.item_threads:
                            forum_channel = self.bot.get_channel(self.store_manager.forum_channel_id)
                            if forum_channel:
                                thread_id = self.store_manager.item_threads[self.item_id]
                                thread = forum_channel.get_thread(thread_id)
                                if thread:
                                    # Buscar el item en store para obtener toda su info
                                    items = self.store_manager.scan_store_items()
                                    item_data = next((item for item in items if item['id'] == self.item_id), None)
                                    if item_data:
                                        await self.store_manager.update_item_thread(thread, item_data)
                                        print(f"✓ Thread actualizado con nueva inflación")
                    except Exception as thread_error:
                        print(f"⚠ Error actualizando thread: {thread_error}")
                except Exception as sale_error:
                    print(f"⚠ Error registrando venta: {sale_error}")
            
            # Fase 3: Responder al usuario
            print(f"📤 Enviando confirmación al usuario...")
            try:
                response_msg = f"✅ **Compra exitosa**\n\n"
                response_msg += f"• Item: **{self.item_name}**\n"
                response_msg += f"• Precio: **{self.item_price:.1f}₱**\n"
                response_msg += f"• Nuevo saldo: **{new_balance:.1f}₱**"
                if ws_error:
                    response_msg += f"\n⚠ (Notificación: {ws_error})"
                
                await interaction.followup.send(
                    response_msg,
                    ephemeral=True
                )
                print(f"✓ Confirmación de compra enviada al usuario")
                
                # Fase 4: Enviar log de compra al canal de logs
                if self.bot:
                    try:
                        log_msg = f"🛍 **Compra realizada**\n• Usuario: {interaction.user.mention} ({interaction.user.name})\n• Item: **{self.item_name}** (ID: `{self.item_id}`)\n• Precio: {self.item_price:.1f}₱\n• Nuevo saldo: {new_balance:.1f}₱"
                        await self.bot.send_log(log_msg, "SUCCESS")
                        print(f"✓ Log de compra enviado al canal de logs")
                    except Exception as log_error:
                        print(f"⚠ Error enviando log de compra: {log_error}")
                
            except discord.errors.InteractionResponded:
                print(f"⚠ Interacción ya fue respondida antes, intentando followup...")
                try:
                    response_msg = f"✅ **Compra exitosa**\n\n"
                    response_msg += f"• Item: **{self.item_name}**\n"
                    response_msg += f"• Precio: **{self.item_price:.1f}₱**\n"
                    response_msg += f"• Nuevo saldo: **{new_balance:.1f}₱**"
                    await interaction.followup.send(
                        response_msg,
                        ephemeral=True
                    )
                    print(f"✓ Followup enviado exitosamente")
                    
                    # Enviar log de compra incluso en followup
                    if self.bot:
                        try:
                            log_msg = f"🛍 **Compra realizada**\n• Usuario: {interaction.user.mention} ({interaction.user.name})\n• Item: **{self.item_name}** (ID: `{self.item_id}`)\n• Precio: {self.item_price:.1f}₱\n• Nuevo saldo: {new_balance:.1f}₱"
                            await self.bot.send_log(log_msg, "SUCCESS")
                        except Exception as log_error:
                            print(f"⚠ Error enviando log de compra: {log_error}")
                            
                except Exception as e:
                    print(f"❌ Error en followup: {type(e).__name__}: {e}")
            
            print(f"{'='*60}")
            print(f"✅ CALLBACK COMPLETADO EXITOSAMENTE")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"❌ ERROR CRÍTICO EN CALLBACK")
            print(f"{'='*60}")
            print(f"Tipo de error: {type(e).__name__}")
            print(f"Mensaje: {e}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            print(f"{'='*60}\n")
            
            # Intentar responder al usuario sobre el error
            try:
                await interaction.followup.send(
                    f"❌ Error procesando la compra: {type(e).__name__}",
                    ephemeral=True
                )
            except Exception as response_error:
                print(f"❌ Error enviando mensaje de error al usuario: {response_error}")


class StoreManager:
    def __init__(self, bot):
        self.bot = bot
        self.store_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'navegador', 'store')
        self.store_config_file = os.path.join(os.path.dirname(__file__), STORE_DATA_FILE)
        self.forum_channel_id = None
        self.item_threads = {}  # {item_id: thread_id}
        self.prices = {}        # {item_id: float} - overrides dinámicos
        self.sales_history = {} # {item_id: [timestamp1, timestamp2, ...]}
        self.inflation_rate = 1.0  # % de incremento por venta (default 1%)
        self.inflation_duration_minutes = 60  # Duración de la inflación en minutos (default 60)
        self.last_inflation_state = {}  # {item_id: inflation_value} para detectar cambios
        self.load_store_config()
        # Iniciar tarea de actualización periódica
        self.start_price_update_loop()

    def load_store_config(self):
        """Carga la configuración de la tienda (canal forum e IDs de threads)"""
        try:
            with open(self.store_config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.forum_channel_id = data.get('forum_channel_id')
                self.item_threads = data.get('item_threads', {})
                self.prices = data.get('prices', {})
                self.sales_history = data.get('sales_history', {})
                self.inflation_rate = data.get('inflation_rate', 1.0)
                self.inflation_duration_minutes = data.get('inflation_duration_minutes', 60)
        except FileNotFoundError:
            self.forum_channel_id = None
            self.item_threads = {}
            self.prices = {}
            self.sales_history = {}
            self.inflation_rate = 1.0
            self.inflation_duration_minutes = 60

    def save_store_config(self):
        """Guarda la configuración de la tienda"""
        data = {
            'forum_channel_id': self.forum_channel_id,
            'item_threads': self.item_threads,
            'prices': self.prices,
            'sales_history': self.sales_history,
            'inflation_rate': self.inflation_rate,
            'inflation_duration_minutes': self.inflation_duration_minutes
        }
        with open(self.store_config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def scan_store_items(self):
        """Escanea la carpeta store/ y retorna lista de items"""
        items = []
        
        if not os.path.exists(self.store_path):
            print(f"⚠ Carpeta store no encontrada: {self.store_path}")
            return items

        # Leer cada subcarpeta
        for folder_name in os.listdir(self.store_path):
            folder_path = os.path.join(self.store_path, folder_name)
            
            # Ignorar archivos, solo carpetas
            if not os.path.isdir(folder_path):
                continue
            
            config_path = os.path.join(folder_path, 'config.json')
            
            # Verificar si tiene config.json
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # Buscar miniatura (jpg, png, gif)
                    thumbnail_path = None
                    for ext in ['jpg', 'jpeg', 'png', 'gif']:
                        thumb_file = os.path.join(folder_path, f'miniatura.{ext}')
                        if os.path.exists(thumb_file):
                            thumbnail_path = thumb_file
                            break
                    
                    # Buscar archivo de audio
                    audio_path = None
                    for ext in ['mp3', 'wav', 'ogg', 'm4a']:
                        audio_file = os.path.join(folder_path, f'audio.{ext}')
                        if os.path.exists(audio_file):
                            audio_path = audio_file
                            break
                    
                    item = {
                        'id': folder_name,
                        'name': config.get('titleText', folder_name),
                        'description': config.get('messageText', 'Sin descripción'),
                        'video_path': os.path.join(folder_path, 'video.mp4'),
                        'has_video': os.path.exists(os.path.join(folder_path, 'video.mp4')),
                        'thumbnail_path': thumbnail_path,
                        'has_thumbnail': thumbnail_path is not None,
                        'audio_path': audio_path,
                        'has_audio': audio_path is not None,
                        'config': config
                    }
                    items.append(item)
                except Exception as e:
                    print(f"❌ Error leyendo config de {folder_name}: {e}")
        
        return items

    async def create_store_forum(self, guild: discord.Guild, category: discord.CategoryChannel = None):
        """Crea el canal forum para la tienda"""
        try:
            # Verificar si ya existe
            if self.forum_channel_id:
                existing_channel = guild.get_channel(self.forum_channel_id)
                if existing_channel and isinstance(existing_channel, discord.ForumChannel):
                    print(f"✓ Canal forum ya existe: {existing_channel.name}")
                    return existing_channel

            # Crear nuevo canal forum
            forum_channel = await guild.create_forum(
                name="🛒・tienda",
                topic="Tienda de notificaciones personalizadas",
                category=category
            )
            
            self.forum_channel_id = forum_channel.id
            self.save_store_config()
            print(f"✓ Canal forum creado: {forum_channel.name}")
            return forum_channel
            
        except discord.Forbidden:
            print(f"❌ Permiso denegado: El bot no tiene permisos para crear canales")
            print(f"   Asegúrate de que el bot tiene permisos de 'Gestionar canales'")
            return None
        except Exception as e:
            print(f"❌ Error creando canal forum: {e}")
            return None

    async def update_store(self, guild: discord.Guild):
        """Actualiza todos los items de la tienda en el forum"""
        # Obtener items de la carpeta
        items = self.scan_store_items()
        
        if not items:
            print("⚠ No se encontraron items en la tienda")
            return

        # Obtener canal forum
        if not self.forum_channel_id:
            print("❌ No hay canal forum configurado. Usa /setup_store primero")
            return

        forum_channel = guild.get_channel(self.forum_channel_id)
        if not forum_channel:
            print(f"❌ Canal forum no encontrado (ID: {self.forum_channel_id})")
            print("   Intenta usar /setup_store para crear uno nuevo")
            return
        
        if not isinstance(forum_channel, discord.ForumChannel):
            print("❌ El canal no es un forum")
            return

        print(f"📦 Actualizando tienda con {len(items)} items...")

        # Obtener IDs de items actuales
        current_item_ids = {item['id'] for item in items}
        stored_item_ids = set(self.item_threads.keys())
        
        # Eliminar threads de items que ya no existen
        removed_items = stored_item_ids - current_item_ids
        for removed_id in removed_items:
            thread_id = self.item_threads.pop(removed_id)
            try:
                thread = forum_channel.get_thread(thread_id)
                if thread:
                    await thread.delete()
                    print(f"  🗑 Thread eliminado: {removed_id}")
            except Exception as e:
                print(f"  ⚠ Error eliminando thread {removed_id}: {e}")
        
        # Guardar cambios
        if removed_items:
            self.save_store_config()

        # Procesar cada item
        for item in items:
            await self.create_or_update_item_thread(forum_channel, item)

        print("✓ Tienda actualizada correctamente")

    async def create_or_update_item_thread(self, forum_channel: discord.ForumChannel, item: dict):
        """Crea o actualiza un thread para un item"""
        try:
            item_id = item['id']
            
            # Verificar si ya existe un thread para este item
            existing_thread_id = self.item_threads.get(item_id)
            
            if existing_thread_id:
                # Intentar obtener el thread existente
                thread = forum_channel.get_thread(existing_thread_id)
                if thread:
                    # Actualizar el thread existente
                    await self.update_item_thread(thread, item)
                    print(f"  ✓ Thread actualizado: {item['name']}")
                    return
            
            # Crear nuevo thread
            embed = self.create_item_embed(item)
            view = ComprarPersistentView(bot=self.bot)
            item_price = self.get_dynamic_price(item_id=item['id'], item_config=item.get('config', {}))
            button = ComprarButton(item['id'], item['name'], item_price, self.bot.websocket_server, self.bot, self)
            view.add_item(button)
            
            # Preparar archivos adjuntos
            files = []
            if item['has_thumbnail']:
                try:
                    files.append(discord.File(item['thumbnail_path']))
                except Exception as e:
                    print(f"  ⚠ Error adjuntando miniatura: {e}")
            if item['has_audio']:
                try:
                    files.append(discord.File(item['audio_path']))
                except Exception as e:
                    print(f"  ⚠ Error adjuntando audio: {e}")
            
            # Crear thread sin contenido inicial, solo con embed y archivos
            thread = await forum_channel.create_thread(
                name=f"🎬 {item['name']}",
                embed=embed,
                files=files if files else None
            )
            
            # Agregar el botón al primer mensaje del thread
            try:
                async for message in thread.thread.history(limit=1, oldest_first=True):
                    await message.edit(view=view)
                    break
            except Exception as e:
                print(f"  ⚠ Error agregando botón: {e}")
            
            # Guardar ID del thread
            self.item_threads[item_id] = thread.thread.id
            self.save_store_config()
            print(f"  ✓ Thread creado: {item['name']}")
            
        except discord.Forbidden:
            print(f"  ❌ Permiso denegado para item {item['id']}: Sin acceso al canal o permisos insuficientes")
        except Exception as e:
            print(f"  ❌ Error con item {item['id']}: {e}")

    async def update_item_thread(self, thread: discord.Thread, item: dict):
        """Actualiza el contenido de un thread existente"""
        try:
            # Obtener el primer mensaje del thread
            async for message in thread.history(limit=1, oldest_first=True):
                embed = self.create_item_embed(item)
                view = ComprarPersistentView(bot=self.bot)
                item_price = self.get_dynamic_price(item_id=item['id'], item_config=item.get('config', {}))
                button = ComprarButton(item['id'], item['name'], item_price, self.bot.websocket_server, self.bot, self)
                view.add_item(button)
                
                await message.edit(
                    embed=embed,
                    view=view
                )
                break
        except Exception as e:
            print(f"  ❌ Error actualizando thread: {e}")

    def create_item_embed(self, item: dict):
        """Crea un embed para un item"""
        embed = discord.Embed(
            title=item['name'],
            description=item['description'],
            color=0x041057
        )
        
        embed.add_field(name="📁 ID", value=f"`{item['id']}`", inline=True)
        
        # Precio base
        base_price = self.get_item_price(item_id=item['id'], item_config=item.get('config', {}))
        
        # Inflación actual
        inflation_percent = self.calculate_inflation(item['id'])
        
        # Precio con inflación
        dynamic_price = self.get_dynamic_price(item['id'], item.get('config', {}))
        
        # Mostrar precio
        price_display = f"{dynamic_price:.1f} ₱"
        if inflation_percent > 0:
            price_display += f" ~~{base_price:.1f}~~"
        embed.add_field(name="💰 Precio", value=price_display, inline=True)
        
        # Mostrar inflación
        if inflation_percent > 0:
            embed.add_field(name="📈 Inflación", value=f"+{inflation_percent:.1f}%", inline=True)
        else:
            embed.add_field(name="📈 Inflación", value="0%", inline=True)
        
        # Si tiene video, agregar información adicional
        if item['has_video']:
            embed.set_footer(text="Este item incluye notificación de video personalizada")
        
        return embed

    def get_item_price(self, item_id: str, item_config: dict) -> float:
        """Obtiene el precio dinámico del item. Prioridad: overrides > config.json > 0.0"""
        # Override guardado dinámicamente
        if item_id in self.prices:
            try:
                return float(self.prices[item_id])
            except (ValueError, TypeError):
                pass
        # Precio en el config.json del item (si existe)
        if item_config and 'price' in item_config:
            try:
                return float(item_config['price'])
            except (ValueError, TypeError):
                pass
        # Por defecto: 0.0 ₱
        return 0.0

    def record_sale(self, item_id: str):
        """Registra una venta con timestamp actual"""
        timestamp = datetime.utcnow().isoformat()
        if item_id not in self.sales_history:
            self.sales_history[item_id] = []
        self.sales_history[item_id].append(timestamp)
        self.clean_old_sales(item_id)
        self.save_store_config()
        print(f"📊 Venta registrada: {item_id} - Total ventas recientes: {len(self.get_recent_sales(item_id))}")

    def get_recent_sales(self, item_id: str) -> list:
        """Obtiene las ventas dentro del período de inflación configurado"""
        if item_id not in self.sales_history:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.inflation_duration_minutes)
        recent_sales = []
        
        for timestamp_str in self.sales_history[item_id]:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp > cutoff_time:
                    recent_sales.append(timestamp_str)
            except (ValueError, TypeError):
                continue
        
        return recent_sales

    def clean_old_sales(self, item_id: str):
        """Limpia ventas mayores al período de inflación configurado para mantener el archivo limpio"""
        if item_id not in self.sales_history:
            return
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.inflation_duration_minutes)
        cleaned_sales = []
        
        for timestamp_str in self.sales_history[item_id]:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp > cutoff_time:
                    cleaned_sales.append(timestamp_str)
            except (ValueError, TypeError):
                continue
        
        self.sales_history[item_id] = cleaned_sales

    def calculate_inflation(self, item_id: str) -> float:
        """Calcula el % de inflación basado en ventas de la última hora"""
        recent_sales = self.get_recent_sales(item_id)
        inflation_percent = len(recent_sales) * self.inflation_rate
        return inflation_percent

    def get_dynamic_price(self, item_id: str, item_config: dict) -> float:
        """Obtiene el precio con inflación aplicada"""
        base_price = self.get_item_price(item_id, item_config)
        inflation_percent = self.calculate_inflation(item_id)
        
        if inflation_percent > 0:
            inflated_price = base_price * (1 + inflation_percent / 100)
            return inflated_price
        
        return base_price

    def start_price_update_loop(self):
        """Inicia la tarea de actualización periódica de precios"""
        if not self.update_prices_task.is_running():
            self.update_prices_task.start()
            print("✓ Tarea de actualización de precios iniciada")
    
    @tasks.loop(minutes=1)
    async def update_prices_task(self):
        """
        Tarea que se ejecuta cada minuto para actualizar precios en los threads.
        
        Detecta cambios en la inflación de los items y actualiza automáticamente los embeds
        de los threads cuando la inflación sube o baja. Esto permite que los precios congelados
        se descongelan cuando la inflación baja.
        """
        try:
            if not self.bot.is_ready():
                return
            
            if not self.forum_channel_id:
                return
            
            # Obtener guild del bot
            guild = self.bot.guilds[0] if self.bot.guilds else None
            if not guild:
                return
            
            # Obtener canal forum
            forum_channel = guild.get_channel(self.forum_channel_id)
            if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
                return
            
            items = self.scan_store_items()
            if not items:
                return
            
            # Verificar cada item para detectar cambios de inflación
            for item in items:
                item_id = item['id']
                current_inflation = self.calculate_inflation(item_id)
                previous_inflation = self.last_inflation_state.get(item_id, -1)
                
                # Solo actualizar si cambió la inflación
                if current_inflation != previous_inflation:
                    self.last_inflation_state[item_id] = current_inflation
                    
                    # Obtener thread del item
                    thread_id = self.item_threads.get(item_id)
                    if thread_id:
                        thread = forum_channel.get_thread(thread_id)
                        if thread:
                            try:
                                await self.update_item_thread(thread, item)
                            except Exception as e:
                                pass
        
        except Exception as e:
            pass


def setup_store_commands(bot):
    """Configura los comandos de la tienda"""
    store_manager = StoreManager(bot)
    bot.store_manager = store_manager  # Guardar referencia en el bot
    
    @bot.tree.command(name="setup_store", description="Crea el canal forum de la tienda")
    @discord.app_commands.checks.has_role(1181253292274221267)
    async def setup_store(interaction: discord.Interaction):
        await interaction.response.defer()
        
        forum_channel = await store_manager.create_store_forum(interaction.guild)
        
        if forum_channel:
            await interaction.followup.send(f"✓ Canal de tienda creado: {forum_channel.mention}")
        else:
            await interaction.followup.send("❌ Error al crear el canal de tienda")
    
    @bot.tree.command(name="update_store", description="Actualiza los items de la tienda")
    @discord.app_commands.checks.has_role(1181253292274221267)
    async def update_store(interaction: discord.Interaction):
        await interaction.response.defer()
        
        await store_manager.update_store(interaction.guild)
        
        await interaction.followup.send("✓ Tienda actualizada correctamente")
    
    @bot.tree.command(name="scan_store", description="Escanea los items disponibles en la tienda")
    @discord.app_commands.checks.has_role(1181253292274221267)
    async def scan_store(interaction: discord.Interaction):
        items = store_manager.scan_store_items()
        
        if items:
            embed = discord.Embed(
                title="📦 Items en la Tienda",
                description=f"Se encontraron {len(items)} items",
                color=0x00ff00
            )
            
            for item in items:
                video_status = "✅" if item['has_video'] else "❌"
                thumb_status = "✅" if item['has_thumbnail'] else "❌"
                audio_status = "✅" if item['has_audio'] else "❌"
                price = store_manager.get_item_price(item_id=item['id'], item_config=item.get('config', {}))
                embed.add_field(
                    name=f"{video_status} {item['name']}",
                    value=(
                        f"ID: `{item['id']}`\n"
                        f"💰 Precio: {price:.1f} ₱\n"
                        f"🖼: {thumb_status} | 🔊: {audio_status}\n"
                        f"{item['description'][:50]}..."
                    ),
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("⚠ No se encontraron items en la tienda")
    
    @bot.tree.command(name="config_incremento", description="Configura el % de inflación por venta")
    @discord.app_commands.checks.has_role(1181253292274221267)
    @discord.app_commands.describe(porcentaje="Porcentaje de incremento por cada venta (ej: 1.0 = 1%)")
    async def config_incremento(interaction: discord.Interaction, porcentaje: float):
        try:
            if porcentaje < 0:
                await interaction.response.send_message("❌ El porcentaje debe ser mayor o igual a 0", ephemeral=True)
                return
            
            old_rate = store_manager.inflation_rate
            store_manager.inflation_rate = porcentaje
            store_manager.save_store_config()
            
            embed = discord.Embed(
                title="⚙️ Configuración de Inflación Actualizada",
                description=f"El porcentaje de inflación por venta ha sido modificado",
                color=0x00ff00
            )
            embed.add_field(name="Valor Anterior", value=f"{old_rate:.2f}%", inline=True)
            embed.add_field(name="Valor Nuevo", value=f"{porcentaje:.2f}%", inline=True)
            embed.set_footer(text="Cada venta en la última hora incrementará el precio en este porcentaje")
            
            await interaction.response.send_message(embed=embed)
            
            # Actualizar todos los threads para reflejar los cambios
            if store_manager.forum_channel_id:
                await interaction.followup.send("🔄 Actualizando precios en la tienda...", ephemeral=True)
                await store_manager.update_store(interaction.guild)
                
        except Exception as e:
            await interaction.response.send_message(f"❌ Error al configurar el incremento: {e}", ephemeral=True)
    
    @bot.tree.command(name="config_inflationrate", description="Configura la duración de la inflación en minutos")
    @discord.app_commands.checks.has_role(1181253292274221267)
    @discord.app_commands.describe(minutos="Duración de la inflación en minutos (mínimo 1)")
    async def config_inflationrate(interaction: discord.Interaction, minutos: int):
        """Configura durante cuántos minutos durará la inflación después de una venta.
        
        Ejemplo:
        - 60 minutos (default): Las ventas afectan el precio por 1 hora
        - 30 minutos: Las ventas afectan el precio por 30 minutos
        - 120 minutos: Las ventas afectan el precio por 2 horas
        """
        try:
            if minutos < 1:
                await interaction.response.send_message(
                    "❌ La duración debe ser mínimo 1 minuto",
                    ephemeral=True
                )
                return
            
            old_duration = store_manager.inflation_duration_minutes
            store_manager.inflation_duration_minutes = minutos
            store_manager.save_store_config()
            
            embed = discord.Embed(
                title="⚙️ Duración de Inflación Actualizada",
                description="El tiempo que durará la inflación tras una venta ha sido modificado",
                color=0x00ff00
            )
            embed.add_field(
                name="Duración Anterior",
                value=f"{old_duration} minutos" if old_duration != 1 else "1 minuto",
                inline=True
            )
            embed.add_field(
                name="Duración Nueva",
                value=f"{minutos} minutos" if minutos != 1 else "1 minuto",
                inline=True
            )
            embed.add_field(
                name="ℹ️ Explicación",
                value=f"Cada venta afectará el precio durante **{minutos}** minuto{'s' if minutos != 1 else ''}",
                inline=False
            )
            embed.set_footer(text="Los precios se descongelarán automáticamente cuando expire este tiempo")
            
            await interaction.response.send_message(embed=embed)
            
            # Actualizar todos los threads para reflejar los cambios
            if store_manager.forum_channel_id:
                await interaction.followup.send("🔄 Actualizando precios en la tienda...", ephemeral=True)
                await store_manager.update_store(interaction.guild)
                
        except Exception as e:
            await interaction.response.send_message(f"❌ Error al configurar la duración: {e}", ephemeral=True)
    
    @bot.tree.command(name="ver_inflacion", description="Ver estadísticas de inflación de todos los items")
    @discord.app_commands.checks.has_role(1181253292274221267)
    async def ver_inflacion(interaction: discord.Interaction):
        items = store_manager.scan_store_items()
        
        if not items:
            await interaction.response.send_message("⚠ No se encontraron items en la tienda", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📊 Estadísticas de Inflación",
            description=f"Tasa de incremento: **{store_manager.inflation_rate:.1f}%** por venta\nDuración: **{store_manager.inflation_duration_minutes}** minutos",
            color=0x041057
        )
        
        for item in items:
            base_price = store_manager.get_item_price(item['id'], item.get('config', {}))
            inflation = store_manager.calculate_inflation(item['id'])
            dynamic_price = store_manager.get_dynamic_price(item['id'], item.get('config', {}))
            recent_sales = len(store_manager.get_recent_sales(item['id']))
            
            value = f"💰 Base: {base_price:.1f}₱ → Actual: {dynamic_price:.1f}₱\n"
            value += f"📈 Inflación: **+{inflation:.1f}%**\n"
            value += f"🛒 Ventas (últimos {store_manager.inflation_duration_minutes} minutos): {recent_sales}"
            
            embed.add_field(
                name=f"{item['name']}",
                value=value,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    print("✓ Comandos de tienda configurados")
