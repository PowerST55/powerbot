# YouTube Listener - Documentación

## 📋 Descripción

El módulo **YouTube Listener** escucha mensajes del chat en vivo de YouTube en tiempo real y proporciona una base sólida para procesarlos.

## 🏗️ Arquitectura

### Componentes principales

1. **YouTubeListener** - Clase principal que maneja el polling
2. **YouTubeMessage** - Representa un mensaje del chat
3. **Message Handlers** - Sistema de callbacks para procesar mensajes

### Flujo de ejecución

```
┌─────────────────┐
│  YouTubeClient  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ YouTubeListener │◄─── add_message_handler()
└────────┬────────┘
         │
         │ (polling cada ~2s)
         │
         ▼
┌─────────────────┐
│  Fetch Messages │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Filter Already  │
│   Processed     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Call Handlers   │
│ for each new    │
│    message      │
└─────────────────┘
```

## 🎯 Características

### ✅ Implementadas

- **Polling asíncrono** - No bloquea el event loop
- **Filtrado de duplicados** - Solo procesa mensajes nuevos
- **Sistema de handlers** - Fácil agregar procesadores personalizados
- **Rate limiting** - Respeta el `pollingIntervalMillis` de YouTube
- **Metadatos de usuario** - Detecta moderadores, owner, sponsors
- **Manejo de errores** - Recuperación automática de errores temporales
- **Estadísticas** - Tracking de mensajes procesados

### 🚀 Preparado para

- **Sistema de comandos** - Base para `!comando` en el chat
- **Filtros avanzados** - Por usuario, privilegios, patrones
- **Respuestas automáticas** - Enviar mensajes como respuesta
- **Logging persistente** - Guardar historial de mensajes
- **Analytics** - Estadísticas de participación del chat

## 📚 Uso

### Desde comandos de consola

```bash
PowerBot> yt autorun          # Activar autorun
PowerBot> yt listener         # Iniciar listener
PowerBot> yt status           # Ver estado
PowerBot> yt stop_listener    # Detener listener
```

### Programáticamente

```python
from backend.services.youtube_api import (
    YouTubeAPI,
    YouTubeListener,
    console_message_handler,
)

# Conectar
youtube = YouTubeAPI()
youtube.connect()

# Obtener chat ID
live_chat_id = youtube.client.get_active_live_chat_id()

# Crear listener
listener = YouTubeListener(youtube.client, live_chat_id)

# Agregar handlers
listener.add_message_handler(console_message_handler)

# Iniciar
await listener.start()

# Detener cuando termines
await listener.stop()
```

## 🔧 Crear Handlers Personalizados

### Handler sincrónico

```python
def my_handler(message: YouTubeMessage) -> None:
    """Handler simple que filtra mensajes."""
    if message.is_moderator:
        print(f"Mod dice: {message.message}")

listener.add_message_handler(my_handler)
```

### Handler asíncrono

```python
async def async_handler(message: YouTubeMessage) -> None:
    """Handler async para operaciones I/O."""
    if message.message.startswith("!comando"):
        await procesar_comando(message)

listener.add_message_handler(async_handler)
```

### Handler con filtros

```python
def owner_only_handler(message: YouTubeMessage) -> None:
    """Solo procesa mensajes del owner."""
    if not message.is_owner:
        return
    
    # Procesar comando especial
    if message.message == "!shutdown":
        shutdown_bot()

listener.add_message_handler(owner_only_handler)
```

## 🎨 YouTubeMessage - Propiedades

```python
message = YouTubeMessage(data)

# Propiedades básicas
message.id                  # ID único del mensaje
message.message             # Texto del mensaje
message.author_name         # Nombre del autor
message.author_channel_id   # Channel ID del autor
message.published_at        # Timestamp de publicación

# Privilegios
message.is_moderator        # ¿Es moderador?
message.is_owner            # ¿Es el dueño del canal?
message.is_sponsor          # ¿Es sponsor/miembro?
message.is_privileged()     # ¿Tiene algún privilegio?

# Raw data
message.raw_data            # Datos completos de la API
```

## ⚙️ Configuración

### Intervalo de polling

```python
# Por defecto usa el valor de YouTube API (normalmente 2000ms)
listener.poll_interval_ms = 2000  # Manual override

# YouTube API puede ajustarlo dinámicamente
# basado en la actividad del chat
```

### Límite de mensajes en caché

```python
# El listener guarda IDs de mensajes procesados
# para evitar duplicados. Se limpia automáticamente
# cuando supera los 1000 mensajes (mantiene últimos 500)
```

## 📊 Estadísticas

```python
stats = listener.get_stats()

print(stats)
# {
#     "is_running": True,
#     "live_chat_id": "Abc123...",
#     "poll_interval_ms": 2000,
#     "processed_messages_count": 42,
#     "registered_handlers": 2
# }
```

## 🔮 Próximas Mejoras

### Sistema de comandos

```python
# Arquitectura planificada
@youtube_command("!hola")
async def cmd_hola(message: YouTubeMessage):
    """Responde al comando !hola"""
    await youtube.send_reply(message, "¡Hola! 👋")

@youtube_command("!puntos", mod_only=True)
async def cmd_puntos(message: YouTubeMessage, usuario: str):
    """Comando solo para mods"""
    puntos = get_puntos(usuario)
    await youtube.send_reply(message, f"{usuario} tiene {puntos} puntos")
```

### Filtros avanzados

```python
# Filtrar por patrón
listener.add_filter(regex=r"!(\w+)")

# Filtrar por privilegios
listener.add_filter(min_privilege="moderator")

# Filtrar por contenido
listener.add_filter(contains=["spam", "enlace"])
```

### Analytics

```python
# Tracking automático
analytics = listener.get_analytics()
# {
#     "messages_per_minute": 5.2,
#     "unique_users": 15,
#     "top_chatters": ["user1", "user2"],
#     "privileged_messages": 3
# }
```

## 🐛 Troubleshooting

### El listener no recibe mensajes

1. Verifica que haya una transmisión activa
2. Verifica que el chat no esté en modo "solo suscriptores"
3. Revisa los logs para errores de API (403, 401)

### Mensajes duplicados

- El listener filtra automáticamente mensajes ya procesados
- Si ves duplicados, puede ser un bug - reportar

### Alto uso de CPU

- El polling es cada ~2 segundos por defecto
- YouTube API ajusta esto automáticamente
- No debería causar alto CPU en condiciones normales

## 📄 Ejemplo Completo

Ver [example_youtube_listener.py](../example_youtube_listener.py) para un ejemplo completo funcional.

## 🔗 Referencias

- [YouTube Live Streaming API](https://developers.google.com/youtube/v3/live/docs)
- [LiveChatMessages](https://developers.google.com/youtube/v3/live/docs/liveChatMessages)
