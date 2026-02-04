#!/usr/bin/env python3
"""
Ejemplo de integración del sistema de BD con Discord Bot en VPS

Este archivo muestra cómo usar la sincronización desde el VPS.
Los comandos automáticamente sincronizarán con el cliente local.
"""

# ============================================================
# IMPORTAR EL SISTEMA DE SINCRONIZACIÓN
# ============================================================
import os
import sys

# Asegurar que el path incluye el backend
BACKEND_PATH = os.path.abspath(os.path.dirname(__file__))
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

# Importar el gestor de usuarios (que ahora incluye sincronización)
from usermanager import (
    cache_discord_user,
    add_points_to_user,
    subtract_points_from_user,
    get_user_by_discord_id,
    link_accounts,
    db_manager,
    sync_manager
)

# ============================================================
# EJEMPLOS DE USO EN DISCORD BOT
# ============================================================

def example_new_discord_user(discord_id, username, avatar_url):
    """
    Cuando un nuevo usuario de Discord se une
    
    ✓ Se crea en caché JSON
    ✓ Se sincroniza automáticamente a BD
    ✓ El cliente local lo recibe al sincronizar
    """
    print(f"👤 Nuevo usuario Discord: {username}")
    cache_discord_user(discord_id, username, avatar_url)
    print(f"✓ {username} sincronizado a BD automáticamente")


def example_give_points(discord_id, points):
    """
    Cuando das puntos a un usuario
    
    ✓ Se actualiza en caché JSON
    ✓ Se envía a BD automáticamente
    ✓ Las transacciones se registran
    """
    user = add_points_to_user(discord_id, points)
    if user:
        print(f"✓ {user['name']} recibió {points} puntos (Total: {user['puntos']})")
    else:
        print(f"❌ Usuario no encontrado")


def example_check_bd_status():
    """
    Verificar si la BD está disponible
    """
    if db_manager and db_manager.is_connected:
        print("✓ BD CONECTADA - Los cambios se sincronizan en tiempo real")
    else:
        print("⚠ BD NO DISPONIBLE - Los cambios se guardan en caché y se sincronizarán después")


def example_force_sync():
    """
    Si necesitas forzar la sincronización en VPS
    
    (Normalmente no es necesario, pero útil para testing)
    """
    if sync_manager:
        status = sync_manager.get_sync_status()
        print("📊 Estado de sincronización:")
        print(f"   BD conectada: {status['db_connected']}")
        print(f"   Usuarios en caché: {status['cache_users']}")


# ============================================================
# INTEGRACIÓN CON DISCORD.PY
# ============================================================

"""
Ejemplo de cómo usar en un comando de Discord:

import discord
from discord.ext import commands

@bot.command(name='dar')
async def give_points(ctx, points: int):
    '''Comando: !dar 100 - da puntos al usuario'''
    
    discord_id = ctx.author.id
    username = ctx.author.name
    
    # Crear usuario si no existe
    from usermanager import cache_discord_user
    cache_discord_user(discord_id, username, str(ctx.author.avatar.url))
    
    # Dar puntos (automáticamente sincronizado)
    from usermanager import add_points_to_user
    user = add_points_to_user(discord_id, points)
    
    if user:
        await ctx.send(f"✓ {user['name']} recibió {points} puntos")
        # Los puntos aparecerán en el cliente local automáticamente
    else:
        await ctx.send("❌ Error al dar puntos")


@bot.command(name='puntos')
async def check_points(ctx):
    '''Comando: !puntos - ver tus puntos'''
    
    from usermanager import get_user_by_discord_id, get_user_points
    
    discord_id = ctx.author.id
    user = get_user_by_discord_id(discord_id)
    
    if user:
        puntos = get_user_points(discord_id)
        await ctx.send(f"Tienes {puntos} puntos")
    else:
        await ctx.send("No tienes cuenta")


@bot.command(name='sincronizar')
@commands.is_owner()
async def sync_status(ctx):
    '''Comando admin: Ver estado de sincronización'''
    
    from usermanager import sync_manager
    
    if sync_manager:
        status = sync_manager.get_sync_status()
        await ctx.send(
            f"BD: {'✓ Conectada' if status['db_connected'] else '❌ Desconectada'}\n"
            f"Usuarios en caché: {status['cache_users']}"
        )
"""

# ============================================================
# CONFIGURACIÓN AUTOMÁTICA
# ============================================================

if __name__ == "__main__":
    print("═" * 60)
    print(" Sistema de Sincronización BD - Discord Bot")
    print("═" * 60)
    
    # 1. Verificar BD
    print("\n[1] Verificando conexión a BD...")
    example_check_bd_status()
    
    # 2. Ver estado
    print("\n[2] Estado de sincronización...")
    example_force_sync()
    
    # 3. Explicar el sistema
    print("\n[3] Cómo funciona:")
    print("   ✓ Cada cambio en VPS se sincroniza automáticamente")
    print("   ✓ Si la BD cae, los cambios se guardan localmente")
    print("   ✓ El cliente local ve todos los cambios en tiempo real")
    print("\n[✓] Sistema listo para usar en tu Discord Bot")
