"""
Sistema de Economía para YouTube (Puntos/Pews)
Gestiona la ganancia de puntos por mensajes en YouTube Chat
Independiente del sistema de Discord
"""
import json
import os
import time

class YouTubeEconomyManager:
    """Gestor de economía y puntos para YouTube"""
    
    # Precios para Text-to-Voice
    TTS_NORMAL_CHAR_COST = 0.5      # Costo por carácter normal
    TTS_SPECIAL_CHAR_COST = 3    # Costo por carácter especial o emoji
    
    def __init__(self, data_dir: str = None):
        """Inicializa el gestor de economía de YouTube
        
        Args:
            data_dir: Directorio donde guardar los archivos de configuración
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Archivo de configuración (independiente de Discord)
        self.points_config_file = os.path.join(self.data_dir, 'youtube_points_config.json')
        
        # Configuración
        self.user_message_count = {}       # {youtube_id: {timestamp: count}} para tracking temporal
        self.points_interval = 5 * 60      # 5 minutos en segundos
        self.points_enabled = True         # Sistema de puntos habilitado/deshabilitado
        
        self.load_config()
    
    def load_config(self):
        """Carga la configuración de puntos de YouTube desde el archivo JSON"""
        try:
            with open(self.points_config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.points_interval = data.get('interval', 5 * 60)
                self.points_enabled = data.get('enabled', True)
        except FileNotFoundError:
            self.points_interval = 5 * 60
            self.points_enabled = True
            self.save_config()
    
    def save_config(self):
        """Guarda la configuración de puntos de YouTube al archivo JSON"""
        data = {
            'interval': self.points_interval,
            'enabled': self.points_enabled
        }
        with open(self.points_config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    
    def toggle_points(self) -> bool:
        """Alterna el estado del sistema de puntos de YouTube
        
        Returns:
            Estado actual del sistema (True = habilitado, False = deshabilitado)
        """
        self.points_enabled = not self.points_enabled
        self.save_config()
        estado = "✓ activado" if self.points_enabled else "✓ desactivado"
        #print(f"Sistema de puntos de YouTube {estado}")
        return self.points_enabled
    
    def is_enabled(self) -> bool:
        """Verifica si el sistema de puntos de YouTube está habilitado
        
        Returns:
            True si está habilitado, False si está deshabilitado
        """
        return self.points_enabled
    
    def get_status(self) -> dict:
        """Obtiene el estado del sistema de economía de YouTube
        
        Returns:
            Dict con información del estado
        """
        return {
            'enabled': self.points_enabled,
            'interval': self.points_interval,
            'interval_minutes': self.points_interval / 60
        }
    
    def process_message(self, youtube_id: str) -> bool:
        """Procesa un mensaje de un usuario para determinar si gana puntos
        
        Args:
            youtube_id: ID de YouTube del usuario
            
        Returns:
            True si el usuario debe ganar puntos, False si no
        """
        # Si el sistema está deshabilitado, no procesar
        if not self.points_enabled:
            return False
        
        current_time = int(time.time())
        time_window = current_time - self.points_interval
        
        youtube_id_str = str(youtube_id)
        
        # Inicializar tracking del usuario si no existe
        if youtube_id_str not in self.user_message_count:
            self.user_message_count[youtube_id_str] = {}
            # Primer mensaje - retornar True inmediatamente
            self.user_message_count[youtube_id_str][current_time] = 1
            return True
        
        # Limpiar mensajes antiguos fuera del rango de tiempo
        self.user_message_count[youtube_id_str] = {
            ts: count for ts, count in self.user_message_count[youtube_id_str].items()
            if ts > time_window
        }
        
        # Contar mensaje actual
        self.user_message_count[youtube_id_str][current_time] = \
            self.user_message_count[youtube_id_str].get(current_time, 0) + 1
        
        # Si es el primer mensaje en el rango de tiempo, retornar True
        # Verificar si hay más de un timestamp o si el timestamp actual es el único
        if len(self.user_message_count[youtube_id_str]) == 1:
            # Solo existe el timestamp actual
            return True
        
        return False
    
    def clean_inactive_users(self, max_age_seconds: int = 3600):
        """Limpia los datos de usuarios inactivos
        
        Args:
            max_age_seconds: Edad máxima en segundos antes de limpiar
        """
        current_time = int(time.time())
        cutoff_time = current_time - max_age_seconds
        
        for youtube_id_str in list(self.user_message_count.keys()):
            # Limpiar timestamps antiguos
            self.user_message_count[youtube_id_str] = {
                ts: count for ts, count in self.user_message_count[youtube_id_str].items()
                if ts > cutoff_time
            }
            
            # Eliminar usuario si no tiene más mensajes
            if not self.user_message_count[youtube_id_str]:
                del self.user_message_count[youtube_id_str]
    
    @staticmethod
    def calculate_tts_cost(text: str) -> float:
        """Calcula el costo de un mensaje de text-to-voice
        
        Precio: 
        - Caracteres normales: 0.5₱
        - Caracteres especiales (emoji, _, etc): 3₱
        - Espacios: GRATIS
        
        Args:
            text: Texto a procesar
            
        Returns:
            Costo total en ₱ (redondeado a 2 decimales)
        """
        if not text:
            return 0.0
        
        cost = 0.0
        special_chars = {'_', '@', '#', '$', '%', '&', '*', '!', '?', '¿', '¡', '~', '^', '[', ']', '{', '}', '|', '\\', '/', '<', '>', '=', '+', '-', '.', ',', ';', ':', '"', "'", '`'}
        
        for char in text:
            # Los espacios no cuestan
            if char == ' ':
                continue
            
            # Detectar emojis (caracteres fuera del rango ASCII)
            try:
                if ord(char) > 127:  # Caracteres no-ASCII incluyen emojis
                    cost += YouTubeEconomyManager.TTS_SPECIAL_CHAR_COST
                elif char in special_chars:
                    cost += YouTubeEconomyManager.TTS_SPECIAL_CHAR_COST
                else:
                    # Caracteres normales
                    cost += YouTubeEconomyManager.TTS_NORMAL_CHAR_COST
            except:
                cost += YouTubeEconomyManager.TTS_SPECIAL_CHAR_COST
        
        return round(cost, 2)
