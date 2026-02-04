"""
Sistema de Economía (Puntos/Pews) para Discord Bot
Gestiona la ganancia de puntos por mensajes en canales específicos
"""
import json
import os
import time
from datetime import datetime, timezone, timedelta

class EconomyManager:
    """Gestor de economía y puntos del sistema"""
    
    def __init__(self, data_dir: str = None):
        """Inicializa el gestor de economía
        
        Args:
            data_dir: Directorio donde guardar los archivos de configuración
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'discordbot', 'data')
        
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Archivo de configuración
        self.points_config_file = os.path.join(self.data_dir, 'points_config.json')
        
        # Configuración
        self.points_channels = []          # Canales donde se ganan puntos
        self.user_message_count = {}       # {discord_id: {timestamp: count}} para tracking temporal
        self.points_interval = 5 * 60      # 5 minutos en segundos
        self.points_per_interval = 1       # Puntos ganados por intervalo
        self.points_enabled = True         # Sistema de puntos habilitado/deshabilitado
        self.voice_users = {}              # {user_id: timestamp_entrada} para tracking de voz
        
        self.load_config()
    
    def load_config(self):
        """Carga la configuración de puntos desde el archivo JSON"""
        try:
            with open(self.points_config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.points_channels = data.get('channels', [])
                self.points_interval = data.get('interval', 5 * 60)
                self.points_per_interval = data.get('points_per_interval', 1)
                self.points_enabled = data.get('enabled', True)
        except FileNotFoundError:
            self.points_channels = []
            self.points_interval = 5 * 60
            self.points_per_interval = 1
            self.points_enabled = True
            self.save_config()
    
    def save_config(self):
        """Guarda la configuración de puntos al archivo JSON"""
        data = {
            'channels': self.points_channels,
            'interval': self.points_interval,
            'points_per_interval': self.points_per_interval,
            'enabled': self.points_enabled
        }
        with open(self.points_config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    
    def add_points_channel(self, channel_id: int) -> bool:
        """Agrega un canal a la lista de canales para ganar puntos
        
        Args:
            channel_id: ID del canal
            
        Returns:
            True si se agregó exitosamente, False si ya existía
        """
        channel_id_str = str(channel_id)
        if channel_id_str not in self.points_channels:
            self.points_channels.append(channel_id_str)
            self.save_config()
            print(f"✓ Canal {channel_id} agregado al sistema de puntos")
            return True
        print(f"⚠ Canal {channel_id} ya está en el sistema de puntos")
        return False
    
    def remove_points_channel(self, channel_id: int) -> bool:
        """Remueve un canal de la lista de canales para ganar puntos
        
        Args:
            channel_id: ID del canal
            
        Returns:
            True si se removió exitosamente, False si no existía
        """
        channel_id_str = str(channel_id)
        if channel_id_str in self.points_channels:
            self.points_channels.remove(channel_id_str)
            self.save_config()
            print(f"✓ Canal {channel_id} removido del sistema de puntos")
            return True
        print(f"⚠ Canal {channel_id} no estaba en el sistema de puntos")
        return False
    
    def toggle_points(self) -> bool:
        """Alterna el estado del sistema de puntos
        
        Returns:
            Estado actual del sistema (True = habilitado, False = deshabilitado)
        """
        self.points_enabled = not self.points_enabled
        self.save_config()
        estado = "✓ activado" if self.points_enabled else "✓ desactivado"
        #print(f"Sistema de puntos {estado}")
        return self.points_enabled
    
    def is_enabled(self) -> bool:
        """Verifica si el sistema de puntos está habilitado
        
        Returns:
            True si está habilitado, False si está deshabilitado
        """
        return self.points_enabled
    
    def get_status(self) -> dict:
        """Obtiene el estado del sistema de economía
        
        Returns:
            Dict con información del estado
        """
        return {
            'enabled': self.points_enabled,
            'channels': self.points_channels,
            'interval': self.points_interval,
            'interval_minutes': self.points_interval / 60
        }
    
    def process_message(self, user_id: int) -> bool:
        """Procesa un mensaje de un usuario para determinar si gana puntos
        
        Args:
            user_id: ID del usuario de Discord
            
        Returns:
            True si el usuario debe ganar puntos, False si no
        """
        # Si el sistema está deshabilitado, no procesar
        if not self.points_enabled:
            return False
        
        current_time = int(time.time())
        time_window = current_time - self.points_interval
        
        user_id_str = str(user_id)
        
        # Inicializar tracking del usuario si no existe
        if user_id_str not in self.user_message_count:
            self.user_message_count[user_id_str] = {}
        
        # Limpiar mensajes antiguos fuera del rango de tiempo
        self.user_message_count[user_id_str] = {
            ts: count for ts, count in self.user_message_count[user_id_str].items()
            if ts > time_window
        }
        
        # Contar mensaje actual
        self.user_message_count[user_id_str][current_time] = \
            self.user_message_count[user_id_str].get(current_time, 0) + 1
        
        # Si es el primer mensaje en el rango de tiempo, retornar True
        total_messages = sum(self.user_message_count[user_id_str].values())
        return total_messages == 1
    
    def clean_inactive_users(self, max_age_seconds: int = 3600):
        """Limpia los datos de usuarios inactivos
        
        Args:
            max_age_seconds: Edad máxima en segundos antes de limpiar
        """
        current_time = int(time.time())
        cutoff_time = current_time - max_age_seconds
        
        for user_id_str in list(self.user_message_count.keys()):
            # Limpiar timestamps antiguos
            self.user_message_count[user_id_str] = {
                ts: count for ts, count in self.user_message_count[user_id_str].items()
                if ts > cutoff_time
            }
            
            # Eliminar usuario si no tiene más mensajes
            if not self.user_message_count[user_id_str]:
                del self.user_message_count[user_id_str]
    
    def add_voice_user(self, user_id: int) -> None:
        """Registra cuando un usuario entra a un canal de voz
        
        Args:
            user_id: ID del usuario de Discord
        """
        user_id_str = str(user_id)
        self.voice_users[user_id_str] = int(time.time())
    
    def remove_voice_user(self, user_id: int) -> None:
        """Registra cuando un usuario sale de un canal de voz
        
        Args:
            user_id: ID del usuario de Discord
        """
        user_id_str = str(user_id)
        if user_id_str in self.voice_users:
            del self.voice_users[user_id_str]
    
    def get_voice_points_earned(self, user_id: int) -> bool:
        """Verifica si un usuario en voz debe ganar puntos
        
        Args:
            user_id: ID del usuario de Discord
            
        Returns:
            True si debe ganar puntos, False si no
        """
        if not self.points_enabled:
            return False
        
        user_id_str = str(user_id)
        if user_id_str not in self.voice_users:
            return False
        
        entry_time = self.voice_users[user_id_str]
        current_time = int(time.time())
        time_elapsed = current_time - entry_time
        
        # Si ha pasado el intervalo de puntos, retornar True
        if time_elapsed >= self.points_interval:
            # Actualizar el timestamp para la próxima ganancia
            self.voice_users[user_id_str] = current_time
            return True
        
        return False
    
    def get_all_voice_users(self) -> list:
        """Obtiene lista de todos los usuarios en voz
        
        Returns:
            Lista de IDs de usuarios en canales de voz
        """
        return [int(user_id) for user_id in self.voice_users.keys()]
    
    def set_points_per_interval(self, amount: float) -> bool:
        """Establece la cantidad de puntos ganados por intervalo
        
        Args:
            amount: Cantidad de puntos a ganar por intervalo (puede ser decimal)
            
        Returns:
            True si se configuró correctamente
        """
        if amount <= 0:
            return False
        
        self.points_per_interval = amount
        self.save_config()
        print(f"✓ Puntos por intervalo establecidos a: {amount}")
        return True
    
    def get_points_per_interval(self) -> float:
        """Obtiene la cantidad de puntos ganados por intervalo
        
        Returns:
            Cantidad de puntos por intervalo
        """
        return self.points_per_interval
    
    def get_config_summary(self) -> dict:
        """Obtiene un resumen de la configuración actual
        
        Returns:
            Dict con la configuración del sistema de puntos
        """
        return {
            'enabled': self.points_enabled,
            'channels': len(self.points_channels),
            'points_per_interval': self.points_per_interval,
            'interval_minutes': self.points_interval / 60,
            'active_voice_users': len(self.voice_users)
        }

