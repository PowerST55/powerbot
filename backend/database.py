import mysql.connector
from mysql.connector import Error
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Configurar logging PRIMERO
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    # Cargar .env desde la carpeta keys/
    env_path = os.path.join(os.path.dirname(__file__), '..', 'keys', '.env')
    load_dotenv(dotenv_path=env_path)
    logger.debug(f"✓ Variables de entorno cargadas desde: {env_path}")
except ImportError:
    logger.warning("⚠ python-dotenv no instalado. Instala con: pip install python-dotenv")


class DatabaseManager:
    """Gestor centralizado de BD MySQL con sincronización con JSON"""
    
    def __init__(self, config_dict: Dict = None):
        """Inicializa conexión a la BD
        
        Args:
            config_dict: Dict con host, port, database, user, password
                        Si None, carga desde variables de entorno
        """
        if config_dict is None:
            config_dict = {
                'host': os.getenv('DB_HOST'),
                'port': int(os.getenv('DB_PORT', 3306)),
                'database': os.getenv('DB_NAME'),
                'user': os.getenv('DB_USER'),
                'password': os.getenv('DB_PASSWORD')
            }
        
        self.config = config_dict
        self.connection = None
        self.is_connected = False
        self.connect()
    
    def connect(self):
        """Establece conexión con la BD con reintentos"""
        try:
            self.connection = mysql.connector.connect(**self.config)
            if self.connection.is_connected():
                self.is_connected = True
                db_info = self.connection.get_server_info()
                logger.info(f"✓ Conectado a BD MySQL {db_info}: {self.config['database']}")
                self._create_tables()
                return True
        except Error as e:
            self.is_connected = False
            logger.warning(f"⚠ No se pudo conectar a BD: {e}")
            logger.warning("  Los datos se guardarán en caché local y se sincronizarán cuando la BD esté disponible")
            return False
    
    def _create_tables(self):
        """Crea las tablas necesarias si no existen"""
        try:
            cursor = self.connection.cursor()
            
            # Tabla de usuarios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    youtube_id VARCHAR(255) UNIQUE,
                    discord_id VARCHAR(255) UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    avatar_url TEXT,
                    avatar_discord_url TEXT,
                    puntos DECIMAL(10, 2) DEFAULT 0,
                    is_moderator BOOLEAN DEFAULT FALSE,
                    is_member BOOLEAN DEFAULT FALSE,
                    platform_sources JSON DEFAULT '["unknown"]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    synced_at TIMESTAMP NULL,
                    INDEX idx_youtube (youtube_id),
                    INDEX idx_discord (discord_id),
                    INDEX idx_updated (updated_at)
                )
            """)
            
            # Tabla de transacciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    username VARCHAR(255),
                    platform VARCHAR(50),
                    transaction_type VARCHAR(50),
                    amount DECIMAL(10, 2),
                    balance_after DECIMAL(10, 2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    synced_at TIMESTAMP NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user (user_id),
                    INDEX idx_created (created_at)
                )
            """)
            
            # Tabla de tienda
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS store_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    item_id VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    price DECIMAL(10, 2),
                    inflation_percentage DECIMAL(5, 2) DEFAULT 0,
                    last_inflation_date TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    synced_at TIMESTAMP NULL,
                    INDEX idx_item_id (item_id)
                )
            """)
            
            # Tabla de vinculaciones pendientes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_links (
                    code VARCHAR(10) PRIMARY KEY,
                    discord_id VARCHAR(255),
                    discord_name VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    synced_at TIMESTAMP NULL,
                    INDEX idx_discord (discord_id),
                    INDEX idx_expires (expires_at)
                )
            """)
            
            # Tabla de sincronización (para evitar conflictos)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    entity_type VARCHAR(50),
                    entity_id VARCHAR(255),
                    action VARCHAR(20),
                    source VARCHAR(50),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_entity (entity_type, entity_id),
                    INDEX idx_timestamp (timestamp)
                )
            """)
            
            self.connection.commit()
            cursor.close()
            logger.info("✓ Tablas verificadas/creadas exitosamente")
            return True
            
        except Error as e:
            logger.error(f"⚠ Error creando tablas: {e}")
            return False
    
    def sync_user_from_cache(self, user_dict: Dict) -> bool:
        """Sincroniza un usuario desde caché JSON a BD con detección de conflictos
        
        Args:
            user_dict: Dict del usuario desde user_cache.json
            
        Returns:
            bool: True si se sincronizó exitosamente
        """
        if not self.is_connected or not self.connection.is_connected():
            logger.debug("⚠ Sin conexión a BD, usuario NO sincronizado")
            return False
        
        try:
            cursor = self.connection.cursor()
            
            platform_sources = json.dumps(user_dict.get('platform_sources', ['unknown']))
            
            # Extraer IDs (uno debe ser no-None)
            youtube_id = user_dict.get('youtube_id')
            discord_id = user_dict.get('discord_id')
            
            # Validación
            if not youtube_id and not discord_id:
                logger.warning(f"⚠ Usuario sin identificadores válidos: {user_dict.get('name')}")
                return False
            
            cursor.execute("""
                INSERT INTO users 
                (youtube_id, discord_id, name, avatar_url, avatar_discord_url, 
                 puntos, is_moderator, is_member, platform_sources, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                avatar_url = VALUES(avatar_url),
                avatar_discord_url = VALUES(avatar_discord_url),
                puntos = VALUES(puntos),
                is_moderator = VALUES(is_moderator),
                is_member = VALUES(is_member),
                platform_sources = VALUES(platform_sources),
                synced_at = NOW()
            """, (
                youtube_id,
                discord_id,
                user_dict.get('name', 'Unknown'),
                user_dict.get('avatar_url'),
                user_dict.get('avatar_discord_url'),
                float(user_dict.get('puntos', 0)),
                bool(user_dict.get('isModerator', False)),
                bool(user_dict.get('isMember', False)),
                platform_sources
            ))
            
            # Registrar en log de sincronización
            cursor.execute("""
                INSERT INTO sync_log (entity_type, entity_id, action, source)
                VALUES ('user', %s, 'sync', 'local_cache')
            """, (youtube_id or discord_id,))
            
            self.connection.commit()
            cursor.close()
            logger.debug(f"✓ Usuario '{user_dict.get('name')}' sincronizado a BD")
            return True
            
        except Error as e:
            logger.warning(f"⚠ Error sincronizando usuario: {e}")
            return False
    
    def get_user_by_discord_id(self, discord_id: str) -> Optional[Dict]:
        """Obtiene usuario por discord_id desde BD"""
        if not self.is_connected or not self.connection.is_connected():
            return None
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM users WHERE discord_id = %s",
                (str(discord_id),)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result and result.get('platform_sources'):
                result['platform_sources'] = json.loads(result['platform_sources'])
            
            return result
        except Error as e:
            logger.warning(f"⚠ Error consultando usuario por Discord: {e}")
            return None
    
    def get_user_by_youtube_id(self, youtube_id: str) -> Optional[Dict]:
        """Obtiene usuario por youtube_id desde BD"""
        if not self.is_connected or not self.connection.is_connected():
            return None
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM users WHERE youtube_id = %s",
                (str(youtube_id),)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result and result.get('platform_sources'):
                result['platform_sources'] = json.loads(result['platform_sources'])
            
            return result
        except Error as e:
            logger.warning(f"⚠ Error consultando usuario por YouTube: {e}")
            return None
    
    def add_points(self, user_id: int, points: float, source: str = 'unknown') -> bool:
        """Suma puntos a un usuario"""
        if not self.is_connected or not self.connection.is_connected():
            return False
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "UPDATE users SET puntos = puntos + %s, updated_at = NOW() WHERE id = %s",
                (float(points), user_id)
            )
            
            # Registrar en log
            cursor.execute("""
                INSERT INTO sync_log (entity_type, entity_id, action, source)
                VALUES ('points', %s, 'add', %s)
            """, (str(user_id), source))
            
            self.connection.commit()
            cursor.close()
            return True
        except Error as e:
            logger.warning(f"⚠ Error actualizando puntos: {e}")
            return False
    
    def subtract_points(self, user_id: int, points: float, source: str = 'unknown') -> bool:
        """Resta puntos a un usuario"""
        if not self.is_connected or not self.connection.is_connected():
            return False
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "UPDATE users SET puntos = puntos - %s, updated_at = NOW() WHERE id = %s",
                (float(points), user_id)
            )
            
            # Registrar en log
            cursor.execute("""
                INSERT INTO sync_log (entity_type, entity_id, action, source)
                VALUES ('points', %s, 'subtract', %s)
            """, (str(user_id), source))
            
            self.connection.commit()
            cursor.close()
            return True
        except Error as e:
            logger.warning(f"⚠ Error restando puntos: {e}")
            return False
    
    def log_transaction(self, user_id: int, username: str, platform: str, 
                       tx_type: str, amount: float, balance_after: float) -> bool:
        """Registra una transacción"""
        if not self.is_connected or not self.connection.is_connected():
            return False
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO transactions 
                (user_id, username, platform, transaction_type, amount, balance_after, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (user_id, username, platform, tx_type, float(amount), float(balance_after)))
            
            self.connection.commit()
            cursor.close()
            return True
        except Error as e:
            logger.warning(f"⚠ Error registrando transacción: {e}")
            return False
    
    def get_user_transactions(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Obtiene transacciones de un usuario"""
        if not self.is_connected or not self.connection.is_connected():
            return []
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM transactions WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit)
            )
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            logger.warning(f"⚠ Error obteniendo transacciones: {e}")
            return []
    
    def link_accounts(self, discord_id: str, youtube_id: str) -> bool:
        """Vincula cuentas Discord y YouTube"""
        if not self.is_connected or not self.connection.is_connected():
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # Buscar usuario por YouTube y actualizar discord_id
            cursor.execute(
                "UPDATE users SET discord_id = %s, updated_at = NOW() WHERE youtube_id = %s",
                (discord_id, youtube_id)
            )
            
            # Registrar en log
            cursor.execute("""
                INSERT INTO sync_log (entity_type, entity_id, action, source)
                VALUES ('link', %s, 'link_accounts', 'system')
            """, (youtube_id,))
            
            self.connection.commit()
            cursor.close()
            logger.info(f"✓ Cuentas vinculadas: Discord {discord_id} <-> YouTube {youtube_id}")
            return True
        except Error as e:
            logger.warning(f"⚠ Error vinculando cuentas: {e}")
            return False
    
    def close(self):
        """Cierra la conexión"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            self.is_connected = False
            logger.info("✓ Conexión BD cerrada")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
