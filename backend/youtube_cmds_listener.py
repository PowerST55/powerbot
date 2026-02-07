import asyncio
import logging
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError
from usermanager import load_banned_users , load_user_cache, load_custom_users, add_points_to_user, get_user_points, find_user_by_query, link_accounts, unlink_account, db_manager, init_database
from activities.poll import iniciar_encuesta, resetpoll
from activities.text2voice import TextToVoice
from backend.transaction_logger import TransactionLogger
import json
import os
import sys
import time
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from backend import config
from backend.economy_youtube import YouTubeEconomyManager
from backend.account_linking import AccountLinkingManager
from backend.code_manager import CodeManager
from activities.spin_wheel import inscribir_en_ruleta
from activities.screentext import add_text_to_screentext

# --- Manejo de archivos de moderadores y miembros ---
MODS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'moderators.json')
MEMBERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'members.json')
CUSTOM_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'custom_users.json')

# Estado temporal para construcción de encuestas vía chat (custom users)
poll_builders = {}

def load_json_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_json_file(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Inicializar gestor de economía de YouTube
youtube_economy_manager = YouTubeEconomyManager(
    data_dir=os.path.join(os.path.dirname(__file__), '..', 'data')
)

# Inicializar gestor de vinculación de cuentas
account_linking_manager = AccountLinkingManager(
    data_dir=os.path.join(os.path.dirname(__file__), '..', 'data'),
    db_manager=db_manager
)

# Inicializar gestor de códigos recompensables
code_manager = CodeManager(
    data_dir=os.path.join(os.path.dirname(__file__), '..', 'data')
)
code_manager.load_config()  # Cargar configuración
code_manager._load_active_code()  # Cargar código activo si existe

# Inicializar logger de transacciones
transaction_logger = TransactionLogger(
    data_dir=os.path.join(os.path.dirname(__file__), '..', 'data')
)

# Actualiza la lista de moderadores usando los mensajes recientes
def update_moderators_from_messages(user_cache, mods_file=MODS_FILE):
    mods = load_json_file(mods_file)
    changed = False
    
    # Agregar moderadores nuevos
    for user in user_cache.get("users", []):
        canal_id = str(user.get("id"))
        if user.get('isModerator'):
            if canal_id not in mods:
                mods[canal_id] = {
                    'name': user.get('name', ''),
                    'avatar_url': user.get('avatar_url', ''),
                    'avatar_local': user.get('avatar_local', '')
                }
                changed = True
    
    # Remover moderadores que ya no tienen el rol
    mods_to_remove = []
    for canal_id in list(mods.keys()):
        # Buscar usuario por id
        user = next((u for u in user_cache.get("users", []) if str(u.get("id")) == canal_id), None)
        if user and not user.get('isModerator'):
            mods_to_remove.append(canal_id)
    
    for canal_id in mods_to_remove:
        del mods[canal_id]
        changed = True
        print(f"Moderador {canal_id} removido de la lista")
    
    if changed:
        save_json_file(mods_file, mods)
    return mods

# Actualiza la lista de miembros usando los mensajes recientes
def update_members_from_messages(user_cache, members_file=MEMBERS_FILE):
    members = load_json_file(members_file)
    changed = False
    
    # Agregar miembros nuevos
    for user in user_cache.get("users", []):
        canal_id = str(user.get("id"))
        if user.get('isMember'):
            if canal_id not in members:
                members[canal_id] = {
                    'name': user.get('name', ''),
                    'avatar_url': user.get('avatar_url', ''),
                    'avatar_local': user.get('avatar_local', '')
                }
                changed = True
    
    # Remover miembros que ya no tienen el rol
    members_to_remove = []
    for canal_id in list(members.keys()):
        user = next((u for u in user_cache.get("users", []) if str(u.get("id")) == canal_id), None)
        if user and not user.get('isMember'):
            members_to_remove.append(canal_id)
    
    for canal_id in members_to_remove:
        del members[canal_id]
        changed = True
        print(f"Miembro {canal_id} removido de la lista")
    
    if changed:
        save_json_file(members_file, members)
    return members

LAST_MSG_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'last_msg_id.json')
ACTIVE_USERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'active_users.json')

def save_last_msg_id(msg_id):
    with open(LAST_MSG_FILE, 'w') as f:
        json.dump({"last_msg_id": msg_id}, f)

def load_last_msg_id():
    try:
        with open(LAST_MSG_FILE, 'r') as f:
            return json.load(f).get("last_msg_id")
    except Exception:
        return None

