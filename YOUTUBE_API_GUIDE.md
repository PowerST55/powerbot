# YouTube API Core - Documentación

## Descripción General

El módulo `youtube_core.py` proporciona una interfaz limpia y robusta para interactuar con la YouTube API. Está diseñado siguiendo principios SOLID con una arquitectura modular y separación clara de responsabilidades.

## Estructura

### Clases Principales

#### `YouTubeConfig`
Gestiona la configuración y validación de rutas de credenciales.

**Características:**
- Búsqueda automática de credenciales en `backend/keys`
- Validación de archivos requeridos
- Personalizable con rutas personalizadas

```python
config = YouTubeConfig()  # Usa backend/keys por defecto
config = YouTubeConfig(keys_dir="/custom/path")  # Custom path
```

#### `YouTubeAuthenticator`
Maneja la autenticación OAuth con YouTube.

**Características:**
- Autenticación con flujo OAuth
- Renovación automática de tokens
- Persistencia de credenciales
- Manejo robusto de errores

```python
authenticator = YouTubeAuthenticator(config)
credentials = authenticator.authenticate()
```

#### `YouTubeClient`
Interfaz para interactuar con la YouTube API.

**Métodos:**
- `get_active_live_chat_id()`: Obtiene el ID de chat del stream activo
- `send_message(live_chat_id, message)`: Envía un mensaje al chat

```python
client = YouTubeClient(credentials)
live_chat_id = client.get_active_live_chat_id()
client.send_message(live_chat_id, "Mensaje")
```

#### `YouTubeAPI`
Punto de entrada principal que orquesta todo.

**Métodos:**
- `connect()`: Establece conexión
- `disconnect()`: Cierra conexión
- `is_connected()`: Verificación de estado
- Soporta context manager (`with` statement)

## Formas de Uso

### 1. Context Manager (Recomendado)
```python
from backend.services.youtube_api import YouTubeAPI

with YouTubeAPI() as youtube:
    if youtube.is_connected():
        live_chat_id = youtube.client.get_active_live_chat_id()
        youtube.client.send_message(live_chat_id, "¡Hola!")
```

### 2. Singleton Pattern (Acceso Global)
```python
from backend.services.youtube_api import initialize_youtube_api, get_youtube_api

# Inicializar una vez
api = initialize_youtube_api()

# Obtener en otro lugar del código
youtube = get_youtube_api()
```

### 3. Manejo Manual
```python
from backend.services.youtube_api import YouTubeAPI

youtube = YouTubeAPI()
if youtube.connect():
    # Tu código aquí
    live_chat_id = youtube.client.get_active_live_chat_id()
    youtube.disconnect()
```

## Requisitos de Archivos

En la carpeta `backend/keys/`:

1. **credentials.json** - Descargado desde Google Cloud Console
   - Contiene las credenciales OAuth de tu aplicación
   - [Obtener credenciales](https://cloud.google.com/docs/authentication/oauth2/service-account)

2. **ytkey.json** - Generado automáticamente
   - Se crea después de la primera autenticación exitosa
   - Contiene el token de acceso para futuras conexiones

## Logging

El módulo registra todos los eventos importantes:

```python
import logging

# Ver logs de YouTube API
logger = logging.getLogger('backend.services.youtube_api.youtube_core')
logger.setLevel(logging.DEBUG)
```

### Niveles de Log

- **INFO**: Operaciones exitosas
- **WARNING**: Situaciones anormales (sin errores)
- **ERROR**: Errores que requieren atención

## Manejo de Errores

Todos los métodos devuelven valores seguros en caso de error:

- `authenticate()` → `None` si falla
- `send_message()` → `False` si falla
- `get_active_live_chat_id()` → `None` si falla
- `connect()` → `False` si falla

## Ejemplo Completo

```python
import logging
from backend.services.youtube_api import YouTubeAPI, initialize_youtube_api

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Opción 1: Context Manager
def send_message_context():
    try:
        with YouTubeAPI() as youtube:
            if not youtube.is_connected():
                print("No pudieron conectarse")
                return

            live_chat_id = youtube.client.get_active_live_chat_id()
            if live_chat_id:
                success = youtube.client.send_message(
                    live_chat_id,
                    "¡Mensaje desde PowerBot!"
                )
                print("✓ Enviado" if success else "✗ Error al enviar")
    except ValueError as e:
        print(f"Error de configuración: {e}")

# Opción 2: Singleton para acceso global
def initialize_bot():
    api = initialize_youtube_api()
    if api.is_connected():
        print("✓ YouTube API conectada")

def send_from_anywhere():
    from backend.services.youtube_api import get_youtube_api
    
    youtube = get_youtube_api()
    if youtube and youtube.client:
        youtube.client.send_message(chat_id, "Mensaje")
```

## Ventajas del Diseño

✓ **Modular**: Cada componente tiene una responsabilidad clara
✓ **Reutilizable**: Fácil de importar y usar en cualquier parte del proyecto
✓ **Testeable**: Cada clase puede probarse independientemente
✓ **Logging**: Seguimiento completo de operaciones
✓ **Manejo de Errores**: Gestión robusta de excepciones
✓ **Flexible**: Soporta múltiples patrones de uso
✓ **Seguro**: Validación de credenciales y rutas

## Troubleshooting

### Error: "Credentials file not found"
- Verifica que `credentials.json` exista en `backend/keys/`
- Descárgalo nuevamente de Google Cloud Console

### Error: "No active broadcast found"
- Asegúrate de tener un stream activo en YouTube
- Verifica que las credenciales tengan permisos suficientes

### Error: "Invalid scope"
- Las credenciales deben autorizar el scope `youtube.force-ssl`
- Regenera las credenciales con el scope correcto en Google Cloud Console
