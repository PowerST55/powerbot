# PowerBot - Discord Bot

Bot de Discord para PowerBot con sistema de puntos, tienda y más.

## Instalación

### Localmente
```bash
# Clonar repositorio
git clone https://github.com/TU_USUARIO/powerbot-discord.git
cd powerbot-discord

# Instalar dependencias
pip install -r requirements.txt

# Crear archivo .env
cp keys/.env.example keys/.env

# Editar .env con tu TOKEN
nano keys/.env  # o tu editor favorito
# Agregar: TOKEN=tu_token_de_discord_aqui
```

### En servidor (Teramont VPS)
```bash
git clone https://github.com/TU_USUARIO/powerbot-discord.git bot
cd bot
pip3 install -r requirements.txt

# Crear .env
cp keys/.env.example keys/.env
nano keys/.env  # Agregar TOKEN real
```

## Variables de entorno (.env)

```
TOKEN=tu_token_de_discord_aqui
PREFIX=!
```

- **TOKEN**: Obtén tu token en https://discord.com/developers/applications
- **PREFIX**: Prefijo para comandos (ej: !ayuda)

## Ejecutar

```bash
python start.py
```

## Estructura del proyecto

```
.
├── discordbot/       # Bot principal
├── backend/          # Lógica de backend
├── activities/       # Actividades del bot
├── data/            # Archivos de datos
├── keys/
│   ├── .env         # Credenciales (no subir a GitHub)
│   └── .env.example # Plantilla
├── requirements.txt
└── start.py
```

## IMPORTANTE

⚠️ **NUNCA subas `keys/.env` a GitHub**

El archivo `.gitignore` está configurado para evitarlo, pero verifica con:
```bash
git status
```

Debe mostrar `.env` como ignorado.
