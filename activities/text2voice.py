"""
Módulo de Text-to-Voice usando Google Text-to-Speech (gTTS)
Configurado para español - Reproduce audio directamente sin almacenarlo
"""

from gtts import gTTS
import pygame
from io import BytesIO
import os
import time


class TextToVoice:
    """Clase para convertir texto a voz usando gTTS"""
    
    def __init__(self, lang='es', slow=False):
        """
        Inicializar el convertidor de texto a voz
        
        Args:
            lang (str): Código de idioma (default: 'es' para español)
            slow (bool): Reproducir lentamente (default: False)
        """
        self.lang = lang
        self.slow = slow
    
    def text_to_speech(self, text):
        """
        Convertir texto a voz y reproducir directamente
        
        Args:
            text (str): Texto a convertir y reproducir
            
        Returns:
            bool: True si se reprodujo exitosamente, False si hubo error
        """
        try:
            print(f"🔊 Reproduciendo: {text[:60]}...")
            
            # Crear objeto gTTS
            tts = gTTS(text=text, lang=self.lang, slow=self.slow)
            
            # Crear stream en memoria
            stream = BytesIO()
            tts.write_to_fp(stream)
            stream.seek(0)
            
            # Inicializar pygame mixer si es necesario
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            # Cargar directamente desde bytes
            sound = pygame.mixer.Sound(stream)
            sound.play()
            
            # Esperar a que termine la reproducción
            duration = sound.get_length()
            time.sleep(duration + 0.1)
            
            print("✓ Audio reproducido correctamente")
            return True
                
        except Exception as e:
            print(f"✗ Error al reproducir voz: {e}")
            return False
    
    def set_language(self, lang):
        """
        Cambiar idioma de reproducción
        
        Args:
            lang (str): Código de idioma ISO 639-1
                - 'es': Español
                - 'en': Inglés
                - 'fr': Francés
                - 'de': Alemán
        """
        self.lang = lang
        print(f"Idioma configurado: {lang}")
    
    def set_speed(self, slow=False):
        """
        Cambiar velocidad de reproducción
        
        Args:
            slow (bool): True para lento, False para normal
        """
        self.slow = slow
        speed = "Lento" if slow else "Normal"
        print(f"Velocidad configurada: {speed}")


# Ejemplo de uso
if __name__ == "__main__":
    # Crear instancia de TextToVoice en español
    tts = TextToVoice(lang='es', slow=False)
    
    # Ejemplo 1: Reproducir directamente
    print("=== Ejemplo 1: Saludos ===")
    tts.text_to_speech("Hola, esto es un test de conversión de texto a voz🤔🤔🤔🤔")
    
    # Ejemplo 2: Reproducir lentamente
    print("\n=== Ejemplo 2: Audio lento ===")
    tts.set_speed(True)
    tts.text_to_speech("Este mensaje se reproduce lentamente")
    tts.set_speed(False)
    
    # Ejemplo 3: Mensajes diferentes
    print("\n=== Ejemplo 3: Mensajes variados ===")
    tts.text_to_speech("¿Cómo estás hoy?")
    
    print("\n✓ Ejemplos completados")
