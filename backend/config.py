# Configuración general
waittime = 3
placeholderprofile = "https://th.bing.com/th/id/OIP.aiDGdmdUAX_iNgRMERipyQHaHF?rs=1&pid=ImgDetMain"

# Configuración de límites de juego
GAMBLE_MAX_BET = 100  # Límite máximo de apuesta en gamble (pews)
TRAGAMONEDAS_MAX_BET = 500  # Límite máximo de apuesta en tragamonedas (pews)

# Configuración de códigos recompensables
CODE_REWARD = 20  # Puntos por canjear un código
CODE_MIN_INTERVAL = 5 * 60  # Mínimo 5 minutos entre códigos
CODE_MAX_INTERVAL = 15 * 60  # Máximo 15 minutos entre códigos
CODE_DURATION = 120  # Duración del código en segundos (2 minutos)
CODE_BLINK_START = 30  # Comenzar a parpadear en los últimos 30 segundos

# Variables de estado global
encuesta_activa = False
votos = {}
participantes_votantes = set()
participantes_ruleta = set()
ruleta_activa = False
itstimetojoin = False
comandos_habilitados = False
keepwinner = False
isyappi = False
youtube = None
live_chat_id = None
skip_old_messages = False  # Flag para ignorar mensajes antiguos al activar la API
store_enabled = True  # Flag para habilitar/deshabilitar compras en la tienda