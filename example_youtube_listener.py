"""
Ejemplo de uso del YouTube Listener
Demuestra cómo escuchar mensajes del chat en vivo
"""

import asyncio
import logging
from backend.services.youtube_api import (
    YouTubeAPI,
    YouTubeListener,
    console_message_handler,
    command_processor_handler,
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def main():
    """Ejemplo de uso del listener."""
    print("🎬 YouTube Listener - Ejemplo de Uso\n")
    
    # 1. Conectar a YouTube API
    print("📡 Conectando a YouTube API...")
    youtube = YouTubeAPI()
    
    if not youtube.connect():
        print("❌ No se pudo conectar a YouTube API")
        return
    
    print("✓ Conectado a YouTube API\n")
    
    # 2. Obtener el chat ID
    print("🔍 Buscando transmisión en vivo...")
    live_chat_id = youtube.client.get_active_live_chat_id()
    
    if not live_chat_id:
        print("❌ No hay transmisión en vivo activa")
        youtube.disconnect()
        return
    
    print(f"✓ Chat encontrado: {live_chat_id[:20]}...\n")
    
    # 3. Crear listener
    print("👂 Iniciando listener...")
    listener = YouTubeListener(youtube.client, live_chat_id)
    
    # 4. Agregar handlers
    listener.add_message_handler(console_message_handler)
    listener.add_message_handler(command_processor_handler)
    
    # 5. Iniciar listener
    await listener.start()
    print("✓ Listener iniciado")
    print("\n" + "="*60)
    print("Escuchando mensajes del chat (Ctrl+C para detener)...")
    print("="*60 + "\n")
    
    try:
        # Mantener el listener corriendo
        while listener.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Deteniendo listener...")
    
    finally:
        # 6. Detener listener
        await listener.stop()
        
        # 7. Mostrar estadísticas
        stats = listener.get_stats()
        print("\n📊 Estadísticas:")
        print(f"  Mensajes procesados: {stats['processed_messages_count']}")
        print(f"  Handlers registrados: {stats['registered_handlers']}")
        
        # 8. Desconectar
        youtube.disconnect()
        print("\n✓ Desconectado de YouTube API")


if __name__ == "__main__":
    asyncio.run(main())
