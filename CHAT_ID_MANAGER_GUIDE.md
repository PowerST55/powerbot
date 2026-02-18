# Chat ID Manager - Guía Técnica

## 📋 Descripción General

El `ChatIdManager` es un módulo que gestiona automáticamente el ID del chat de YouTube Live, proporcionando:

- **Búsqueda automática** del chat ID activo
- **Persistencia** en archivo JSON
- **Monitoreo continuo** para detectar nuevas transmisiones
- **Notificaciones** cuando cambia el chat ID
- **Recuperación automática** del último chat ID conocido

## 🏗️ Arquitectura

```
backend/services/youtube_api/config/
├── chat_id_finder.py      # Módulo principal
└── __init__.py            # Exportaciones

backend/data/youtube_bot/
└── active_chat.json       # Chat ID persistido
```

## 📁 Estructura del Archivo `active_chat.json`

```json
{
  "live_chat_id": "Cg0KCzB...",
  "last_updated": "2026-02-17T10:30:45.123456",
  "status": "active"
}
```

## 🔧 Uso Básico

### Crear una instancia

```python
from backend.services.youtube_api import ChatIdManager

# Con cliente de YouTube
manager = ChatIdManager(youtube_client, check_interval=60)
```

### Obtener el chat ID

```python
# Cargar desde archivo
chat_id = manager.load_saved_chat_id()

# Buscar en YouTube API
chat_id = manager.fetch_active_chat_id()

# Actualizar (fetch + save)
chat_id = manager.update_chat_id(force_fetch=True)
```

### Iniciar monitoreo automático

```python
# Inicia verificación periódica
await manager.start_monitoring()

# El manager verificará cada 60 segundos (configurable)
# si hay una nueva transmisión o cambios en el chat ID
```

### Detener monitoreo

```python
await manager.stop_monitoring()
```

## 🔔 Callbacks de Cambio

Puedes registrar una función que se ejecuta cuando cambia el chat ID:

```python
def on_chat_change(old_chat_id: Optional[str], new_chat_id: Optional[str]):
    if new_chat_id:
        print(f"Nueva transmisión: {new_chat_id}")
    else:
        print("Transmisión finalizada")

manager.set_on_change_callback(on_chat_change)
```

## 📊 Estado del Manager

```python
status = manager.get_status()

# Retorna:
# {
#     'current_chat_id': 'Cg0KCz...',
#     'is_monitoring': True,
#     'check_interval': 60,
#     'data_file': 'backend/data/youtube_bot/active_chat.json',
#     'has_active_stream': True
# }
```

## 🎯 Integración con Comandos

El ChatIdManager está integrado en los comandos de YouTube:

### `yt listener`
1. Crea el ChatIdManager si no existe
2. Intenta cargar el último chat ID guardado
3. Verifica y actualiza el chat ID con la API
4. Inicia el monitoreo automático (cada 60s)
5. Configura callback para notificar cambios
6. Inicia el listener de mensajes

### `yt stop_listener`
- Detiene el listener de mensajes
- Detiene el monitoreo del chat ID

### `yt status`
- Muestra el estado del ChatIdManager
- Indica si está monitoreando
- Muestra el chat ID actual
- Muestra el intervalo de verificación

## 🔄 Flujo de Monitoreo

```
┌─────────────────────────────────────────┐
│  1. Usuario ejecuta: yt listener       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  2. ChatIdManager se crea/obtiene       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  3. Carga chat ID guardado (si existe)  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  4. Verifica con YouTube API            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  5. Guarda en active_chat.json          │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  6. Inicia monitoreo (cada 60s)         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  7. Listener usa el chat ID             │
└─────────────────────────────────────────┘
               │
               ▼
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
┌───────────┐     ┌──────────────┐
│ Sin cambio│     │ Nuevo chat ID│
└───────────┘     └──────┬───────┘
                         │
                         ▼
              ┌────────────────────┐
              │ Callback notifica  │
              │ "Reinicia listener"│
              └────────────────────┘
```

## ⚡ Ventajas del Sistema

