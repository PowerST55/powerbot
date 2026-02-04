"""
Sistema de Vinculación de Cuentas Discord-YouTube
Gestiona el proceso de vincular cuentas entre plataformas
"""
import json
import os
import time
import secrets
import string

class AccountLinkingManager:
    """Gestor de vinculación de cuentas entre Discord y YouTube"""
    
    def __init__(self, data_dir: str = None):
        """Inicializa el gestor de vinculación
        
        Args:
            data_dir: Directorio donde guardar los datos
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Archivo para pendientes de vinculación
        self.pending_file = os.path.join(self.data_dir, 'pending_links.json')
        
        # Almacenamiento en memoria para vinculaciones pendientes
        # {codigo: {discord_id, discord_name, timestamp, timeout}}
        self.pending_links = {}
        
        # Cargar pendientes del archivo
        self.load_pending_links()
    
    def load_pending_links(self):
        """Carga las vinculaciones pendientes del archivo JSON"""
        try:
            with open(self.pending_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.pending_links = data.get('pending', {})
        except FileNotFoundError:
            self.pending_links = {}
    
    def save_pending_links(self):
        """Guarda las vinculaciones pendientes al archivo JSON"""
        data = {'pending': self.pending_links}
        with open(self.pending_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✓ Guardado {len(self.pending_links)} códigos pendientes en {self.pending_file}")
    
    def generate_link_code(self) -> str:
        """Genera un código único para vinculación
        
        Returns:
            str: Código único de 6 caracteres alfanuméricos
        """
        # Generar código de 6 caracteres (números y letras mayúsculas)
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if code not in self.pending_links:
                return code
    
    def create_pending_link(self, discord_id: int, discord_name: str, timeout_seconds: int = 600) -> str:
        """Crea una vinculación pendiente para un usuario de Discord
        
        Args:
            discord_id: ID de Discord del usuario
            discord_name: Nombre de Discord del usuario
            timeout_seconds: Segundos hasta que expire (default 10 minutos = 600s)
            
        Returns:
            str: Código único para usar en YouTube
        """
        code = self.generate_link_code()
        current_time = int(time.time())
        
        self.pending_links[code] = {
            'discord_id': discord_id,
            'discord_name': discord_name,
            'timestamp': current_time,
            'timeout': timeout_seconds
        }
        
        self.save_pending_links()
        print(f"✓ Vinculación pendiente creada: {code} para {discord_name}")
        return code
    
    def get_pending_link(self, code: str) -> dict:
        """Obtiene la información de una vinculación pendiente
        
        Args:
            code: Código de vinculación
            
        Returns:
            dict: Información de la vinculación o None si no existe/expiró
        """
        # IMPORTANTE: Recargar desde archivo para ver códigos creados por otras instancias
        self.load_pending_links()
        
        if code not in self.pending_links:
            print(f"⚠ Código {code} no encontrado. Códigos disponibles: {list(self.pending_links.keys())}")
            return None
        
        link_info = self.pending_links[code]
        current_time = int(time.time())
        created_time = link_info['timestamp']
        timeout = link_info['timeout']
        
        # Verificar si ha expirado
        if current_time - created_time > timeout:
            # Expiró, eliminar
            del self.pending_links[code]
            self.save_pending_links()
            print(f"⚠ Código {code} expiró (edad: {current_time - created_time}s, timeout: {timeout}s)")
            return None
        
        print(f"✓ Código {code} validado correctamente")
        return link_info
    
    def remove_pending_link(self, code: str) -> bool:
        """Elimina una vinculación pendiente
        
        Args:
            code: Código de vinculación
            
        Returns:
            bool: True si se eliminó, False si no existía
        """
        if code in self.pending_links:
            del self.pending_links[code]
            self.save_pending_links()
            return True
        return False
    
    def cleanup_expired_links(self):
        """Limpia todas las vinculaciones expiradas"""
        current_time = int(time.time())
        expired_codes = []
        
        for code, link_info in self.pending_links.items():
            created_time = link_info['timestamp']
            timeout = link_info['timeout']
            
            if current_time - created_time > timeout:
                expired_codes.append(code)
        
        for code in expired_codes:
            del self.pending_links[code]
        
        if expired_codes:
            self.save_pending_links()
            print(f"⚠ Limpieza: {len(expired_codes)} códigos expirados removidos")
    
    def get_pending_links_count(self) -> int:
        """Obtiene el número de vinculaciones pendientes activas"""
        self.cleanup_expired_links()
        return len(self.pending_links)
    
    def list_pending_links(self) -> dict:
        """Lista todas las vinculaciones pendientes activas"""
        self.cleanup_expired_links()
        return dict(self.pending_links)
