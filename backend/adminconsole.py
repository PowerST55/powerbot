from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
import asyncio
import logging
import sys
import os
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from backend import config
from usermanager import ban_user_by_name, unban_user_by_name, show_ban_list, add_custom_user_by_name, delete_custom_user_by_name, show_custom_list
from youtube_api import toggle_youtube_api, send_message_async
from activities.poll import resetpoll

# Import discord bot functions from local discordbot folder
# Using dynamic import to avoid circular dependencies and timing issues
# The discordbot module will be imported at runtime when needed

def console_input(server):
    # ...existing code...
    session = PromptSession()
    cmlist ="""📌 Comandos disponibles:
/say, /cmds, /yapi, /ssyapi, /uc, /index
/ruleta, /r, /rgirar, /rg, /rend, /rup, /rlist, /ropen, /rclose, /ragregar, /ragg, /rkw
/poll, /e, /encuesta, /etittle, /eadd, /evote, /eend
/texthub, /th, /texhubend, /thadd, /thtest
/ban, /unban, /banlist
/custom add, /custom delete, /custom list
/fakenotif <tipo> <titulo> <mensaje> [url_avatar]
/nttest <notification_id>
/fcode
    /discord, /dc (toggle bot de Discord)
    /dcstore (activar/desactivar tienda)
    /dcpoints (activar/desactivar sistema de puntos de Discord)
    /ytpoints (activar/desactivar sistema de puntos de YouTube)
    /reload (reiniciar toda la aplicación)"""

    with patch_stdout():
        while True:
            try:
                comando = session.prompt("Admin > ")
                
                # Mensajes en el chat
                if comando.startswith("/say"):
                    contenido = comando[5:].strip()
                    if contenido:
                        if config.isyappi:
                            asyncio.run(send_message_async(config.youtube, contenido))
                            print("Mensaje enviado correctamente con /say")
                        else:
                            print("La API de YouTube está desactivada, usa /yapi")
                    else:
                        print("Comando /say vacío o no válido.")
                
                elif comando == "/cmds":
                    config.comandos_habilitados = not config.comandos_habilitados
                    print(f"Comandos del chat {'activados' if config.comandos_habilitados else 'desactivados'}.")
                
                # Comando Discord (toggle)
                elif comando in ["/discord", "/dc"]:
                    try:
                        from discordbot.dcbot import start_discord_bot, stop_discord_bot, discord_bot_instance
                        import discordbot.dcbot as dcbot_module
                        
                        if dcbot_module.discord_bot_instance is None:
                            # Iniciar el bot
                            start_discord_bot(server)
                            print("✓ Bot de Discord iniciado en background.")
                        else:
                            # Detener el bot
                            stop_discord_bot()
                            print("✓ Bot de Discord detenido.")
                    except Exception as e:
                        print(f"Error al toggle bot de Discord: {e}")

                # Toggle de tienda
                elif comando == "/dcstore":
                    try:
                        from backend import config as _config
                        _config.store_enabled = not getattr(_config, 'store_enabled', True)
                        estado = 'activada' if _config.store_enabled else 'desactivada'
                        print(f"Tienda {estado}. {'Las compras están habilitadas.' if _config.store_enabled else 'Las compras están bloqueadas.'}")
                    except Exception as e:
                        print(f"Error al alternar la tienda: {e}")
                
                # Toggle del sistema de puntos de Discord
                elif comando == "/dcpoints":
                    try:
                        from discordbot.dcbot import discord_bot_instance
                        if discord_bot_instance and hasattr(discord_bot_instance, 'economy_manager'):
                            estado_actual = discord_bot_instance.economy_manager.toggle_points()
                            print(f"Sistema de puntos Discord (Pews) {'activado ✓' if estado_actual else 'desactivado ✗'}.")
                        else:
                            print("⚠ El bot de Discord no está en ejecución.")
                    except Exception as e:
                        print(f"Error al alternar el sistema de puntos de Discord: {e}")
                
                # Toggle del sistema de puntos de YouTube
                elif comando == "/ytpoints":
                    try:
                        from backend.youtube_cmds_listener import youtube_economy_manager
                        estado_actual = youtube_economy_manager.toggle_points()
                        print(f"Sistema de puntos YouTube (Pews) {'activado ✓' if estado_actual else 'desactivado ✗'}.")
                    except Exception as e:
                        print(f"Error al alternar el sistema de puntos de YouTube: {e}")

                # Comando para falsear una notificación
                elif comando.startswith("/fakenotif"):
                    partes = comando.split(maxsplit=3)
                    # Uso: /fakenotif <tipo> <titulo> <mensaje> [url_avatar]
                    if len(partes) >= 4:
                        tipo = int(partes[1]) if partes[1].isdigit() else 1
                        titulo = partes[2]
                        mensaje = partes[3]
                        url_avatar = None
                        if tipo == 2:
                            url_avatar = session.prompt("URL del avatar (opcional, Enter para omitir): ").strip()
                        notif = {
                            "type": "notification",
                            "caseType": tipo,
                            "titleText": titulo,
                            "messageText": mensaje
                        }
                        if tipo == 2 and url_avatar:
                            notif["profileImage"] = {"src": url_avatar}
                        awaitable = server.send_update(notif)
                        try:
                            asyncio.run(awaitable)
                        except RuntimeError:
                            # Si ya existe un loop, usar create_task
                            asyncio.get_event_loop().create_task(awaitable)
                        print(f"Notificación falsa enviada: {notif}")
                    else:
                        print("Uso: /fakenotif <tipo> <titulo> <mensaje> [url_avatar]")
                
                # Comando para probar notificaciones del catálogo dinámico
                elif comando.startswith("/nttest"):
                    partes = comando.split(maxsplit=1)
                    if len(partes) == 2:
                        notif_id = partes[1].strip()
                        notif = {
                            "type": "notification",
                            "notificationId": notif_id
                        }
                        awaitable = server.send_update(notif)
                        try:
                            asyncio.run(awaitable)
                        except RuntimeError:
                            asyncio.get_event_loop().create_task(awaitable)
                        print(f"✓ Notificación de prueba enviada: {notif_id}")
                    else:
                        print("Uso: /nttest <notification_id>")
                        print("Ejemplo: /nttest hijodelamaraca")
                
                # Comando para forzar código recompensable
                elif comando == "/fcode":
                    try:
                        from backend.code_manager import CodeManager
                        from backend import config as _config
                        
                        code_manager = CodeManager(
                            data_dir=os.path.join(os.path.dirname(__file__), '..', 'data')
                        )
                        
                        # Generar código forzado
                        code_data = code_manager.generate_code()
                        if code_data:
                            # Enviar por WebSocket
                            notif = {
                                'type': 'show_code',
                                'code': code_data['code'],
                                'duration': code_data['duration'],
                                'blink_start': _config.CODE_BLINK_START
                            }
                            awaitable = server.send_update(notif)
                            try:
                                asyncio.run(awaitable)
                            except RuntimeError:
                                asyncio.get_event_loop().create_task(awaitable)
                            print(f"🎁 Código forzado generado: {code_data['code']} (Válido por {code_data['duration']}s)")
                        else:
                            print("⚠ No se pudo generar el código (ya hay uno activo)")
                    except Exception as e:
                        logging.error(f"Error en /fcode: {e}")
                        print(f"Error al generar código: {e}")
                
                # Control de ruleta
                elif comando in ["/ruleta","/r"]:
                    config.participantes_ruleta.clear()
                    asyncio.run(server.change_page("ruleta.html"))
                    config.ruleta_activa = True
                    config.itstimetojoin = True
                    if config.isyappi:
                        asyncio.run(send_message_async(config.youtube, "Una Ruleta acaba de iniciar escribe !participar para unirte"))
                    print("Ruleta iniciada. Esperando participantes...")
                elif comando.startswith(("/ragregar", "/ragg")):
                    if config.ruleta_activa:
                        partes = comando.split(maxsplit=1)
                        if len(partes) == 2 and isinstance(partes[1], str) and partes[1]:
                            item_name = partes[1]
                            avatar = session.prompt("Elije Un url para la imagen: ")
                            asyncio.run(server.add_item(item_name,avatar))
                            config.participantes_ruleta.add(item_name)
                            print(f"\nItem '{item_name}' agregado a la ruleta.")
                        else:
                            print("\nFormato incorrecto. Uso: /ragregar <item_name>")
                elif comando == "/rtest":
                    pass
                    # asyncio.run(add_users_to_roulette())

                elif comando == "/rgirar" or comando == "/rg":
                    if config.ruleta_activa:
                        try:
                            asyncio.run(server.spin_wheel())
                            if config.isyappi:
                                asyncio.run(send_message_async(config.youtube, "La ruleta está girando..."))
                            print("La ruleta ha comenzado a girar.")
                        except Exception as e:
                            logging.error(f"Error al girar la ruleta: {e}")
                            print(f"Error al girar la ruleta: {e}")
                    else:
                        print("No hay ruleta activa.")
                
                elif comando == "/rend":
                    if config.ruleta_activa:
                        config.ruleta_activa = False
                        config.itstimetojoin = False
                        config.participantes_ruleta.clear()
                        asyncio.run(server.reset_wheel())
                        asyncio.run(server.change_page("index.html"))
                        if config.isyappi:
                            asyncio.run(send_message_async(config.youtube, "La ruleta ha sido reseteada por completo."))
                        print("Ruleta terminada y reiniciada completamente.")
                    else:
                        print("No hay ninguna ruleta activa.")
                
                elif comando == "/rkw":
                    config.keepwinner = not config.keepwinner
                    asyncio.run(server.keepwinner(config.keepwinner))
                    print(f"keepWinner {'activado' if config.keepwinner else 'desactivado'}.")
                
                elif comando == "/rup":
                    asyncio.run(server.updaterul())
                    print("Se ha actualizado la ruleta.")
                # RULETA OPEN/CLOSE
                elif comando == "/ropen":
                    config.itstimetojoin = True
                    print("Se ha abierto la ruleta para unirse.")
                elif comando == "/rclose":
                    config.itstimetojoin = False
                    print("Se ha cerrado la ruleta para unirse.")

                #------------------------------------------ Secuencia encuesta ⇓⇓⇓⇓⇓ ------------------------------------------
                elif comando in ["/poll", "/e", "/encuesta"]:
                    if not config.encuesta_activa:
                        # Cambiar página una sola vez
                        asyncio.run(server.change_page("poll.html"))
                        import time
                        time.sleep(0.3)
                        
                        # Obtener título
                        titulo = session.prompt("Elije el nombre de la encuesta: ")
                        asyncio.run(server.settittle(titulo))
                        time.sleep(0.2)
                        
                        # Agregar opciones
                        opciones = []
                        while True:
                            opcion = session.prompt("Escribe la opción que deseas añadir o escribe /c para continuar: ")
                            if opcion == "/c":
                                break
                            if opcion:
                                opciones.append(opcion)
                                asyncio.run(server.addoption(opcion))
                                time.sleep(0.2)
                                print(f"Opción añadida: {opcion}")
                            else:
                                print("Por favor, escribe una opción válida.")
                        
                        # Validar que hay suficientes opciones
                        if len(opciones) < 2:
                            print("Error: Necesitas al menos 2 opciones.")
                            continue
                        
                        # Obtener tiempo
                        tiempo_str = session.prompt("Escribe cuántos segundos durará la encuesta (presiona Enter para 60s por defecto): ")
                        if not tiempo_str:
                            tiempo_str = "60"
                        
                        if tiempo_str.isdigit():
                            tiempo = int(tiempo_str)
                            print(f"Tiempo de la encuesta establecido: {tiempo} segundos.")
                        else:
                            print("Error: El tiempo debe ser un número válido.")
                            continue
                        
                        # Iniciar la encuesta sin reload
                        try:
                            config.encuesta_activa = True
                            asyncio.run(server.polltime(tiempo))
                            if config.isyappi:
                                asyncio.run(send_message_async(config.youtube, f"Acaba de iniciar una Encuesta: '{titulo}'. Usa !v <opción> para votar."))
                            print("La encuesta ha comenzado.")
                        except Exception as e:
                            logging.error(f"Error al iniciar la encuesta: {e}")
                            print(f"Error al iniciar la encuesta: {e}")
                            config.encuesta_activa = False
                    else:
                        print("Error: Ya hay una encuesta activa.")
                elif comando == "/emini" :
                    if config.encuesta_activa:
                     asyncio.run(server.toggle_mini())
                    else:
                        print("Error: Primero inicia una encuesta con /encuesta.")
                elif comando == "/rmini" :
                     if config.ruleta_activa:
                                asyncio.run(server.toggle_mini())
                     else:
                        print("Error: Primero inicia una ruleta con /ruleta.")

                #------------------------------------------ Secuencia encuesta ⇑⇑⇑⇑⇑ ------------------------------------------
                # Comandos de respaldo ⇓⇓⇓⇓⇓⇓⇓⇓-----------------------------------------------------------
                elif comando == "/pgpoll":
                    asyncio.run(server.change_page("poll.html"))


                elif comando.startswith("/etittle"):
                    if config.encuesta_activa:
                        contenido = comando[9:].strip()
                        asyncio.run(server.settittle(contenido))
                        print(f"Título de la encuesta establecido: {contenido}")
                    else:
                        print("Error: Primero inicia una encuesta con /encuesta.")
                
                elif comando.startswith("/eadd"):
                    if config.encuesta_activa:
                        contenido = comando[6:].strip()
                        asyncio.run(server.addoption(contenido))
                        print(f"Opción añadida: {contenido}")
                    else:
                        print("Error: Primero inicia una encuesta con /encuesta.")
                
                elif comando.startswith("/evote"):
                    contenido = comando[7:].strip()
                    if config.encuesta_activa and contenido.isdigit():
                        config.votos["Console"] = contenido
                        asyncio.run(server.addvote(int(contenido), "Admin"))
                        print(f"Voto registrado: {contenido}")
                    else:
                        print("Error: No hay encuesta activa o voto inválido.")
                
                elif comando.startswith("/eend"):
                    if config.encuesta_activa:
                        resetpoll(config)
                        asyncio.run(server.showwinner())
                    else:
                        print("Error: No hay encuesta activa.")
                #--------------------------------- Encuesta comandos de respaldo ⇑⇑⇑⇑⇑⇑⇑ ---------------------------------
                elif comando.startswith("/wtime"):
                    contenido = comando[7:].strip()
                    if contenido.isdigit():
                        config.waittime = int(contenido)
                        print(f"waittime is set: {config.waittime}")
                # Configuración de API de YouTube
                elif comando == "/yapi":
                    toggle_youtube_api(config)
                
                elif comando == "/ssyapi":
                    print(f"El estado de isyapi es: {config.isyappi}")
                
                elif comando == "/uc":
                    pass
                
                # Otras opciones
                elif comando == "/index":
                    asyncio.run(server.change_page("index.html"))
                    print("Redirigiendo a Index...")
                
                elif comando == "/screentext" or comando == "/st":
                    asyncio.run(server.change_page("screentext.html"))
                    print("Redirigiendo a texhub y activando...")
                    if config.isyappi:
                        asyncio.run(send_message_async(config.youtube, "Texto en Stream activado. Usa !st <mensaje>"))
                
                elif comando.startswith("/thadd"):
                    contenido = comando[7:].strip()
                    asyncio.run(server.addtexthub(contenido))
                    print(f"Enviando a TexHub: {contenido}")


                elif comando.startswith("/ban") and comando != "/banlist":
                    user = comando[4:].strip()
                    if user:
                        ban_user_by_name(user)
                    else:
                        print("Por favor, especifica un usuario para banear.")
                elif comando.startswith("/unban"):
                    user = comando[7:].strip()
                    if user:
                        unban_user_by_name(user)
                    else:
                        print("Por favor, especifica un usuario para desbanear.")    
                elif comando.startswith("/banlist"):
                    show_ban_list()
                elif comando.startswith("/custom"):
                    partes = comando.split(maxsplit=2)
                    if len(partes) >= 2:
                        subcomando = partes[1].lower()
                        if subcomando == "add" and len(partes) == 3:
                            user = partes[2].strip()
                            if user:
                                add_custom_user_by_name(user)
                            else:
                                print("Por favor, especifica un usuario para agregar a custom.")
                        elif subcomando == "delete" and len(partes) == 3:
                            user = partes[2].strip()
                            if user:
                                delete_custom_user_by_name(user)
                            else:
                                print("Por favor, especifica un usuario para eliminar de custom.")
                        elif subcomando == "list":
                            show_custom_list()
                        else:
                            print("Uso: /custom add <nombre> | /custom delete <nombre> | /custom list")
                    else:
                        print("Uso: /custom add <nombre> | /custom delete <nombre> | /custom list")
                elif comando.startswith("/who "):
                    busqueda = comando[5:].strip()
                    if busqueda:
                        # Cargar el user_cache
                        try:
                            from usermanager import load_user_cache
                            user_cache = load_user_cache()
                            
                            usuario_encontrado = None
                            # Verificar si es un ID (número) o nombre
                            if busqueda.isdigit():
                                # Buscar por ID
                                for user in user_cache.get("users", []):
                                    if str(user.get("id")) == busqueda:
                                        usuario_encontrado = user
                                        break
                            else:
                                # Buscar por nombre (case-insensitive)
                                for user in user_cache.get("users", []):
                                    if user.get("name", "").lower() == busqueda.lower():
                                        usuario_encontrado = user
                                        break
                            
                            if usuario_encontrado:
                                print(f"\n📌 Usuario encontrado:")
                                print(f"   ID: {usuario_encontrado.get('id')}")
                                print(f"   Nombre: {usuario_encontrado.get('name')}")
                                print(f"   Es Moderador: {usuario_encontrado.get('isModerator', False)}")
                                print(f"   Es Miembro: {usuario_encontrado.get('isMember', False)}")
                            else:
                                print(f"No se encontró ningún usuario con el ID/nombre: {busqueda}")
                        except Exception as e:
                            logging.error(f"Error al buscar usuario: {e}")
                            print(f"Error al buscar usuario: {e}")
                    else:
                        print("Uso: /who <ID|nombre>")
                
                elif comando == "/reload":
                    print("🔄 Reiniciando aplicación...")
                    print("⚠ Cerrando todos los procesos...")
                    
                    # Cerrar el bot de Discord si está activo
                    try:
                        from discordbot.dcbot import stop_discord_bot, discord_bot_instance
                        if discord_bot_instance is not None:
                            print("   ✓ Cerrando bot de Discord...")
                            stop_discord_bot()
                            time.sleep(1)  # Esperar a que cierre correctamente
                    except Exception as e:
                        logging.error(f"Error al cerrar Discord bot: {e}")
                    
                    print("   ✓ Reiniciando proceso de Python...")
                    
                    # Reiniciar el proceso completo
                    import sys
                    os.execv(sys.executable, ['python'] + sys.argv)
                
                elif comando == "/help":
                    print(cmlist)
                else:
                    print("\nComando no reconocido. Usa /help para ver los comandos disponibles.")
            
            except Exception as e:
                logging.error(f"Error en el procesamiento del comando: {e}")
                print(f"Error al procesar el comando: {e}")