### 1. **Persistencia**
- El chat ID se guarda automáticamente
- Al reiniciar la app, se recupera el último chat ID
- Útil si la conexión se cae temporalmente

### 2. **Detección automática de nuevas transmisiones**
- Cada 60 segundos verifica si hay nueva transmisión
- Notifica automáticamente al usuario
- Evita errores por chat ID obsoleto

### 3. **Separación de responsabilidades**
- YouTubeCore: Autenticación y API
- ChatIdManager: Gestión del chat ID
- YouTubeListener: Procesar mensajes
- Commands: Orquestación

### 4. **Configurabilidad**
- Intervalo de verificación ajustable
- Directorio de datos configurable
- Callbacks personalizables

## 🐛 Troubleshooting

### El chat ID no se guarda
Verificar permisos de escritura en `backend/data/youtube_bot/`

### El monitoreo no detecta cambios
- Verificar que `check_interval` no sea demasiado largo
- Confirmar que YouTube API está conectada
- Revisar logs para errores de API

### Callback no se ejecuta
- Verificar que el callback fue registrado con `set_on_change_callback`
- Confirmar que el monitoreo está activo
- Revisar que la función callback no lanza excepciones

## 📚 API Reference

### `ChatIdManager.__init__(youtube_client, data_dir=None, check_interval=60)`
Crea una instancia del gestor.

**Parámetros:**
- `youtube_client`: Cliente de YouTube API
- `data_dir`: Directorio donde guardar datos (default: backend/data/youtube_bot)
- `check_interval`: Segundos entre verificaciones (default: 60)

### `get_current_chat_id() -> Optional[str]`
Retorna el chat ID actual en memoria.

### `load_saved_chat_id() -> Optional[str]`
Carga el chat ID desde el archivo JSON.

### `save_chat_id(chat_id: Optional[str]) -> None`
Guarda el chat ID en el archivo JSON.

### `fetch_active_chat_id() -> Optional[str]`
Busca el chat ID activo directamente desde YouTube API.

### `update_chat_id(force_fetch: bool = False) -> Optional[str]`
Actualiza el chat ID (fetch + save + notificar).

**Parámetros:**
- `force_fetch`: Si True, busca aunque ya tengamos un chat ID

### `set_on_change_callback(callback: Callable) -> None`
Establece callback que se ejecuta cuando cambia el chat ID.

**Firma del callback:**
```python
def callback(old_chat_id: Optional[str], new_chat_id: Optional[str]) -> None:
    pass
```

### `async start_monitoring() -> None`
Inicia el monitoreo automático del chat ID.

### `async stop_monitoring() -> None`
Detiene el monitoreo automático.

### `get_status() -> dict`
Retorna el estado actual del manager.

## 🎓 Ejemplos Avanzados

### Monitoreo con logging personalizado

```python
def log_chat_changes(old_id, new_id):
    timestamp = datetime.now().isoformat()
    with open('chat_changes.log', 'a') as f:
        f.write(f"{timestamp}: {old_id} -> {new_id}\n")

manager.set_on_change_callback(log_chat_changes)
await manager.start_monitoring()
```

### Integración con sistema de notificaciones

```python
async def notify_discord(old_id, new_id):
    if new_id:
        await discord_webhook.send(f"Nueva transmisión: {new_id}")

manager.set_on_change_callback(notify_discord)
```

### Monitoreo manual

```python
# Sin usar start_monitoring(), verificar manualmente
while True:
    new_chat_id = manager.update_chat_id(force_fetch=True)
    if new_chat_id != last_chat_id:
        print(f"Chat cambió a: {new_chat_id}")
        last_chat_id = new_chat_id
    
    await asyncio.sleep(30)  # Verificar cada 30s
```

## 📝 Notas

- El archivo `active_chat.json` se crea automáticamente si no existe
- El directorio `backend/data/youtube_bot/` se crea automáticamente
- Los errores de API no detienen el monitoreo, solo se loguean
- El monitoreo continúa incluso si no hay transmisión activa
- El callback se ejecuta en el mismo hilo que el monitoreo (usar asyncio.to_thread si es blocking)
