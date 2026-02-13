"""
Comandos de administración para PowerBot Discord.
Solo ejecutables por administradores.
"""
import discord
from discord import app_commands
from discord.ext import commands
from backend.services.discord_bot.config import get_channels_config, get_economy_config
from backend.services.discord_bot.config.roles import get_roles_config
from backend.services.discord_bot.bot_logging import log_info, log_success


def setup_admin_commands(bot: commands.Bot):
    """Registra comandos de administración"""
    
    @bot.tree.command(name="setprefix", description="Cambia el prefix del bot (solo admin)")
    @app_commands.describe(prefix="El nuevo prefix (ej: !, ?, >)")
    async def setprefix(interaction: discord.Interaction, prefix: str):
        """Cambia el prefix del bot en este servidor - Solo administradores"""
        
        # Verificar permisos de administración
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Acceso denegado",
                description="Solo los administradores pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Si tiene permisos, ejecutar comando
        if len(prefix) > 3:
            embed = discord.Embed(
                title="❌ Error",
                description="El prefix debe tener máximo 3 caracteres.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="✅ Prefix actualizado",
            description=f"Nuevo prefix: `{prefix}`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Grupo de comandos /set
    set_group = app_commands.Group(name="set", description="Configuración del servidor")
    
    @set_group.command(name="channel", description="Configura canales del servidor")
    @app_commands.describe(
        tipo="Tipo de canal a configurar",
        channel="Canal a asignar"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Confesiones", value="confession"),
        app_commands.Choice(name="Logs", value="logs"),
    ])
    async def set_channel(interaction: discord.Interaction, tipo: app_commands.Choice[str], channel: discord.TextChannel):
        """Configura canales del servidor - Solo administradores"""
        
        # Verificar permisos
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Acceso denegado",
                description="Solo los administradores pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Obtener configuración de canales
            channels_config = get_channels_config(interaction.guild.id)
            
            # Mapear tipos a nombres de configuración
            channel_map = {
                "confession": "confession_channel",
                "logs": "logs_channel",
            }
            
            config_name = channel_map.get(tipo.value)
            if not config_name:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Tipo de canal no reconocido.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Guardar el canal
            channels_config.set_channel(config_name, channel.id)
            
            # Mapear tipos a nombres amigables
            tipo_nombre = {
                "confession": "Confesiones",
                "logs": "Logs",
            }
            
            embed = discord.Embed(
                title="✅ Canal configurado",
                description=f"Canal de {tipo_nombre.get(tipo.value)} establecido",
                color=discord.Color.green()
            )
            embed.add_field(name="Tipo", value=f"`{tipo_nombre.get(tipo.value)}`", inline=True)
            embed.add_field(name="Canal", value=f"{channel.mention}", inline=True)
            embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
            embed.set_footer(text="Guardado en data/discord_bot/")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Log de la configuración (solo si no es el canal de logs mismo)
            if tipo.value != "logs":
                await log_success(
                    bot,
                    interaction.guild.id,
                    "Canal configurado",
                    f"Canal de {tipo_nombre.get(tipo.value)} establecido por {interaction.user.mention}",
                    fields={
                        "Tipo": tipo_nombre.get(tipo.value),
                        "Canal": channel.mention,
                        "Configurado por": interaction.user.display_name
                    }
                )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Error al configurar el canal: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @set_group.command(name="currency", description="Configura la moneda del servidor")
    @app_commands.describe(
        nombre="Nombre de la moneda (máx 20 caracteres)",
        simbolo="Símbolo de la moneda (máx 5 caracteres)"
    )
    async def set_currency(interaction: discord.Interaction, nombre: str, simbolo: str):
        """Configura la moneda del servidor - Solo administradores"""
        
        # Verificar permisos
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Acceso denegado",
                description="Solo los administradores pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Validar longitud del nombre
        if len(nombre) > 20:
            embed = discord.Embed(
                title="❌ Error",
                description="El nombre de la moneda no puede exceder 20 caracteres.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Validar símbolo
        if len(simbolo) > 5:
            embed = discord.Embed(
                title="❌ Error",
                description="El símbolo no puede exceder 5 caracteres.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Obtener configuración de economía y guardar
            economy_config = get_economy_config(interaction.guild.id)
            economy_config.set_currency(nombre, simbolo)
            
            embed = discord.Embed(
                title="✅ Moneda actualizada",
                description=f"Nueva moneda configurada",
                color=discord.Color.green()
            )
            embed.add_field(name="Nombre", value=f"`{nombre}`", inline=True)
            embed.add_field(name="Símbolo", value=f"`{simbolo}`", inline=True)
            embed.set_footer(text="Guardado en data/discord_bot/")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Error al actualizar la moneda: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @set_group.command(name="points", description="Configura cantidad e intervalo de puntos")
    @app_commands.describe(
        amount="Cantidad de puntos que da el bot",
        interval="Intervalo en segundos (ej: 300 = 5 minutos)"
    )
    async def set_points(interaction: discord.Interaction, amount: int, interval: int):
        """Configura puntos y su intervalo - Solo administradores"""
        
        # Verificar permisos
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Acceso denegado",
                description="Solo los administradores pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Validar values
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Error",
                description="La cantidad de puntos debe ser mayor a 0.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if interval <= 0:
            embed = discord.Embed(
                title="❌ Error",
                description="El intervalo debe ser mayor a 0 segundos.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Obtener configuración de economía y guardar
            economy_config = get_economy_config(interaction.guild.id)
            economy_config.set_points(amount, interval)
            
            # Convertir segundos a minutos para mostrar
            minutes = interval / 60
            
            embed = discord.Embed(
                title="✅ Configuración de puntos actualizada",
                description=f"Puntos configurados correctamente",
                color=discord.Color.green()
            )
            embed.add_field(name="Cantidad de puntos", value=f"`{amount}` puntos", inline=True)
            embed.add_field(name="Intervalo", value=f"`{interval}` segundos (`{minutes:.1f}` min)", inline=True)
            embed.set_footer(text="Guardado en data/discord_bot/")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Error al configurar puntos: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @set_group.command(name="role", description="Configura roles del servidor")
    @app_commands.describe(
        tipo="Tipo de rol a configurar",
        rol="Rol a asignar"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="DJ", value="dj"),
        app_commands.Choice(name="MOD", value="mod"),
    ])
    async def set_role(interaction: discord.Interaction, tipo: app_commands.Choice[str], rol: discord.Role):
        """Configura roles del servidor - Solo administradores"""
        
        # Verificar permisos
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Acceso denegado",
                description="Solo los administradores pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Obtener configuración de roles
            roles_config = get_roles_config(interaction.guild.id)
            
            # Mapear tipos a nombres amigables
            tipo_nombre = {
                "dj": "DJ",
                "mod": "MOD",
            }
            
            # Manejo diferenciado para DJ (único) y MOD (múltiple)
            if tipo.value == "dj":
                # DJ solo puede tener un rol
                roles_config.set_role("dj", rol.id)
                
                embed = discord.Embed(
                    title="✅ Rol DJ configurado",
                    description=f"Rol DJ establecido",
                    color=discord.Color.green()
                )
                embed.add_field(name="Tipo", value=f"`DJ`", inline=True)
                embed.add_field(name="Rol", value=f"{rol.mention}", inline=True)
                embed.add_field(name="ID", value=f"`{rol.id}`", inline=True)
                embed.set_footer(text="Guardado en data/discord_bot/")
                
            else:  # MOD
                # MOD puede tener múltiples roles
                is_new = roles_config.add_mod_role(rol.id)
                
                if is_new:
                    embed = discord.Embed(
                        title="✅ Rol MOD agregado",
                        description=f"Rol MOD agregado a la lista",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Tipo", value=f"`MOD`", inline=True)
                    embed.add_field(name="Rol agregado", value=f"{rol.mention}", inline=True)
                    embed.add_field(name="ID", value=f"`{rol.id}`", inline=True)
                else:
                    embed = discord.Embed(
                        title="ℹ️ Rol MOD ya existe",
                        description=f"Este rol ya está configurado como MOD",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Rol", value=f"{rol.mention}", inline=True)
                    embed.add_field(name="ID", value=f"`{rol.id}`", inline=True)
                
                # Mostrar todos los roles MOD
                mod_roles = roles_config.get_mod_roles()
                if mod_roles:
                    roles_list = "\n".join([f"• <@&{role_id}>" for role_id in mod_roles])
                    embed.add_field(name="Roles MOD totales", value=roles_list, inline=False)
                
                embed.set_footer(text="Guardado en data/discord_bot/")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Error al configurar el rol: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    bot.tree.add_command(set_group)
    
    @bot.tree.command(name="clean", description="Limpia configuración guardada")
    @app_commands.describe(tipo="Qué configuración deseas limpiar")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Roles", value="roles"),
        app_commands.Choice(name="Canales", value="channels"),
        app_commands.Choice(name="Economía", value="economy"),
    ])
    async def clean(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
        """Limpia configuración guardada - Solo administradores"""
        
        # Verificar permisos
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Acceso denegado",
                description="Solo los administradores pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            tipo_valor = tipo.value
            tipo_nombre = {
                "roles": "Roles",
                "channels": "Canales",
                "economy": "Economía",
            }
            
            if tipo_valor == "roles":
                # Limpiar roles
                roles_config = get_roles_config(interaction.guild.id)
                roles_config._config = roles_config._defaults.copy()
                roles_config._save()
                
                embed = discord.Embed(
                    title="✅ Roles limpiados",
                    description="Configuración de roles reiniciada a valores por defecto",
                    color=discord.Color.green()
                )
                
            elif tipo_valor == "channels":
                # Limpiar canales
                channels_config = get_channels_config(interaction.guild.id)
                channels_config._config = channels_config._defaults.copy()
                channels_config._save()
                
                embed = discord.Embed(
                    title="✅ Canales limpiados",
                    description="Configuración de canales reiniciada a valores por defecto",
                    color=discord.Color.green()
                )
                
            elif tipo_valor == "economy":
                # Limpiar economía
                economy_config = get_economy_config(interaction.guild.id)
                economy_config._config = economy_config._defaults.copy()
                economy_config._save()
                
                embed = discord.Embed(
                    title="✅ Economía limpiada",
                    description="Configuración de economía reiniciada a valores por defecto",
                    color=discord.Color.green()
                )
            
            embed.add_field(name="Tipo", value=f"`{tipo_nombre.get(tipo_valor)}`", inline=True)
            embed.set_footer(text="Puedes volver a configurar este apartado")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Error al limpiar configuración: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @bot.tree.command(
        name="say",
        description="Envía un mensaje como el bot (solo mods)"
    )
    @app_commands.describe(mensaje="El mensaje que enviará el bot")
    async def say(interaction: discord.Interaction, mensaje: str):
        """Envía un mensaje como el bot en el canal actual - Solo moderadores"""
        
        # Verificar permisos de moderación (admin o permisos de moderar miembros)
        if not (interaction.user.guild_permissions.administrator or 
                interaction.user.guild_permissions.moderate_members):
            embed = discord.Embed(
                title="❌ Acceso denegado",
                description="Solo los moderadores pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Responder al usuario de forma ephemeral
            confirm_embed = discord.Embed(
                title="✅ Mensaje enviado",
                description=f"Tu mensaje ha sido publicado en {interaction.channel.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
            
            # Enviar el mensaje en el canal
            await interaction.channel.send(mensaje)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Error de permisos",
                description="El bot no tiene permisos para enviar mensajes en este canal.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Ocurrió un error: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    print("   ✓ Comandos de administración registrados")
