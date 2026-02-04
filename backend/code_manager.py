"""
Sistema de Códigos Recompensables para YouTube
Genera códigos aleatorios que los usuarios pueden canjear por puntos
"""
import json
import os
import time
import random
import asyncio

class CodeManager:
    """Gestor de códigos recompensables"""
    
    # Lista de palabras para los códigos
    CODE_WORDS = ["pibecarlos", "pow3r", "yutus", "Zeus", "dns","roblox","lobito","permanganato","survmay","demiex","unpowerst"]
    
    def __init__(self, data_dir: str = None):
        """Inicializa el gestor de códigos
        
        Args:
            data_dir: Directorio donde guardar los archivos de configuración
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Archivos
        self.codes_config_file = os.path.join(self.data_dir, 'codes_config.json')
        self.active_codes_file = os.path.join(self.data_dir, 'active_codes.json')
        
        # Configuración
        self.code_reward = 20  # Puntos por canjear código
        self.code_duration = 120  # Duración del código en segundos (2 minutos)
        self.code_min_interval = 5 * 60  # Mínimo 5 minutos entre códigos
        self.code_max_interval = 15 * 60  # Máximo 15 minutos entre códigos
        self.code_blink_start = 30  # Parpadear en los últimos 30 segundos
        
        # Estado activo
        self.active_code = None  # Código actual activo
        self.active_code_data = None  # Datos del código activo
        self.last_code_time = 0  # Timestamp del último código generado
        self.next_code_time = self._calculate_next_code_time()  # Próximo código
        
        self.load_config()
    
    def load_config(self):
        """Carga la configuración de códigos desde el archivo JSON"""
        try:
            with open(self.codes_config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.code_reward = data.get('reward', 20)
                self.code_duration = data.get('duration', 120)
                self.code_min_interval = data.get('min_interval', 5 * 60)
                self.code_max_interval = data.get('max_interval', 15 * 60)
                self.code_blink_start = data.get('blink_start', 30)
        except FileNotFoundError:
            self.save_config()
    
    def save_config(self):
        """Guarda la configuración de códigos al archivo JSON"""
        data = {
            'reward': self.code_reward,
            'duration': self.code_duration,
            'min_interval': self.code_min_interval,
            'max_interval': self.code_max_interval,
            'blink_start': self.code_blink_start
        }
        with open(self.codes_config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    
    def _calculate_next_code_time(self) -> float:
        """Calcula el próximo tiempo para generar un código"""
        delay = random.randint(self.code_min_interval, self.code_max_interval)
        return time.time() + delay
    
    def should_generate_code(self) -> bool:
        """Verifica si es tiempo de generar un nuevo código"""
        current_time = time.time()
        
        # Si hay un código activo, verificar si ha expirado
        if self.active_code_data:
            if current_time - self.active_code_data['created_at'] > self.code_duration:
                self._expire_code()
                return self._should_generate_based_on_timer()
            return False
        
        return self._should_generate_based_on_timer()
    
    def _should_generate_based_on_timer(self) -> bool:
        """Verifica si es tiempo basado en el temporizador"""
        return time.time() >= self.next_code_time
    
    def generate_code(self) -> dict:
        """Genera un nuevo código aleatorio
        
        Returns:
            Dict con los datos del código generado
        """
        if self.active_code:
            print(f"⚠ Código activo aún: {self.active_code}")
            return None
        
        code = random.choice(self.CODE_WORDS)
        created_at = time.time()
        
        self.active_code = code
        self.active_code_data = {
            'code': code,
            'created_at': created_at,
            'expires_at': created_at + self.code_duration
        }
        
        self.last_code_time = created_at
        self.next_code_time = self._calculate_next_code_time()
        
        self._save_active_code()
        
        print(f"🎁 Código generado: {code} (Válido por {self.code_duration}s)")
        
        return {
            'code': code,
            'duration': self.code_duration,
            'created_at': created_at
        }
    
    def _save_active_code(self):
        """Guarda el código activo en archivo JSON"""
        if self.active_code_data:
            try:
                with open(self.active_codes_file, 'w', encoding='utf-8') as f:
                    json.dump(self.active_code_data, f, indent=4, ensure_ascii=False)
                print(f"💾 Código guardado en {self.active_codes_file}")
                print(f"   Código: {self.active_code_data.get('code')}")
                print(f"   Expira en: {self.active_code_data.get('expires_at', 0) - time.time():.1f}s")
            except Exception as e:
                print(f"❌ Error guardando código: {e}")
    
    def _load_active_code(self):
        """Carga el código activo desde archivo JSON"""
        try:
            if not os.path.exists(self.active_codes_file):
                print(f"📄 Archivo de códigos no existe: {self.active_codes_file}")
                self.active_code = None
                self.active_code_data = None
                return
                
            with open(self.active_codes_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                print(f"📄 Contenido del archivo de códigos: {data}")
                
                # Si el archivo está vacío o no tiene código, tratarlo como inexistente
                if not data or 'code' not in data:
                    print("⚠️ Archivo vacío o sin código válido")
                    self.active_code = None
                    self.active_code_data = None
                    return
                
                self.active_code_data = data
                self.active_code = self.active_code_data.get('code')
                
                print(f"✓ Código cargado: {self.active_code} (expira en {self.active_code_data.get('expires_at', 0) - time.time():.1f}s)")
                
                # Verificar si ha expirado
                if time.time() > self.active_code_data.get('expires_at', 0):
                    print(f"⏰ Código ha expirado al cargar")
                    self._expire_code()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"❌ Error cargando código: {e}")
            self.active_code = None
            self.active_code_data = None
    
    def verify_code(self, user_code: str) -> tuple[bool, str]:
        """Verifica si un código es válido y puede canjearse
        
        Args:
            user_code: Código ingresado por el usuario
            
        Returns:
            Tupla (es_válido, mensaje)
        """
        # Recargar el código activo desde el archivo por si fue regenerado
        if not self.active_code:
            self._load_active_code()
        
        # Debug
        print(f"🔍 Verificando código: '{user_code}' | Código activo: '{self.active_code}' | Activo data: {self.active_code_data is not None}")
        
        # Verificar si hay código activo
        if not self.active_code:
            return False, "No hay código activo en este momento."
        
        # Verificar si el código coincide (case-insensitive)
        if user_code.lower() != self.active_code.lower():
            return False, f"Código incorrecto. Intenta de nuevo."
        
        # Verificar si ha expirado
        current_time = time.time()
        if current_time > self.active_code_data.get('expires_at', 0):
            self._expire_code()
            return False, "El código ha expirado. Espera el próximo."
        
        # ¡Código válido!
        reward = self.code_reward
        print(f"✅ Código '{user_code}' canjeado correctamente. Recompensa: {reward}₱")
        self._expire_code()  # Usar el código lo hace inválido
        
        return True, f"✓ Código correcto. +{reward}₱"
    
    def _expire_code(self):
        """Expira el código activo"""
        if self.active_code:
            print(f"❌ Código expirado: {self.active_code}")
        self.active_code = None
        self.active_code_data = None
        
        # Eliminar archivo - con manejo robusto de errores en Windows
        if os.path.exists(self.active_codes_file):
            try:
                os.remove(self.active_codes_file)
            except PermissionError:
                # Si el archivo está bloqueado, vaciarlo en lugar de eliminarlo
                try:
                    with open(self.active_codes_file, 'w') as f:
                        json.dump({}, f)
                except Exception as e:
                    print(f"⚠️ No se pudo limpiar active_codes.json: {e}")
            except Exception as e:
                print(f"⚠️ Error al eliminar código expirado: {e}")
    
    def get_code_info(self) -> dict:
        """Obtiene información del código activo actual"""
        if not self.active_code_data:
            return {'active': False}
        
        current_time = time.time()
        time_left = self.active_code_data.get('expires_at', 0) - current_time
        
        if time_left <= 0:
            self._expire_code()
            return {'active': False}
        
        return {
            'active': True,
            'code': self.active_code,
            'time_left': int(time_left),
            'should_blink': time_left <= self.code_blink_start
        }
    
    def set_reward(self, amount: int):
        """Establece la recompensa por canjear código"""
        self.code_reward = amount
        self.save_config()
        print(f"Recompensa actualizada: {amount}₱")
    
    def add_code_word(self, word: str):
        """Agrega una palabra a la lista de códigos"""
        if word not in self.CODE_WORDS:
            self.CODE_WORDS.append(word)
            print(f"Palabra agregada: {word}")
        else:
            print(f"La palabra ya existe: {word}")
    
    def remove_code_word(self, word: str):
        """Remueve una palabra de la lista de códigos"""
        if word in self.CODE_WORDS:
            self.CODE_WORDS.remove(word)
            print(f"Palabra removida: {word}")
        else:
            print(f"La palabra no existe: {word}")