# ---- Gestión de usuarios activos (últimos 5 minutos) ----
def save_active_users(active_users):
    """Guarda el dict de usuarios activos con timestamps en JSON."""
    with open(ACTIVE_USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(active_users, f, indent=4, ensure_ascii=False)

def load_active_users():
    """Carga el dict de usuarios activos desde JSON."""
    try:
        with open(ACTIVE_USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def update_active_user(canal_id, autor, timestamp):
    """Actualiza el timestamp del usuario activo."""
    active_users = load_active_users()
    active_users[str(canal_id)] = {
        'name': autor,
        'timestamp': timestamp
    }
    save_active_users(active_users)

def get_active_users_in_window(minutes=5):
    """Obtiene usuarios activos en los últimos N minutos.
    
    Args:
        minutes: Ventana de tiempo en minutos
        
    Returns:
        list: [(canal_id, nombre), ...] de usuarios activos
    """
    import time
    active_users = load_active_users()
    current_time = int(time.time())
    time_window = current_time - (minutes * 60)
    
    active_in_window = []
    for canal_id, info in active_users.items():
        if info.get('timestamp', 0) > time_window:
            active_in_window.append((canal_id, info.get('name', 'Usuario')))
    
    return active_in_window

async def youtube_listener(
    server,
    send_message_async,
    votos,
    waittime,
    cache_user_info,
    store_manager=None
):
    next_page_token = None
    max_reintentos = 2
    intentos = 0

    last_msg_id = load_last_msg_id()

    while True:
        youtube = config.youtube
        live_chat_id = config.live_chat_id
        comandos_habilitados = config.comandos_habilitados
        ruleta_activa = config.ruleta_activa
        itstimetojoin = config.itstimetojoin
        encuesta_activa = config.encuesta_activa
        participantes_ruleta = config.participantes_ruleta
        participantes_votantes = config.participantes_votantes

        # Recarga la lista de baneados en cada ciclo
        banned_users = load_banned_users()
        user_cache = load_user_cache()  # Carga la caché de usuarios (nuevo formato)

        # Actualiza la lista de moderadores y miembros en cada ciclo usando el cache
        mods = update_moderators_from_messages(user_cache)
        members = update_members_from_messages(user_cache)
        custom_users = load_custom_users()  # Carga la lista de usuarios custom

        if youtube and config.isyappi:
            try:
                # --- GENERAR CÓDIGO RECOMPENSABLE ---
                if code_manager.should_generate_code():
                    code_data = code_manager.generate_code()
                    if code_data:
                        # Enviar código por WebSocket
                        await server.send_update({
                            'type': 'show_code',
                            'code': code_data['code'],
                            'duration': code_data['duration'],
                            'blink_start': code_manager.code_blink_start
                        })
                        print(f"📡 Código enviado por WebSocket: {code_data['code']}")
                
                if next_page_token:
                    response = youtube.liveChatMessages().list(
                        liveChatId=live_chat_id,
                        part="snippet,authorDetails",
                        pageToken=next_page_token
                    ).execute()
                else:
                    response = youtube.liveChatMessages().list(
                        liveChatId=live_chat_id,
                        part="snippet,authorDetails"
                    ).execute()
                
                for item in response.get("items", []):
                    mensaje_raw = item["snippet"].get("textMessageDetails", {}).get("messageText", "")
                    mensaje = mensaje_raw.lower()
                    autor = item["authorDetails"]["displayName"]
                    avatar_url = item["authorDetails"]["profileImageUrl"]
                    canal_id = item["authorDetails"].get("channelId", "ID no encontrado")
                    is_moderator = item["authorDetails"].get("isChatModerator", False) or item["authorDetails"].get("isChatOwner", False)
                    is_member = item["authorDetails"].get("isChatSponsor", False)
                    
                    # SIEMPRE cachear usuarios (con o sin guardar)
                    if config.skip_old_messages:
                        # Modo batch: no guardar en cada mensaje
                        cache_user_info(canal_id, autor, avatar_url, is_moderator, is_member, skip_save=True)
                    else:
                        # Modo normal: guardar cada mensaje
                        cache_user_info(canal_id, autor, avatar_url, is_moderator, is_member)
                    
                    # Si estamos ignorando mensajes antiguos, saltar procesamiento de comandos
                    if config.skip_old_messages:
                        # Después de procesar todas las páginas de mensajes antiguos,
                        # cuando ya no haya nextPageToken, resetearemos el flag
                        continue
                    
                    if canal_id in banned_users:
                        print(f"El usuario baneado '{autor}' intentó enviar un mensaje: {mensaje}")
                        continue
                    
                    print(f"{autor}: {mensaje}")

                    
                    # Actualizar tracking de usuarios activos (para !apsall)
                    import time
                    update_active_user(canal_id, autor, int(time.time()))
                    
                    # --- SISTEMA DE GANANCIA DE PEWS PARA YOUTUBE ---
                    # Procesar mensaje para ganar puntos (independiente de Discord)
                    try:
                        if youtube_economy_manager.process_message(canal_id):
                            result = add_points_to_user(canal_id, 1)
                            if result:
                                current_pews = result.get("puntos", 0)
                                print(f"✓ 1.0₱ sumado a {autor} | Tu cantidad de Pews es: {current_pews:.1f}₱")
                    except Exception as e:
                        logging.error(f"Error procesando ganancia de puntos en YouTube: {e}")

                    # --- COMANDO !pew / !pews / !puntos PARA CONSULTAR PEWS ---
                    if mensaje in ["!pew", "!pews", "!puntos"]:
                        try:
                            user_info = get_user_points(canal_id)
                            if user_info:
                                pews = user_info.get("puntos", 0)
                                await send_message_async(youtube, f"{autor} tienes {pews:.1f}₱")
                            else:
                                await send_message_async(youtube, f"{autor} aún no tienes pews registrados.")
                        except Exception as e:
                            logging.error(f"Error consultando pews: {e}")
                            await send_message_async(youtube, f"{autor} error al consultar tus pews.")
                    
                    # --- COMANDO !pew / !pews / !puntos <usuario|ID> PARA CONSULTAR PEWS DE OTRO USUARIO ---
                    elif any(mensaje.startswith(alias) for alias in ["!pew ", "!pews ", "!puntos "]):
                        try:
                            # Determinar parámetro posterior al comando
                            usuario_buscar = None
                            for alias in ["!pew ", "!pews ", "!puntos "]:
                                if mensaje.startswith(alias):
                                    usuario_buscar = mensaje[len(alias):].strip()
                                    break
                            if not usuario_buscar:
                                # Sin parámetro: manejar como propio (ya cubierto por el bloque anterior), aquí ignoramos
                                pass
                            else:
                                # Remover @ si está presente
                                if usuario_buscar.startswith("@"):
                                    usuario_buscar = usuario_buscar[1:]

                                usuario_encontrado = find_user_by_query(usuario_buscar, allow_partial=True)

                                if usuario_encontrado:
                                    uid = usuario_encontrado.get("id") or usuario_encontrado.get("discord_id") or usuario_encontrado.get("youtube_id")
                                    info = get_user_points(uid) if uid else usuario_encontrado
                                    pews = info.get("puntos", 0) if info else 0
                                    nombre = usuario_encontrado.get("name", usuario_buscar)
                                    await send_message_async(youtube, f"{nombre} tiene {pews:.1f}₱")
                                else:
                                    await send_message_async(youtube, f"Usuario '{usuario_buscar}' no encontrado en el registro.")
                        except Exception as e:
                            logging.error(f"Error consultando pews de usuario: {e}")
                            await send_message_async(youtube, f"{autor} error al consultar pews del usuario.")

                    # --- COMANDO !mod SOLO PARA MODERADORES ---
                    if mensaje == "!mod":
                        if canal_id in mods:
                            await send_message_async(youtube, f"{autor} ¡Eres moderador!")
                        else:
                            # No responder si no es moderador, o puedes poner un mensaje si lo deseas
                            pass

                    # --- COMANDO !miembro SOLO PARA MIEMBROS ---
                    if mensaje == "!miembro":
                        if canal_id in members:
                            await send_message_async(youtube, f"{autor} ¡Eres miembro del canal!")
                        else:
                            # No responder si no es miembro
                            pass

                    # --- COMANDO !custom SOLO PARA USUARIOS CUSTOM ---
                    if mensaje == "!custom":
                        if canal_id in custom_users:
                            custom_msg = custom_users[canal_id].get("custom_message", "¡Eres un usuario especial!")
                            await send_message_async(youtube, f"{autor} {custom_msg}")
                        else:
                            # No responder si no es custom
                            pass

                    # --- COMANDO !vincular <CODIGO> PARA VINCULAR CUENTAS ---
                    if mensaje.startswith("!vincular "):
                        try:
                            code = mensaje.replace("!vincular ", "").strip().upper()
                            
                            # Validar el código - Primero BD, luego fallback local
                            pending_link = None
                            
                            # Ensegurar DB inicializada
                            if not db_manager or not db_manager.is_connected:
                                init_database()
                            
                            # Intentar obtener de BD primero
                            if db_manager and db_manager.is_connected:
                                pending_link = db_manager.get_pending_link(code)
                                if pending_link:
                                    # Validar que no haya expirado usando expires_at de BD
                                    expires_at = pending_link.get('expires_at')
                                    if expires_at:
                                        if isinstance(expires_at, str):
                                            expires_at = datetime.fromisoformat(expires_at)
                                        if datetime.now() > expires_at:
                                            # Código expirado
                                            print(f"⚠ Código {code} expirado en BD")
                                            pending_link = None
                            
                            # Si no está en BD, intentar fallback local
                            if not pending_link:
                                pending_link = account_linking_manager.get_pending_link(code)
                            
                            if pending_link:
                                discord_id = pending_link['discord_id']
                                discord_name = pending_link['discord_name']

                                # IMPORTANTE: Asegurar que el usuario de YouTube está completamente cacheado ANTES de vincular
                                # Esto garantiza que los puntos ganados en YouTube se transferirán correctamente
                                cache_user_info(canal_id, autor, avatar_url, is_moderator, is_member)

                                # Recargar el cache después de actualizar info del usuario
                                user_cache = load_user_cache()

                                # Evitar re-vincular si ya está unido
                                linked_youtube = next(
                                    (u for u in user_cache.get("users", []) if u.get("youtube_id") == canal_id and u.get("discord_id")),
                                    None
                                )
                                if linked_youtube:
                                    await send_message_async(
                                        youtube,
                                        f"{autor} tu cuenta de YouTube ya está vinculada con Discord (ID {linked_youtube.get('discord_id')}). Usa !desvincular si quieres cambiar."
                                    )
                                    continue

                                linked_discord = next(
                                    (u for u in user_cache.get("users", []) if u.get("discord_id") == str(discord_id) and u.get("youtube_id")),
                                    None
                                )
                                if linked_discord:
                                    await send_message_async(
                                        youtube,
                                        f"{autor} la cuenta de Discord @{discord_name} ya está vinculada con otro canal de YouTube. Usa /desvincular en Discord si quieres cambiar."
                                    )
                                    continue
                                
                                # Vincular las cuentas
                                result = link_accounts(discord_id, canal_id)
                                
                                if result:
                                    # Eliminar el código usado - de BD y de JSON local
                                    if db_manager and db_manager.is_connected:
                                        db_manager.delete_pending_link(code)
                                        print(f"✓ Código {code} eliminado de BD")
                                    
                                    account_linking_manager.remove_pending_link(code)
                                    print(f"✓ Código {code} eliminado de JSON local")
                                    
                                    # Notificar éxito
                                    total_pews = result.get('puntos', 0)
                                    await send_message_async(youtube, 
                                        f"✓ {autor} ¡Cuentas vinculadas exitosamente! "
                                        f"Discord (@{discord_name}) + YouTube ({autor}) "
                                        f"= {total_pews:.1f}₱ combinados")
                                    print(f"✓ Cuentas vinculadas: Discord {discord_name} ({discord_id}) + YouTube {autor} ({canal_id})")
                                    
                                    # Enviar log al canal de Discord
                                    try:
                                        # Importación dinámica para obtener la instancia más reciente
                                        from discordbot.dcbot import discord_bot_instance as bot_instance, bot_loop
                                        if bot_instance and hasattr(bot_instance, 'send_log') and bot_loop:
                                            # Usar asyncio.run_coroutine_threadsafe para ejecutar en el event loop del bot
                                            future = asyncio.run_coroutine_threadsafe(
                                                bot_instance.send_log(
                                                    f"Discord: {discord_name}\n"
                                                    f"ID Discord: {discord_id}\n\n"
                                                    f"YouTube: {autor}\n"
                                                    f"ID Canal: {canal_id}\n\n"
                                                    f"Puntos totales: {total_pews:.1f}₱",
                                                    "SUCCESS"
                                                ),
                                                bot_loop
                                            )
                                            # Esperar a que se complete con timeout
                                            future.result(timeout=5)
                                            print(f"✓ Log de vinculación enviado a Discord")
                                        else:
                                            print("⚠ discord_bot_instance no disponible para enviar log")
                                    except Exception as e:
                                        print(f"⚠ Error enviando log de vinculación: {e}")
                                        import traceback
                                        traceback.print_exc()
                                else:
                                    await send_message_async(youtube, f"{autor} error al vincular las cuentas.")
                            else:
                                await send_message_async(youtube, 
                                    f"{autor} código inválido o expirado. "
                                    f"Usa /vincular en Discord para obtener un código nuevo.")
                        except Exception as e:
                            logging.error(f"Error vinculando cuentas: {e}")
                            await send_message_async(youtube, f"{autor} error al procesar la vinculación.")

                    # --- COMANDO !desvincular PARA DESVINCULAR CUENTAS ---
                    if mensaje == "!desvincular":
                        try:
                            # Desvincular pero mantener YouTube como plataforma principal
                            result = unlink_account(canal_id, "youtube")
                            
                            if result:
                                puntos = result.get('puntos', 0)
                                await send_message_async(youtube, 
                                    f"✓ {autor} Tu cuenta de Discord ha sido desvinculada. "
                                    f"Tus {puntos:.1f}₱ permanecen en YouTube.")
                                print(f"✓ Desvinculación YouTube: {autor} ({canal_id}) se desvinculó de Discord")
                                
                                # Enviar log al canal de Discord
                                try:
                                    from discordbot.dcbot import discord_bot_instance as bot_instance, bot_loop
                                    if bot_instance and hasattr(bot_instance, 'send_log') and bot_loop:
                                        # Buscar información de Discord vinculada
                                        discord_info = result.get("discord_id", "No registrado")
                                        discord_name = None
                                        # Intentar obtener el nombre de Discord del resultado
                                        for user in user_cache.get("users", []):
                                            if user.get("youtube_id") == canal_id and user.get("discord_id"):
                                                discord_name = user.get("name", "Usuario")
                                                break
                                        
                                        future = asyncio.run_coroutine_threadsafe(
                                            bot_instance.send_log(
                                                f"YouTube: {autor}\n"
                                                f"ID Canal: {canal_id}\n\n"
                                                f"Discord: {discord_name or 'Usuario'}\n"
                                                f"ID Discord: {discord_info}\n\n"
                                                f"Puntos mantenidos en YouTube: {puntos:.1f}₱",
                                                "INFO"
                                            ),
                                            bot_loop
                                        )
                                        future.result(timeout=5)
                                        print(f"✓ Log de desvinculación enviado a Discord")
                                except Exception as e:
                                    print(f"⚠ Error enviando log de desvinculación: {e}")
                            else:
                                await send_message_async(youtube, 
                                    f"{autor} Tu cuenta no tiene vinculación con Discord.")
                        except Exception as e:
                            logging.error(f"Error desvinculando en YouTube: {e}")
                            await send_message_async(youtube, f"{autor} error al desvincular tu cuenta.")

                    # --- COMANDO !dar / !give PARA TRANSFERIR PEWS ---
                    if mensaje.startswith(("!dar ", "!give ")):
                        try:
                            # Obtener el prefijo usado
                            prefix = "!dar " if mensaje.startswith("!dar ") else "!give "
                            partes = mensaje[len(prefix):].split()
                            
                            if len(partes) < 2:
                                await send_message_async(youtube, f"{autor} Uso: {prefix.strip()} <usuario o ID> <cantidad o 'all'>")
                                continue
                            
                            usuario_destino_str = partes[0]
                            cantidad_str = partes[1]
                            
                            # Buscar usuario destino por nombre o ID
                            usuario_destino = None
                            usuario_destino_nombre = None
                            usuario_destino_id = None
                            
                            # Si es un número, buscar por ID
                            if usuario_destino_str.isdigit():
                                for user in user_cache.get("users", []):
                                    if str(user.get("id")) == usuario_destino_str:
                                        usuario_destino = user
                                        usuario_destino_id = user.get("youtube_id") or user.get("discord_id")
                                        usuario_destino_nombre = user.get("name", usuario_destino_str)
                                        break
                            else:
                                # Buscar por nombre (case-insensitive)
                                usuario_destino_lower = usuario_destino_str.lower()
                                for user in user_cache.get("users", []):
                                    if user.get("name", "").lower() == usuario_destino_lower:
                                        usuario_destino = user
                                        usuario_destino_id = user.get("youtube_id") or user.get("discord_id")
                                        usuario_destino_nombre = user.get("name", usuario_destino_str)
                                        break
                            
                            if not usuario_destino:
                                await send_message_async(youtube, f"{autor} El usuario '{usuario_destino_str}' no existe o no se encontró.")
                                continue
                            
                            # Obtener puntos del donante
                            usuario_donante = get_user_points(canal_id)
                            if not usuario_donante:
                                await send_message_async(youtube, f"{autor} Error: No se encontró tu información.")
                                continue
                            
                            puntos_donante = usuario_donante.get("puntos", 0)
                            
                            # Determinar cantidad a transferir
                            if cantidad_str.lower() == "all":
                                cantidad_transferir = puntos_donante
                            else:
                                if not cantidad_str.replace(".", "").isdigit():
                                    await send_message_async(youtube, f"{autor} La cantidad debe ser un número válido o 'all'.")
                                    continue
                                cantidad_transferir = float(cantidad_str)
                            
                            # Validar cantidad
                            if cantidad_transferir <= 0:
                                await send_message_async(youtube, f"{autor} La cantidad debe ser mayor a 0.")
                                continue
                            
                            if cantidad_transferir > puntos_donante:
                                await send_message_async(youtube, 
                                    f"{autor} No tienes suficientes pews. "
                                    f"Tienes: {puntos_donante:.1f}₱ y quieres dar: {cantidad_transferir:.1f}₱")
                                continue
                            
                            # Realizar transferencia
                            donor_before = puntos_donante
                            donor_result = add_points_to_user(canal_id, -cantidad_transferir)
                            destino_info_before = get_user_points(usuario_destino_id)
                            destino_before = destino_info_before.get("puntos", 0) if destino_info_before else 0
                            resultado = add_points_to_user(usuario_destino_id, cantidad_transferir)
                            
                            if resultado and donor_result:
                                donor_after = donor_result.get("puntos", 0)
                                puntos_finales_destino = resultado.get("puntos", 0)
                                # Loggear envío y recepción
                                transaction_logger.log_transaction(
                                    user_id=canal_id,
                                    username=autor,
                                    platform="youtube",
                                    transaction_type="transfer_send",
                                    amount=-cantidad_transferir,
                                    balance_after=donor_after
                                )
                                transaction_logger.log_transaction(
                                    user_id=usuario_destino_id,
                                    username=usuario_destino_nombre,
                                    platform="youtube",
                                    transaction_type="transfer_receive",
                                    amount=cantidad_transferir,
                                    balance_after=puntos_finales_destino
                                )
                                # Mensaje de confirmación
                                await send_message_async(youtube, 
                                    f"✓ {autor} ha transferido {cantidad_transferir:.1f}₱ a {usuario_destino_nombre}. "
                                    f"({usuario_destino_nombre} ahora tiene {puntos_finales_destino:.1f}₱)")
                                print(f"✓ Transferencia: {autor} → {usuario_destino_nombre} = {cantidad_transferir:.1f}₱")
                            else:
                                await send_message_async(youtube, f"{autor} Error al transferir los pews.")
                        except Exception as e:
                            logging.error(f"Error en comando !dar/!give: {e}")
                            await send_message_async(youtube, f"{autor} Error procesando la transferencia.")

                    # --- COMANDO !quitar / !castigar / !rps PARA RESTAR PEWS (SOLO CUSTOM) ---
                    if mensaje.startswith(("!quitar ", "!castigar ", "!rps ")):
                        try:
                            # Verificar que sea usuario custom
                            if canal_id not in custom_users:
                                await send_message_async(youtube, f"{autor} Solo usuarios especiales pueden usar este comando.")
                                continue
                            
                            # Obtener prefijo usado
                            if mensaje.startswith("!quitar "):
                                prefix = "!quitar "
                            elif mensaje.startswith("!castigar "):
                                prefix = "!castigar "
                            else:
                                prefix = "!rps "
                            
                            partes = mensaje[len(prefix):].split()
                            
                            if len(partes) < 2:
                                await send_message_async(youtube, f"{autor} Uso: {prefix.strip()} <@usuario o ID> <cantidad o 'all'>")
                                continue
                            
                            usuario_castigo_str = partes[0]
                            cantidad_str = partes[1]
                            
                            # Construir versión limpia solo para búsqueda (sin @)
                            usuario_castigo_str_limpio = usuario_castigo_str[1:] if usuario_castigo_str.startswith("@") else usuario_castigo_str
                            
                            # Buscar usuario a castigar
                            usuario_castigo = None
                            usuario_castigo_nombre = None
                            usuario_castigo_id = None
                            
                            # Si es número, buscar por ID
                            if usuario_castigo_str_limpio.isdigit():
                                for user in user_cache.get("users", []):
                                    if str(user.get("id")) == usuario_castigo_str_limpio:
                                        usuario_castigo = user
                                        # Preferir YouTube ID si existe
                                        usuario_castigo_id = user.get("youtube_id") if user.get("youtube_id") else user.get("discord_id")
                                        usuario_castigo_nombre = user.get("name", usuario_castigo_str_limpio)
                                        break
                            else:
                                # Buscar por nombre (normalizado y soporte parcial)
                                usuario_castigo_lower = usuario_castigo_str_limpio.lower()
                                for user in user_cache.get("users", []):
                                    name_val = (user.get("name", "") or "").strip()
                                    name_lower = name_val.lower()
                                    if name_lower == usuario_castigo_lower or usuario_castigo_lower in name_lower:
                                        usuario_castigo = user
                                        # Preferir YouTube ID si existe
                                        usuario_castigo_id = user.get("youtube_id") if user.get("youtube_id") else user.get("discord_id")
                                        usuario_castigo_nombre = name_val
                                        break
                            
                            if not usuario_castigo:
                                await send_message_async(youtube, f"{autor} El usuario '{usuario_castigo_str}' no existe.")
                                continue
                            
                            # Obtener puntos del usuario a castigar
                            info_castigo = get_user_points(usuario_castigo_id)
                            if not info_castigo:
                                await send_message_async(youtube, f"{autor} Error: No se encontró información del usuario.")
                                continue
                            
                            puntos_castigo = info_castigo.get("puntos", 0)
                            
                            # Determinar cantidad a restar
                            if cantidad_str.lower() == "all":
                                cantidad_restar = puntos_castigo
                            else:
                                if not cantidad_str.replace(".", "").isdigit():
                                    await send_message_async(youtube, f"{autor} La cantidad debe ser un número válido o 'all'.")
                                    continue
                                cantidad_restar = float(cantidad_str)
                            
                            # Validar cantidad
                            if cantidad_restar <= 0:
                                await send_message_async(youtube, f"{autor} La cantidad debe ser mayor a 0.")
                                continue
                            
                            if cantidad_restar > puntos_castigo:
                                cantidad_restar = puntos_castigo
                            
                            # Realizar resta
                            resultado = add_points_to_user(usuario_castigo_id, -cantidad_restar)
                            
                            if resultado:
                                puntos_finales = resultado.get("puntos", 0)
                                transaction_logger.log_transaction(
                                    user_id=usuario_castigo_id,
                                    username=usuario_castigo_nombre,
                                    platform="youtube",
                                    transaction_type="punishment",
                                    amount=-cantidad_restar,
                                    balance_after=puntos_finales
                                )
                                # Mensaje diferente según el comando usado
                                if mensaje.startswith("!castigar "):
                                    await send_message_async(youtube, 
                                        f"⚠ {usuario_castigo_nombre} ha sido castigado. "
                                        f"Se le restaron {cantidad_restar:.1f}₱ "
                                        f"(Puntos actuales: {puntos_finales:.1f}₱)")
                                else:
                                    await send_message_async(youtube, 
                                        f"✓ {cantidad_restar:.1f}₱ removidos de {usuario_castigo_nombre} "
                                        f"(Puntos actuales: {puntos_finales:.1f}₱)")
                                
                                print(f"✓ Castigo ({prefix.strip()}): {autor} → {usuario_castigo_nombre} = -{cantidad_restar:.1f}₱")
                            else:
                                await send_message_async(youtube, f"{autor} Error al aplicar el castigo.")
                        except Exception as e:
                            logging.error(f"Error en comando de castigo: {e}")
                            await send_message_async(youtube, f"{autor} Error procesando el castigo.")

                    # --- COMANDO !apsall (SOLO CUSTOM) PARA DAR PUNTOS A TODOS LOS ACTIVOS ---
                    if mensaje.startswith("!apsall "):
                        if canal_id in custom_users:
                            try:
                                partes = mensaje.split()
                                if len(partes) < 2:
                                    await send_message_async(youtube, f"{autor} Uso: !apsall <cantidad>")
                                    continue
                                
                                cantidad_str = partes[1]
                                
                                # Parsear cantidad
                                try:
                                    cantidad_por_usuario = int(float(cantidad_str))
                                except ValueError:
                                    await send_message_async(youtube, f"{autor} Cantidad inválida. Usa un número.")
                                    continue
                                
                                if cantidad_por_usuario <= 0:
                                    await send_message_async(youtube, f"{autor} La cantidad debe ser mayor a 0.")
                                    continue
                                
                                # Obtener usuarios activos en últimos 5 minutos
                                activos = get_active_users_in_window(minutes=5)
                                
                                if not activos:
                                    await send_message_async(youtube, f"{autor} No hay usuarios activos en los últimos 5 minutos.")
                                    continue
                                
                                # Distribuir puntos
                                usuarios_actualizados = []
                                for uid, nombre in activos:
                                    info_before = get_user_points(uid)
                                    balance_before = info_before.get("puntos", 0) if info_before else 0
                                    result = add_points_to_user(uid, cantidad_por_usuario)
                                    if result:
                                        usuarios_actualizados.append(nombre)
                                        current_pews = result.get("puntos", 0)
                                        transaction_logger.log_transaction(
                                            user_id=uid,
                                            username=nombre,
                                            platform="youtube",
                                            transaction_type="apsall",
                                            amount=cantidad_por_usuario,
                                            balance_after=current_pews
                                        )
                                        print(f"  ✓ {cantidad_por_usuario}₱ → {nombre} (Total: {current_pews:.1f}₱)")
                                
                                # Confirmación
                                total_puntos = cantidad_por_usuario * len(usuarios_actualizados)
                                await send_message_async(
                                    youtube,
                                    f"✓ {autor} distribuyó {total_puntos:,}₱ entre {len(usuarios_actualizados)} usuario(s) activo(s)"
                                )
                                print(f"✓ !apsall: {cantidad_por_usuario}₱ x {len(usuarios_actualizados)} usuarios = {total_puntos}₱ distribuidos")
                                
                            except Exception as e:
                                logging.error(f"Error en comando !apsall: {e}")
                                await send_message_async(youtube, f"{autor} error al ejecutar !apsall.")
                        else:
                            pass
                    
                    # --- COMANDO !aps / !premiar (SOLO CUSTOM) PARA AÑADIR PEWS ---
                    if mensaje.startswith(("!aps ", "!premiar ")):
                        try:
                            # Verificar que sea usuario custom
                            if canal_id not in custom_users:
                                await send_message_async(youtube, f"{autor} Solo usuarios especiales pueden usar este comando.")
                                continue

                            prefix = "!aps " if mensaje.startswith("!aps ") else "!premiar "
                            partes = mensaje[len(prefix):].split()

                            if len(partes) < 2:
                                await send_message_async(youtube, f"{autor} Uso: !aps/!premiar <usuario o ID> <cantidad o 'all'>")
                                continue

                            usuario_destino_str = partes[0]
                            cantidad_str = partes[1]

                            # Construir versión limpia solo para búsqueda (sin @)
                            usuario_destino_str_limpio = usuario_destino_str[1:] if usuario_destino_str.startswith("@") else usuario_destino_str

                            # Buscar usuario destino por nombre o ID (exacto o parcial)
                            usuario_destino = None
                            usuario_destino_nombre = None
                            usuario_destino_id = None

                            if usuario_destino_str_limpio.isdigit():
                                for user in user_cache.get("users", []):
                                    if str(user.get("id")) == usuario_destino_str_limpio:
                                        usuario_destino = user
                                        usuario_destino_id = user.get("youtube_id") if user.get("youtube_id") else user.get("discord_id")
                                        usuario_destino_nombre = user.get("name", usuario_destino_str_limpio)
                                        break
                            else:
                                usuario_destino_lower = usuario_destino_str_limpio.lower()
                                for user in user_cache.get("users", []):
                                    name_val = (user.get("name", "") or "").strip()
                                    name_lower = name_val.lower()
                                    if name_lower == usuario_destino_lower or usuario_destino_lower in name_lower:
                                        usuario_destino = user
                                        usuario_destino_id = user.get("youtube_id") if user.get("youtube_id") else user.get("discord_id")
                                        usuario_destino_nombre = name_val
                                        break

                            if not usuario_destino:
                                await send_message_async(youtube, f"{autor} El usuario '{usuario_destino_str}' no existe o no se encontró.")
                                continue

                            # Determinar cantidad a añadir
                            if cantidad_str.lower() == "all":
                                # Usar los pews del emisor (admin/custom) como cantidad de referencia
                                admin_info = get_user_points(canal_id)
                                if not admin_info:
                                    await send_message_async(youtube, f"{autor} Error: No se pudo obtener tu información para 'all'.")
                                    continue
                                cantidad_aniadir = admin_info.get("puntos", 0)
                            else:
                                if not cantidad_str.replace(".", "").isdigit():
                                    await send_message_async(youtube, f"{autor} La cantidad debe ser un número válido o 'all'.")
                                    continue
                                cantidad_aniadir = float(cantidad_str)

                            # Validaciones
                            if cantidad_aniadir <= 0:
                                await send_message_async(youtube, f"{autor} La cantidad debe ser mayor a 0.")
                                continue

                            # Añadir puntos
                            destino_info = get_user_points(usuario_destino_id)
                            balance_before = destino_info.get("puntos", 0) if destino_info else 0
                            resultado = add_points_to_user(usuario_destino_id, cantidad_aniadir)
                            if resultado:
                                puntos_finales = resultado.get("puntos", 0)
                                transaction_logger.log_transaction(
                                    user_id=usuario_destino_id,
                                    username=usuario_destino_nombre,
                                    platform="youtube",
                                    transaction_type="reward",
                                    amount=cantidad_aniadir,
                                    balance_after=puntos_finales
                                )
                                # Mensajería según comando
                                if prefix.strip() == "!premiar":
                                    premio_msg = (
                                        f"🎉 {usuario_destino_nombre} ha sido premiado con {cantidad_aniadir:.1f}₱ "
                                        f"(Ahora tiene {puntos_finales:.1f}₱)"
                                    )
                                    await send_message_async(youtube, premio_msg)
                                    print(f"✓ Premio (!premiar): {autor} → {usuario_destino_nombre} = +{cantidad_aniadir:.1f}₱")
                                else:
                                    await send_message_async(youtube,
                                        f"✓ {autor} ha añadido {cantidad_aniadir:.1f}₱ a {usuario_destino_nombre}. "
                                        f"(Ahora tiene {puntos_finales:.1f}₱)")
                                    print(f"✓ Aporte (!aps): {autor} → {usuario_destino_nombre} = +{cantidad_aniadir:.1f}₱")
                            else:
                                await send_message_async(youtube, f"{autor} Error al añadir los pews.")
                        except Exception as e:
                            logging.error(f"Error en comando !aps: {e}")
                            await send_message_async(youtube, f"{autor} Error procesando el aporte.")

                    # --- COMANDO !comprar / !co PARA COMPRAR ITEMS DE LA TIENDA ---
                    if mensaje.startswith(("!comprar ", "!co ")):
                        try:
                            # Verificar que la tienda esté disponible
                            if not store_manager:
                                await send_message_async(youtube, f"{autor} La tienda no está disponible en este momento.")
                                continue
                            
                            # Extraer item_id del comando
                            partes = mensaje.split(maxsplit=1)
                            if len(partes) < 2:
                                await send_message_async(youtube, f"{autor} Uso: !comprar <item_id> o !co <item_id>")
                                continue
                            
                            item_id = partes[1].strip().lower()
                            
                            # Escanear items disponibles
                            items = store_manager.scan_store_items()
                            item_encontrado = None
                            
                            for item in items:
                                if item['id'].lower() == item_id:
                                    item_encontrado = item
                                    break
                            
                            if not item_encontrado:
                                await send_message_async(youtube, f"{autor} Item '{item_id}' no encontrado en la tienda.")
                                continue
                            
                            # Obtener precio dinámico (con inflación)
                            precio_final = store_manager.get_dynamic_price(
                                item_id=item_encontrado['id'],
                                item_config=item_encontrado.get('config', {})
                            )
                            
                            # Verificar puntos del usuario
                            user_data = get_user_points(canal_id)
                            if not user_data:
                                await send_message_async(youtube, f"{autor} No tienes puntos registrados.")
                                continue
                            
                            puntos_actuales = user_data.get("puntos", 0)
                            
                            # Verificar saldo suficiente
                            if puntos_actuales < precio_final:
                                await send_message_async(youtube, 
                                    f"{autor} Saldo insuficiente. Tienes {puntos_actuales:.1f}₱, necesitas {precio_final:.1f}₱")
                                continue
                            
                            # Cobrar puntos
                            from usermanager import subtract_points_from_user
                            resultado = subtract_points_from_user(canal_id, int(precio_final))
                            
                            if not resultado:
                                await send_message_async(youtube, f"{autor} Error al procesar el pago.")
                                continue
                            
                            nuevo_saldo = resultado.get("puntos", 0)
                            
                            # Registrar venta (esto aumenta la inflación)
                            store_manager.record_sale(item_encontrado['id'])
                            
                            # Calcular inflación actual para mostrar
                            inflacion_actual = store_manager.calculate_inflation(item_encontrado['id'])
                            transaction_logger.log_transaction(
                                user_id=canal_id,
                                username=autor,
                                platform="youtube",
                                transaction_type="store_purchase",
                                amount=-precio_final,
                                balance_after=nuevo_saldo
                            )
                            
                            # Enviar notificación por WebSocket (MISMO FORMATO QUE DISCORD)
                            try:
                                print(f"📡 Intentando enviar notificación por WebSocket...")
                                notification_data = {
                                    "type": "notification",
                                    "notificationId": item_encontrado['id'],
                                    "userId": canal_id,
                                    "itemName": item_encontrado['name'],
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                                print(f"   Datos a enviar: {notification_data}")
                                await server.send_update(notification_data)
                                print(f"✓ Notificación enviada por WebSocket: {autor} compró {item_encontrado['name']}")
                            except Exception as ws_error:
                                print(f"⚠ Error enviando notificación WebSocket: {ws_error}")
                            
                            # Responder al usuario
                            await send_message_async(youtube, 
                                f"✓ {autor} compraste '{item_encontrado['name']}' por {precio_final:.1f}₱. "
                                f"Nuevo saldo: {nuevo_saldo:.1f}₱")
                            
                            print(f"🛒 Compra en YouTube: {autor} ({canal_id}) compró '{item_encontrado['name']}' "
                                  f"por {precio_final:.1f}₱. Inflación: {inflacion_actual:.1f}%")
                            
                        except Exception as e:
                            logging.error(f"Error en comando !comprar: {e}")
                            await send_message_async(youtube, f"{autor} Error procesando la compra.")

                    # --- COMANDO !tienda / !shop PARA VER ITEMS DISPONIBLES ---
                    if mensaje in ["!tienda", "!shop"]:
                        try:
                            if not store_manager:
                                await send_message_async(youtube, f"{autor} La tienda no está disponible en este momento.")
                                continue
                            
                            items = store_manager.scan_store_items()
                            
                            if not items:
                                await send_message_async(youtube, f"{autor} La tienda está vacía.")
                                continue
                            
                            # Mostrar primeros 5 items
                            items_mostrar = items[:5]
                            respuesta = f"🛒 Tienda ({len(items)} items): "
                            
                            for item in items_mostrar:
                                precio = store_manager.get_dynamic_price(item['id'], item.get('config', {}))
                                inflacion = store_manager.calculate_inflation(item['id'])
                                
                                if inflacion > 0:
                                    respuesta += f"{item['name']} ({item['id']}) {precio:.1f}₱ (+{inflacion:.0f}%), "
                                else:
                                    respuesta += f"{item['name']} ({item['id']}) {precio:.1f}₱, "
                            
                            respuesta = respuesta.rstrip(", ")
                            if len(items) > 5:
                                respuesta += f" ... y {len(items) - 5} más."
                            
                            await send_message_async(youtube, respuesta)
                            
                        except Exception as e:
                            logging.error(f"Error en comando !tienda: {e}")
                            await send_message_async(youtube, f"{autor} Error mostrando la tienda.")

                    # --- COMANDO !gamble / !g PARA APOSTAR PEWS ---
                    if mensaje.startswith(("!gamble ", "!g ")):
                        try:
                            from activities.Jackpot import calculate_gamble_result, validate_gamble
                            from backend.config import GAMBLE_MAX_BET
                            
                            parts = mensaje.split()
                            if len(parts) < 2:
                                await send_message_async(youtube, f"{autor} Usa: !gamble <cantidad> o !g <cantidad>")
                                continue
                            
                            cantidad_str = parts[1]
                            
                            # Obtener puntos actuales del usuario (considerando vinculación)
                            user_info = get_user_points(canal_id)
                            puntos_actuales = user_info.get("puntos", 0) if user_info else 0
                            
                            # Determinar cantidad a apostar (permitir decimales, máximo 2)
                            if cantidad_str.lower() == "all":
                                bet_amount = round(float(puntos_actuales), 2)
                            else:
                                try:
                                    bet_amount = round(float(cantidad_str), 2)
                                except ValueError:
                                    await send_message_async(youtube, f"{autor} Cantidad inválida. Usa un número o 'all'.")
                                    continue
                            
                            # Validar apuesta (incluye límite máximo)
                            es_valido, mensaje_error = validate_gamble(puntos_actuales, bet_amount, GAMBLE_MAX_BET)
                            if not es_valido:
                                await send_message_async(youtube, f"{autor} {mensaje_error}")
                                continue
                            
                            # Calcular resultado
                            roll, ganancia_neta, multiplicador, rango = calculate_gamble_result(bet_amount)
                            
                            # Actualizar puntos (permitiendo decimales)
                            add_points_to_user(canal_id, ganancia_neta)
                            puntos_finales = round(puntos_actuales + ganancia_neta, 2)
                            transaction_logger.log_transaction(
                                user_id=canal_id,
                                username=autor,
                                platform="youtube",
                                transaction_type="gamble_win" if ganancia_neta > 0 else "gamble_loss",
                                amount=ganancia_neta,
                                balance_after=puntos_finales
                            )
                            
                            # Generar mensaje simplificado con 2 decimales
                            if ganancia_neta > 0:
                                resultado = f"+{ganancia_neta:,.2f}₱"
                            elif ganancia_neta == 0:
                                resultado = "±0₱"
                            else:
                                resultado = f"{ganancia_neta:,.2f}₱"
                            
                            await send_message_async(
                                youtube,
                                f"{autor} 🎲 Roll {roll}/100 (x{multiplicador:.2f}) | {resultado} | Saldo: {puntos_finales:,.2f}₱"
                            )
                            
                        except Exception as e:
                            logging.error(f"Error en comando !gamble: {e}")
                            await send_message_async(youtube, f"{autor} Error procesando gamble.")

                    # --- COMANDO !tragamonedas / !tm PARA JUGAR SLOTS ---
                    if mensaje.startswith(("!tragamonedas ", "!tm ")):
                        try:
                            from activities.Jackpot import spin_slots, validate_gamble, increment_user_luck_multiplier, reset_user_luck_multiplier
                            from backend.config import TRAGAMONEDAS_MAX_BET
                            
                            parts = mensaje.split()
                            if len(parts) < 2:
                                await send_message_async(youtube, f"{autor} Usa: !tragamonedas <cantidad> o !tm <cantidad>")
                                continue
                            
                            cantidad_str = parts[1]
                            
                            # Obtener puntos actuales del usuario (considerando vinculación)
                            user_info = get_user_points(canal_id)
                            puntos_actuales = user_info.get("puntos", 0) if user_info else 0
                            
                            # Determinar cantidad a apostar
                            if cantidad_str.lower() == "all":
                                bet_amount = int(puntos_actuales)
                            else:
                                try:
                                    bet_amount = int(float(cantidad_str))
                                except ValueError:
                                    await send_message_async(youtube, f"{autor} Cantidad inválida. Usa un número o 'all'.")
                                    continue
                            
                            # Validar apuesta (incluye límite máximo)
                            es_valido, mensaje_error = validate_gamble(puntos_actuales, bet_amount, TRAGAMONEDAS_MAX_BET)
                            if not es_valido:
                                await send_message_async(youtube, f"{autor} {mensaje_error}")
                                continue
                            
                            # Realizar spin (usar ID del usuario para luck multiplier)
                            combo, ganancia_neta, multiplicador, descripcion, es_ganancia, luck_multiplier = spin_slots(bet_amount, canal_id)
                            
                            # Actualizar puntos
                            add_points_to_user(canal_id, ganancia_neta)
                            puntos_finales = puntos_actuales + ganancia_neta
                            transaction_logger.log_transaction(
                                user_id=canal_id,
                                username=autor,
                                platform="youtube",
                                transaction_type="slot_win" if ganancia_neta > 0 else "slot_loss",
                                amount=ganancia_neta,
                                balance_after=puntos_finales
                            )
                            
                            # Actualizar multiplicador de suerte
                            if es_ganancia:
                                reset_user_luck_multiplier(canal_id)
                            else:
                                increment_user_luck_multiplier(canal_id, 0.1)
                            
                            # Generar mensaje simplificado
                            combo_display = " ".join(combo)
                            if ganancia_neta > 0:
                                resultado = f"+{ganancia_neta:,}₱"
                            elif ganancia_neta == 0:
                                resultado = "Sin premio"
                            else:
                                resultado = f"{ganancia_neta:,}₱"
                            
                            await send_message_async(
                                youtube,
                                f"{autor} 🎰 {combo_display} | {descripcion} | {resultado} | Saldo: {puntos_finales:,}₱"
                            )
                            
                        except Exception as e:
                            logging.error(f"Error en comando !tragamonedas: {e}")
                            await send_message_async(youtube, f"{autor} Error procesando tragamonedas.")

                    # --- COMANDO !tv PARA REPRODUCIR TEXTO A VOZ ---
                    if mensaje.startswith(("!tv ", "!vt ")):
                        try:
                            # Extraer el texto después de !tv
                            texto = mensaje[4:].strip() if mensaje.startswith("!tv ") else mensaje[4:].strip()
                            
                            if not texto:
                                await send_message_async(youtube, f"{autor} Uso: !tv <texto a reproducir>")
                                continue
                            
                            # Calcular costo
                            costo = youtube_economy_manager.calculate_tts_cost(texto)
                            
                            # Obtener puntos actuales del usuario
                            user_info = get_user_points(canal_id)
                            puntos_actuales = user_info.get("puntos", 0) if user_info else 0
                            
                            # Validar que tenga suficientes puntos
                            if puntos_actuales < costo:
                                await send_message_async(
                                    youtube, 
                                    f"{autor} ❌ No tienes suficientes puntos. Necesitas {costo:.1f}₱ y tienes {puntos_actuales:.1f}₱"
                                )
                                continue
                            
                            # Descontar puntos
                            add_points_to_user(canal_id, -costo)
                            puntos_finales = round(puntos_actuales - costo, 2)
                            transaction_logger.log_transaction(
                                user_id=canal_id,
                                username=autor,
                                platform="youtube",
                                transaction_type="tts",
                                amount=-costo,
                                balance_after=puntos_finales
                            )
                            
                            # Reproducir audio
                            tts = TextToVoice(lang='es', slow=False)
                            tts.text_to_speech(texto)
                            
                            # Confirmar compra
                            await send_message_async(
                                youtube,
                                f"🔊 {autor} ha enviado correctamente el mensaje por: (-{costo:.1f}₱) | Saldo: {puntos_finales:.1f}₱"
                            )
                            
                            print(f"🔊 Text-to-Voice en YouTube: {autor} ({canal_id}) reprodujo '{texto}' "
                                  f"(-{costo:.1f}₱). Saldo: {puntos_finales:.1f}₱")
                            
                        except Exception as e:
                            logging.error(f"Error en comando !tv: {e}")
                            await send_message_async(youtube, f"{autor} Error reproduciendo audio.")

                    # --- COMANDO !code PARA CANJEAR CÓDIGO RECOMPENSABLE ---
                    if mensaje.startswith("!code "):
                        try:
                            codigo = mensaje[6:].strip().upper()
                            
                            if not codigo:
                                await send_message_async(youtube, f"{autor} Uso: !code <código>")
                                continue
                            
                            # Verificar código
                            es_valido, mensaje_resultado = code_manager.verify_code(codigo)
                            
                            if es_valido:
                                # Dar puntos al usuario
                                recompensa = code_manager.code_reward
                                user_info_before = get_user_points(canal_id)
                                balance_before = user_info_before.get("puntos", 0) if user_info_before else 0
                                add_points_to_user(canal_id, recompensa)
                                
                                # Obtener nuevo saldo
                                user_info = get_user_points(canal_id)
                                puntos_finales = user_info.get("puntos", 0) if user_info else 0
                                transaction_logger.log_transaction(
                                    user_id=canal_id,
                                    username=autor,
                                    platform="youtube",
                                    transaction_type="code_redeem",
                                    amount=recompensa,
                                    balance_after=puntos_finales
                                )
                                
                                # Enviar mensaje a todos
                                await send_message_async(
                                    youtube,
                                    f"🎁 ¡{autor} canjeó el código correctamente! +{recompensa}₱ | Saldo: {puntos_finales:.1f}₱"
                                )
                                
                                print(f"🎁 Código canjeado en YouTube: {autor} ({canal_id}) ganó {recompensa}₱")
                                
                                # Notificar a los clientes para remover el código de la pantalla
                                await server.send_update({
                                    'type': 'code_redeemed',
                                    'code': codigo
                                })
                            else:
                                # Respuesta privada del error (se muestra igual pero el bot lo sabe)
                                await send_message_async(youtube, f"{autor} ❌ {mensaje_resultado}")
                            
                        except Exception as e:
                            logging.error(f"Error en comando !code: {e}")
                            await send_message_async(youtube, f"{autor} Error procesando código.")

                    # --- COMANDO !ruleta SOLO PARA USUARIOS CUSTOM ---
                    if mensaje == "!ruleta":
                        if canal_id in custom_users:
                            if not config.ruleta_activa:
                                config.participantes_ruleta.clear()
                                await server.change_page("ruleta.html")
                                config.ruleta_activa = True
                                config.itstimetojoin = True
                                await send_message_async(youtube, f"{autor} ha iniciado una Ruleta! Escribe !participar para unirte")
                                print(f"Ruleta iniciada por usuario custom: {autor}")
                            else:
                                await send_message_async(youtube, f"{autor} Ya hay una ruleta activa.")
                        else:
                            # No responder si no es custom
                            pass

                    # --- COMANDO !rgirar SOLO PARA USUARIOS CUSTOM ---
                    if mensaje == "!rgirar":
                        if canal_id in custom_users:
                            if config.ruleta_activa:
                                await server.spin_wheel()
                                await send_message_async(youtube, f"{autor} Ha hecho girar la ruleta...")
                                print(f"Ruleta girada por usuario custom: {autor}")
                            else:
                                await send_message_async(youtube, f"{autor} No hay ruleta activa.")
                        else:
                            pass
                    # --- COMANDO !rkw SOLO PARA USUARIOS CUSTOM ---
                    if mensaje == "!rkw":
                        if canal_id in custom_users:
                            if config.ruleta_activa:
                                config.keepwinner = not config.keepwinner
                                await server.keepwinner(config.keepwinner)
                                await send_message_async(youtube, f"Mantenter ganador ha sido {'activado' if config.keepwinner else 'desactivado'} por {autor}.")
                                print(f"Mantenter ganador ha sido {'activado' if config.keepwinner else 'desactivado'}.")

                            else:
                                await send_message_async(youtube, f"{autor} No hay ruleta activa.")
                        else:
                            pass

                    # --- COMANDO !ropen SOLO PARA USUARIOS CUSTOM ---
                    if mensaje == "!ropen":
                        if canal_id in custom_users:
                            if config.ruleta_activa:
                                config.itstimetojoin = True
                                await send_message_async(youtube, f"{autor} ha abierto la ruleta para unirse!")
                                print(f"Ruleta abierta por usuario custom: {autor}")
                            else:
                                await send_message_async(youtube, f"{autor} No hay ruleta activa.")
                        else:
                            pass

                    # --- COMANDO !rclose SOLO PARA USUARIOS CUSTOM ---
                    if mensaje == "!rclose":
                        if canal_id in custom_users:
                            if config.ruleta_activa:
                                config.itstimetojoin = False
                                await send_message_async(youtube, f"{autor} ha cerrado la ruleta. Ya no se puede unir.")
                                print(f"Ruleta cerrada por usuario custom: {autor}")
                            else:
                                await send_message_async(youtube, f"{autor} No hay ruleta activa.")
                        else:
                            pass

                    # --- COMANDO !rend SOLO PARA USUARIOS CUSTOM ---
                    if mensaje == "!rend":
                        if canal_id in custom_users:
                            if config.ruleta_activa:
                                config.ruleta_activa = False
                                config.itstimetojoin = False
                                config.participantes_ruleta.clear()
                                await server.reset_wheel()
                                await server.change_page("index.html")
                                await send_message_async(youtube, f"{autor} ha terminado la ruleta.")
                                print(f"Ruleta terminada por usuario custom: {autor}")
                            else:
                                await send_message_async(youtube, f"{autor} No hay ruleta activa.")
                        else:
                            pass

                    # --- COMANDO !rmini SOLO PARA USUARIOS CUSTOM ---
                    if mensaje == "!rmini":
                        if canal_id in custom_users:
                            if config.ruleta_activa:
                                await server.toggle_mini()
                                await send_message_async(youtube, f"{autor} ha cambiado el modo de la ruleta.")
                                print(f"Modo mini de ruleta cambiado por: {autor}")
                            else:
                                await send_message_async(youtube, f"{autor} No hay ruleta activa para minimizar.")
                        else:
                            pass

                    # --- CREAR ENCUESTA VIA CHAT (!e, opciones, /time) SOLO CUSTOM ---
                    builder = poll_builders.get(canal_id)

                    # Iniciar construcción y redirigir inmediatamente
                    if mensaje.startswith("!e "):
                        if canal_id in custom_users:
                            if config.encuesta_activa:
                                await send_message_async(youtube, f"{autor} Ya hay una encuesta activa.")
                            elif poll_builders:
                                await send_message_async(youtube, f"{autor} Ya hay otra encuesta en preparación.")
                            else:
                                titulo_encuesta = mensaje_raw[3:].strip()
                                if titulo_encuesta:
                                    poll_builders[canal_id] = {"title": titulo_encuesta, "options": []}
                                    # Log opcional: print(f"[Encuesta] Redirigiendo a poll.html y poniendo título: {titulo_encuesta}")
                                    await server.change_page("poll.html")
                                    await asyncio.sleep(0.3)
                                    await server.settittle(titulo_encuesta)
                                    config.encuesta_activa = True  # ACTIVAR ENCUESTA AQUÍ
                                    await send_message_async(youtube, f"{autor} Encuesta preparada: '{titulo_encuesta}'. Envía opciones (una por mensaje). Termina con !etime <segundos> (default 60).")
                                else:
                                    await send_message_async(youtube, f"{autor} Usa !e <titulo> para iniciar.")
                        # No feedback si no es custom

                    # Añadir opciones mientras haya builder y no es comando
                    elif builder and not mensaje.startswith(("!etime", "!et")) and not mensaje.startswith("!e"):
                        opcion = mensaje_raw.strip()
                        if opcion:
                            builder["options"].append(opcion)
                            # Log opcional: print(f"[Encuesta] Agregando opción: {opcion}")
                            await server.addoption(opcion)
                            await asyncio.sleep(0.2)
                            await send_message_async(youtube, f"{autor} Opción agregada: {opcion} (total {len(builder['options'])}).")

                    # Finalizar con !etime o !et (sin redirect, solo inicia la encuesta con el tiempo)
                    elif builder and mensaje.startswith(("!etime", "!et")):
                        partes = mensaje.split()
                        tiempo = 60
                        if len(partes) > 1 and partes[1].isdigit():
                            tiempo = int(partes[1])
                        # Log opcional: print(f"[Encuesta] Finalizando encuesta: '{builder['title']}' opciones={builder['options']} tiempo={tiempo}")
                        if len(builder["options"]) < 2:
                            # Log opcional: print(f"[Encuesta] No hay suficientes opciones: {builder['options']}")
                            await send_message_async(youtube, f"{autor} Necesitas al menos 2 opciones antes de iniciar.")
                        else:
                            try:
                                # Log opcional: print("[Encuesta] Llamando iniciar_encuesta...")
                                await server.polltime(tiempo)
                                # Log opcional: print("[Encuesta] Encuesta iniciada correctamente")
                                await send_message_async(youtube, f"{autor} Encuesta iniciada: '{builder['title']}'. Vota con !v <número> (duración {tiempo}s).")
                            except Exception as e:
                                logging.error(f"Error al iniciar encuesta desde chat: {e}")
                                print(f"[Encuesta] Error al iniciar encuesta: {e}")
                                await send_message_async(youtube, f"{autor} Ocurrió un error al iniciar la encuesta.")
                        poll_builders.pop(canal_id, None)
                    # Comando !emini para usuarios especiales (minimizar encuesta)
                    if mensaje == "!emini":
                        if canal_id in custom_users:
                            if config.encuesta_activa:
                                await server.toggle_mini()
                                await send_message_async(youtube, f"{autor} Encuesta minimizada.")
                            else:
                                await send_message_async(youtube, f"{autor} No hay encuesta activa para minimizar.")

                  # Comando para forzar el fin de la encuesta
                    if mensaje.startswith("!eend"):
                        if canal_id in custom_users:
                            if config.encuesta_activa:
                              await server.showwinner()
                              await send_message_async(youtube, f"{autor} Ha forzado el fin de la encuesta.")
                            else:
                                await send_message_async(youtube, f"{autor} No hay encuesta activa para finalizar.")

                  
                  
                  
                  
                  
                    # --- RULETA ---
                    if mensaje in ["!participar", "!join", "!p"] and ruleta_activa and itstimetojoin:
                        # Buscar el usuario en el cache para obtener avatar_local
                        avatar_local = avatar_url
                        for user in user_cache.get("users", []):
                            if user.get("youtube_id") == canal_id:
                                avatar_local = user.get("avatar_local", avatar_url)
                                break
                        
                        await inscribir_en_ruleta(
                            autor,
                            avatar_local,
                            server,
                            youtube,
                            send_message_async
                        )

                    # --- ENCUESTA ---
                    if mensaje.startswith("!v "):
                        if poll_builders:
                            await send_message_async(youtube, f"{autor}, la encuesta aún se está configurando. Espera a que se inicie para votar.")
                        elif encuesta_activa:
                            try:
                                numero_voto = mensaje.split()[1]
                                if numero_voto.isdigit():
                                    # Obtener avatar_local desde el cache (fallback al avatar_url)
                                    avatar_local = avatar_url
                                    for user in user_cache.get("users", []):
                                        if user.get("youtube_id") == canal_id:
                                            avatar_local = user.get("avatar_local", avatar_url)
                                            break

                                    if autor not in participantes_votantes:
                                        votos[autor] = int(numero_voto)
                                        participantes_votantes.add(autor)
                                        print("ENCUESTA CORRECTA")
                                        await server.addvote(int(numero_voto), autor)
                                        print(f"Se ha votado por: {numero_voto}")
                                        await send_message_async(youtube, f"{autor}, Has votado correctamente por: {numero_voto}.")

                                        # Notificación con avatar local
                                        notification = {
                                            "type": "notification",
                                            "caseType": 2,
                                            "titleText": f"{autor}",
                                            "messageText": f"votó por la opción {numero_voto}",
                                            "profileImage": {"src": avatar_local}
                                        }
                                        try:
                                            await server.send_update(notification)
                                        except Exception as e:
                                            logging.error(f"No se pudo enviar notificación de voto: {e}")
                                    else:
                                        await send_message_async(youtube, f"{autor}, Ya has votado una vez.")
                                else:
                                    await send_message_async(youtube, f"{autor}, El voto debe ser un número válido.")
                            except Exception as e:
                                logging.error(f"Error procesando voto: {e}")
                    # --- SCREENTEXT (!ST) ---
                    if mensaje.startswith("!st "):
                        contenido = mensaje[4:].strip()
                        await add_text_to_screentext(contenido, server)

                    # --- COMANDO !who / !id PARA BUSCAR USUARIOS O CONSULTAR PROPIO ID ---
                    if mensaje.startswith("!who") or mensaje.startswith("!id"):
                        # Extraer parámetro de búsqueda
                        if mensaje.startswith("!who "):
                            busqueda = mensaje[5:].strip()
                        elif mensaje.startswith("!id "):
                            busqueda = mensaje[4:].strip()
                        else:
                            # Si es !who o !id sin parámetros, mostrar ID propio
                            busqueda = None
                        
                        if not busqueda:
                            # Sin parámetro: mostrar ID del usuario actual
                            usuario_actual = None
                            for user in user_cache.get("users", []):
                                if user.get("youtube_id") == canal_id:
                                    usuario_actual = user
                                    break
                            
                            if usuario_actual:
                                user_id = usuario_actual.get("id")
                                await send_message_async(youtube, f"{autor} Tu número de ID es: {user_id}")
                            else:
                                await send_message_async(youtube, f"{autor} No se pudo encontrar tu ID en el sistema.")
                        else:
                            # Con parámetro: buscar usuario por ID o nombre
                            usuario_encontrado = None
                            # Verificar si es un ID (número) o nombre
                            if busqueda.isdigit():
                                # Buscar por ID
                                for user in user_cache.get("users", []):
                                    if str(user.get("id")) == busqueda:
                                        usuario_encontrado = user
                                        break
                                if usuario_encontrado:
                                    await send_message_async(youtube, f"El usuario con ID {busqueda} es: {usuario_encontrado.get('name', 'Usuario desconocido')}")
                                else:
                                    await send_message_async(youtube, f"No se encontró ningún usuario con el ID: {busqueda}")
                            else:
                                # Buscar por nombre (case-insensitive)
                                for user in user_cache.get("users", []):
                                    if user.get("name", "").lower() == busqueda.lower():
                                        usuario_encontrado = user
                                        break
                                if usuario_encontrado:
                                    await send_message_async(youtube, f"El usuario '{busqueda}' tiene el ID: {usuario_encontrado.get('id')}")
                                else:
                                    await send_message_async(youtube, f"No se encontró ningún usuario con el nombre: {busqueda}")

                    if comandos_habilitados:
                        try:
                            if mensaje == "!ping":
                                print(f"Comando recibido !ping: {mensaje} de {autor}")
                                await send_message_async(youtube, "Pong!")
                            elif mensaje == "!tienda":
                                await send_message_async(youtube, f"{autor} Visita la tienda aquí: https://streamlabs.com/powerst")
                            elif mensaje in ["!discord", "!d"]:
                                await send_message_async(youtube, f"{autor} Únete a nuestro Discord: https://discord.gg/NWgsynTAXQ")
                            elif mensaje in ["!roblox", "rb"]:
                                await send_message_async(youtube, f"{autor} Mi usuario de Roblox: @ElPowerST | https://www.roblox.com/es/users/2745412910/profile")
                            elif mensaje in ["hola", "ola", "oli", "holas", "hola power", "olaa", "olaaa"]:
                                await send_message_async(youtube, f"Holaa {autor} Bienvenido al stream!")
                        except Exception as e:
                            logging.error(f"Error ejecutando comando: {e}")

                # Actualizar el token para la próxima página de mensajes
                next_page_token = response.get("nextPageToken")
                
                # Desactivar flag cuando ya no hay más mensajes antiguos (cuando no hay nextPageToken)
                if config.skip_old_messages and not next_page_token:
                    from usermanager import save_user_cache, load_user_cache
                    user_cache = load_user_cache()
                    save_user_cache(user_cache)
                    config.skip_old_messages = False
                    print("✓ Mensajes antiguos cargados. Caché guardado. Ahora procesando mensajes nuevos...")


                
                intentos = 0  # Reiniciar el contador si la ejecución fue exitosa
                await asyncio.sleep(waittime)  # Evita hacer demasiadas peticiones seguidas

            except HttpError as e:
                logging.error(f"Error en la API de YouTube: {e}")
                print("Error en la API de YouTube. Reintentando en 10 segundos...")
                await asyncio.sleep(10)

            except Exception as e:
                intentos += 1
                logging.error(f"Error inesperado: {e} (Intento {intentos}/{max_reintentos})")
                print(f"Error inesperado{e}. Revisar logs.")

                if intentos >= max_reintentos:
                    print("Demasiados errores seguidos. Ignorando el error y continuando.")
                    intentos = 0  # Resetea el contador para que no se bloquee

                await asyncio.sleep(10)  # Espera antes de continuar

        else:
            await asyncio.sleep(5)  # Si no está activo, espera antes de reintentar

