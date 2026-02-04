#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de validación para verificar que la sincronización con BD central funciona correctamente.
Ejecutar desde: python Aislado/VALIDAR_BD_SETUP.py
"""

import os
import sys
import json

print("=" * 70)
print("🔍 VALIDACIÓN DE CONFIGURACIÓN DE BASE DE DATOS CENTRALIZADA")
print("=" * 70)

# 1. Verificar archivo .env
print("\n1️⃣  VERIFICANDO ARCHIVO .env")
print("-" * 70)
env_path = os.path.join(os.path.dirname(__file__), 'keys', '.env')
if os.path.exists(env_path):
    print(f"✅ Archivo .env encontrado en: {env_path}")
    try:
        with open(env_path, 'r') as f:
            env_content = f.read()
        if 'DB_HOST=' in env_content and 'DB_USER=' in env_content:
            print("✅ Archivo .env contiene credenciales de BD")
            if 'panther.teramont.net' in env_content:
                print("✅ Apuntando al servidor correcto: panther.teramont.net")
            else:
                print("⚠️  El servidor no es panther.teramont.net")
        else:
            print("❌ Archivo .env no tiene credenciales de BD")
    except Exception as e:
        print(f"❌ Error leyendo .env: {e}")
else:
    print(f"❌ Archivo .env NO encontrado en: {env_path}")

# 2. Verificar ruta al backend central
print("\n2️⃣  VERIFICANDO RUTA AL BACKEND CENTRAL")
print("-" * 70)
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
print(f"Ruta esperada del backend central: {backend_root}")
if os.path.exists(backend_root):
    print(f"✅ Ruta accesible")
    
    # Verificar archivos clave
    db_file = os.path.join(backend_root, 'database.py')
    sync_file = os.path.join(backend_root, 'sync_manager.py')
    
    if os.path.exists(db_file):
        print(f"✅ database.py encontrado en backend central")
    else:
        print(f"❌ database.py NO encontrado")
    
    if os.path.exists(sync_file):
        print(f"✅ sync_manager.py encontrado en backend central")
    else:
        print(f"❌ sync_manager.py NO encontrado")
else:
    print(f"❌ Ruta NO accesible: {backend_root}")

# 3. Verificar python-dotenv instalado
print("\n3️⃣  VERIFICANDO DEPENDENCIAS")
print("-" * 70)
try:
    import dotenv
    print("✅ python-dotenv instalado")
except ImportError:
    print("❌ python-dotenv NO instalado - Instala con: pip install python-dotenv")

try:
    import mysql.connector
    print("✅ mysql-connector-python instalado")
except ImportError:
    print("❌ mysql-connector-python NO instalado - Instala con: pip install mysql-connector-python")

# 4. Verificar carga de credenciales
print("\n4️⃣  VERIFICANDO CARGA DE CREDENCIALES")
print("-" * 70)
try:
    from dotenv import load_dotenv
    
    env_path = os.path.join(os.path.dirname(__file__), 'keys', '.env')
    load_dotenv(dotenv_path=env_path)
    
    db_host = os.getenv('DB_HOST')
    db_user = os.getenv('DB_USER')
    db_name = os.getenv('DB_NAME')
    
    if db_host:
        print(f"✅ DB_HOST cargado: {db_host}")
    else:
        print("❌ DB_HOST no cargado")
    
    if db_user:
        print(f"✅ DB_USER cargado: {db_user}")
    else:
        print("❌ DB_USER no cargado")
    
    if db_name:
        print(f"✅ DB_NAME cargado: {db_name}")
    else:
        print("❌ DB_NAME no cargado")
except Exception as e:
    print(f"❌ Error cargando variables de entorno: {e}")

# 5. Intentar conexión (si es posible)
print("\n5️⃣  PROBANDO CONEXIÓN A BD")
print("-" * 70)
try:
    import mysql.connector
    from dotenv import load_dotenv
    
    env_path = os.path.join(os.path.dirname(__file__), 'keys', '.env')
    load_dotenv(dotenv_path=env_path)
    
    config_dict = {
        'host': os.getenv('DB_HOST'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD')
    }
    
    print(f"Intentando conectar a {config_dict['host']}...")
    conn = mysql.connector.connect(**config_dict)
    
    if conn.is_connected():
        print("✅ ¡CONEXIÓN EXITOSA A BD!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        cursor.close()
        
        print(f"✅ Usuarios en BD: {count}")
        conn.close()
    else:
        print("❌ No se pudo conectar a BD")
except Exception as e:
    print(f"⚠️  No se pudo conectar a BD: {e}")
    print("   (Esto es normal si el servidor no está accesible desde esta ubicación)")

# 6. Verificar estructura de caché
print("\n6️⃣  VERIFICANDO ESTRUCTURA DE CACHÉ")
print("-" * 70)
cache_path = os.path.join(os.path.dirname(__file__), 'data', 'user_cache.json')
if os.path.exists(cache_path):
    print(f"✅ user_cache.json encontrado")
    try:
        with open(cache_path, 'r') as f:
            cache = json.load(f)
        
        users = cache.get('users', [])
        print(f"✅ Usuarios en caché: {len(users)}")
        
        if users:
            first_user = users[0]
            print(f"   Ejemplo usuario: {first_user.get('name', 'N/A')}")
            if 'youtube_id' in first_user:
                print(f"   - Tiene YouTube ID: ✅")
            if 'discord_id' in first_user:
                print(f"   - Tiene Discord ID: ✅")
    except json.JSONDecodeError:
        print("❌ user_cache.json está corrupto")
else:
    print(f"⚠️  user_cache.json no encontrado (se creará al sincronizar)")

# Resumen final
print("\n" + "=" * 70)
print("📋 RESUMEN FINAL")
print("=" * 70)
print("""
✅ Si ves todos los checkmarks verdes, el sistema está correctamente configurado.

⚠️  Próximos pasos:
1. Asegúrate de tener python-dotenv instalado en ambos lados (PC y VPS)
2. Verifica que el archivo .env existe en Aislado/keys/
3. Si la BD no conecta, verifica:
   - Que la PC tenga MySQL-connector-python instalado
   - Que el firewall permita conexiones al puerto 3306
   - Que las credenciales son exactas

Para sincronizar datos:
- Ejecuta el Discord bot en la VPS
- Ejecuta el bot del PC
- Los datos se sincronizarán automáticamente a la BD central
""")
print("=" * 70)
