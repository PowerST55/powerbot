"""
Comandos sociales para PowerBot Discord.
Comandos de confesiones, chats, etc.
"""
import discord
from discord import app_commands
from discord.ext import commands
from backend.services.discord_bot.config import get_channels_config


def setup_social_commands(bot: commands.Bot):
    """Registra comandos sociales"""
    
    @bot.tree.command(
        name="confesar",
        description="Envía una confesión anónima al canal de confesiones"
    )
    @app_commands.describe(message="Tu confesión (máximo 2000 caracteres)")
    async def confesar(interaction: discord.Interaction, message: str):
        """Envía una confesión anónima al canal de confesiones"""
        
        # Obtener configuración de canales
        channels_config = get_channels_config(interaction.guild.id)
        confession_channel_id = channels_config.get_channel("confession_channel")
        
        # Verificar si el canal está configurado
        if not confession_channel_id:
            embed = discord.Embed(
                title="❌ Canal no configurado",
                description="El administrador aún no ha configurado el canal de confesiones.\n"
                            "Usa `/set confession_channel` para establecerlo.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Obtener el canal
        confession_channel = bot.get_channel(confession_channel_id)
        
        if not confession_channel:
            embed = discord.Embed(
                title="❌ Error",
                description="El canal de confesiones no existe o no es accesible.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Validar longitud del mensaje
        if len(message) > 2000:
            embed = discord.Embed(
                title="❌ Mensaje muy largo",
                description="La confesión no puede exceder 2000 caracteres.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if len(message) < 1:
            embed = discord.Embed(
                title="❌ Mensaje vacío",
                description="La confesión no puede estar vacía.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Crear embed de confesión anónima
        from datetime import datetime
        
        embed = discord.Embed(
            title="🤐 Confesión Anónima",
            description=message,
            color=discord.Color.purple()
        )
        
        # Agregar timestamp en el footer
        now = datetime.now()
        timestamp = now.strftime("%d/%m/%Y %H:%M")
        embed.set_footer(text=f"Confesión anónima • {timestamp}")
        
        try:
            # Enviar al canal de confesiones
            await confession_channel.send(embed=embed)
            
            # Confirmar al usuario (ephemeral)
            confirm_embed = discord.Embed(
                title="✅ Confesión enviada",
                description="Tu confesión ha sido enviada de forma anónima al canal de confesiones.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Error de permisos",
                description="El bot no tiene permisos para enviar mensajes al canal de confesiones.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Ocurrió un error al enviar la confesión: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    print("   ✓ Comandos sociales registrados")
