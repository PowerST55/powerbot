import os
import logging
import ssl
import json
import certifi
import asyncio
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CHAT_ID_FILE = "chat_id.json"

# Ajuste de rutas para la carpeta 'keys' en la raíz del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS_DIR = os.path.join(BASE_DIR, "keys")
CREDENTIALS_PATH = os.path.join(KEYS_DIR, "credentials.json")
TOKEN_PATH = os.path.join(KEYS_DIR, "ytkey.json")

logging.basicConfig(level=logging.ERROR, filename='bot_log.txt', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

def authenticate_youtube_api():
    creds = None
    try:
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
    except Exception as e:
        logging.error(f"Error durante la autenticación: {e}")
    return creds

# Guardar el chat ID en un archivo JSON
def save_chat_id(live_chat_id):
    with open(CHAT_ID_FILE, "w") as f:
        json.dump({"live_chat_id": live_chat_id}, f)

# Cargar el chat ID desde el archivo JSON
def load_chat_id():
    if os.path.exists(CHAT_ID_FILE):
        with open(CHAT_ID_FILE, "r") as f:
            data = json.load(f)
            return data.get("live_chat_id")
    return None

# Obtener el chat ID y sobrescribirlo en el archivo JSON
def get_live_chat_id(youtube):
    try:
        request = youtube.liveBroadcasts().list(part="snippet", broadcastStatus="active")
        response = request.execute()
        if response.get("items") and response["items"][0].get("snippet"):
            live_chat_id = response["items"][0]["snippet"].get("liveChatId")
            save_chat_id(live_chat_id)
            print(live_chat_id)
            return live_chat_id
        else:
            print("No se encontró ninguna transmisión activa.")
            logging.warning("No se encontró ninguna transmisión activa.")
            return None
    except HttpError as e:
        logging.error(f"Error al obtener el ID del chat en vivo: {e}")
    except ssl.SSLError as e:
        logging.error(f"Error SSL: {e}")
    except Exception as e:
        logging.error(f"Error inesperado: {e}")
    return None

# Enviar mensaje al chat en vivo, obteniendo el chat ID desde el archivo
def send_message(youtube, mensaje):
    live_chat_id = load_chat_id()
    if not live_chat_id:
        print("No se puede enviar el mensaje porque no hay transmisión activa.")
        return
    
    try:
       # print(youtube)
        youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {
                        "messageText": mensaje
                    }
                }
            }
        ).execute()
        print("Mensaje enviado correctamente.")
    except HttpError as e:
        logging.error(f"Error al enviar un mensaje: {e}")
    except ssl.SSLError as e:
        logging.error(f"Error SSL ignorado: {e}")
    except Exception as e:
        logging.error(f"Error inesperado ignorado: {e}")

async def send_message_async(youtube, mensaje):
    live_chat_id = load_chat_id()
    if not live_chat_id:
        print("No se puede enviar el mensaje porque no hay transmisión activa.")
        return

    def _send():
        try:
            youtube.liveChatMessages().insert(
                part="snippet",
                body={
                    "snippet": {
                        "liveChatId": live_chat_id,
                        "type": "textMessageEvent",
                        "textMessageDetails": {
                            "messageText": mensaje
                        }
                    }
                }
            ).execute()
            print("Mensaje enviado correctamente.")
        except HttpError as e:
            logging.error(f"Error al enviar un mensaje: {e}")
        except ssl.SSLError as e:
            logging.error(f"Error SSL ignorado: {e}")
        except Exception as e:
            logging.error(f"Error inesperado ignorado: {e}")

    await asyncio.to_thread(_send)

def toggle_youtube_api(config):
    """
    Activa o desactiva la API de YouTube y actualiza el chat_id automáticamente.
    Modifica config.isyappi, config.youtube y config.live_chat_id.
    """
    config.isyappi = not config.isyappi

    if config.isyappi:
        try:
            print("Intentando activar la API de YouTube...")
            config.youtube = build("youtube", "v3", credentials=authenticate_youtube_api())
            config.live_chat_id = get_live_chat_id(config.youtube)  # Obtiene el chat ID actualizado

            if not config.live_chat_id:
                print("No hay chat ID guardado. Asegúrate de estar en vivo y actualiza el archivo JSON.")
                config.isyappi = False
            else:
                print("API de YouTube activada con éxito.")
                config.skip_old_messages = True  # Activar flag para ignorar mensajes antiguos
        except Exception as e:
            logging.error(f"Error al activar la API de YouTube: {e}")
            print("Error al activar la API de YouTube. Desactivándola...")
            config.isyappi = False
    else:
        print("Desactivando API de YouTube...")
