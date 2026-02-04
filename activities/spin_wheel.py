import logging
import asyncio
import sys
import os

# Agrega la carpeta Raiz (la que contiene backend y activities) al sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from backend import config

async def inscribir_en_ruleta(autor, avatar_local, server, youtube, send_message_async):
    """
    Inscribe a un usuario en la ruleta si no está ya inscrito.
    Usa el avatar_local que se le pasa como argumento.
    La lista de participantes se toma de config.
    Envía una notificación cuando el usuario se une.
    """
    participantes_ruleta = config.participantes_ruleta
    print("INSCRIBIR:", participantes_ruleta)
    if autor not in participantes_ruleta:
        participantes_ruleta.add(autor)
        try:
            await asyncio.wait_for(server.add_item(autor, avatar_local), timeout=5)
            await send_message_async(youtube, f"{autor}, se ha inscrito en la ruleta.")
            print(f"{autor} inscrito en la ruleta.")
            
            # Enviar notificación de que se unió a la ruleta
            notification = {
                "type": "notification",
                "caseType": 2,
                "titleText": f"{autor}",
                "messageText": "se unió a la ruleta",
                "profileImage": {"src": avatar_local}
            }
            await server.send_update(notification)
            
        except asyncio.TimeoutError:
            logging.error(f"Timeout al agregar {autor} a la ruleta.")
            await send_message_async(youtube, f"{autor}, hubo un problema al inscribirte en la ruleta.")
            return
        except Exception as e:
            logging.error(f"Error al inscribir en la ruleta: {e}")
    else:
        await send_message_async(youtube, f"{autor}, Usted ya está inscrito en esta ruleta.")
        print(f"{autor} ya estaba inscrito en la ruleta.")

def resetear_ruleta():
    """
    Vacía la lista de participantes de la ruleta.
    """
    participantes_ruleta = config.participantes_ruleta
    participantes_ruleta.clear()
    print("Ruleta reseteada.")