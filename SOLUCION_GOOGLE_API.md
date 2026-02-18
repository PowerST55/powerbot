# Solución: Error "No module named 'google'"

## 🔍 Problema Identificado

El sistema mostraba que instalaba 2 paquetes faltantes pero luego fallaba con:
```
⚠ Error al conectar YouTube: No module named 'google'
```

**Causa raíz**: Las dependencias de Google API (`google-auth`, `google-auth-oauthlib`, `google-api-python-client`) **NO estaban en el pyproject.toml**.

## ✅ Solución Aplicada

### 1. Agregadas dependencias de Google al pyproject.toml

```toml
dependencies = [
    "prompt-toolkit>=3.0.36",
    "rich>=13.7.0",
    "discord.py>=2.3.0",
    "python-dotenv>=1.0.0",
    "google-auth>=2.23.0",              # ⬅️ NUEVO
    "google-auth-oauthlib>=1.1.0",      # ⬅️ NUEVO
    "google-api-python-client>=2.100.0", # ⬅️ NUEVO
]
```

### 2. Actualizado bootstrap.py para reconocer paquetes de Google

Se agregaron mapeos especiales para que el sistema reconozca correctamente:
- `google-auth` → importa como `google.auth`
- `google-auth-oauthlib` → importa como `google_auth_oauthlib`
- `google-api-python-client` → importa como `googleapiclient`
- `python-dotenv` → importa como `dotenv`
- `discord.py` → importa como `discord`

## ✅ Verificación

```bash
python test_google_dependencies.py
```

Resultado:
```
✅ TODAS LAS DEPENDENCIAS ESTÁN INSTALADAS CORRECTAMENTE

Bootstrap: ✅ PASS
Google Imports: ✅ PASS
YouTube Core: ✅ PASS
```

## 🚀 Cómo Usar

### Opción 1: Comando TODO EN UNO (Recomendado)

```bash
python backend/app.py
```

En la consola escribe:
```
yapi
```

Esto automáticamente:
1. ✅ Conecta YouTube API
2. ✅ Busca transmisión en vivo
3. ✅ Inicia listener de mensajes
4. ✅ Inicia monitoreo automático de nuevas transmisiones

### Opción 2: Paso a paso

```bash
python backend/app.py
```

En la consola:
```
yt autorun       # Activa/desactiva inicio automático
yt listener      # Inicia listener manualmente
yt status        # Ver estado del sistema
yt stop_listener # Detener listener
```

## 📁 Archivos Modificados

1. **pyproject.toml** - Agregadas dependencias de Google API
2. **backend/bootstrap.py** - Actualizado mapeo de nombres de paquetes
3. **backend/console/commands/commands_youtube.py** - Agregado comando `yapi`
4. **backend/console/commands/commands_general.py** - Registrado comando `yapi`

## 🎯 Resultado

Ahora cuando ejecutes `python backend/app.py`:

✅ **SIN ERRORES**:
- Instalará automáticamente las dependencias de Google
- No mostrará "No module named 'google'"
- El autorun de YouTube funcionará correctamente

✅ **Comando `/yapi` disponible**:
- Conecta YouTube API automáticamente
- Busca transmisión en vivo
- Inicia listener de mensajes
- Imprime mensajes del chat en consola

## 💡 Notas

- Las dependencias se instalan **automáticamente** al iniciar la aplicación
- Si tienes un entorno virtual (venv), las dependencias se instalarán ahí
- Si no tienes venv, se instalarán en tu Python global
- El archivo `backend/data/youtube_bot/active_chat.json` guarda el último chat ID

## 🐛 Si Aún Tienes Problemas

Instalación manual:
```bash
pip install google-auth google-auth-oauthlib google-api-python-client
```

Verificación:
```bash
python -c "import google.auth; import google_auth_oauthlib; import googleapiclient; print('✅ Todo OK')"
```
