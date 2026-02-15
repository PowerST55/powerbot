"""
Comandos de economía para usuarios normales.
Sistema de consulta de puntos y transacciones.
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime

from backend.managers.user_lookup_manager import find_user_by_discord_id, find_user_by_global_id
from backend.managers.economy_manager import get_user_balance_by_id
from backend.managers import get_or_create_discord_user
from backend.services.discord_bot.config.economy import get_economy_config


def setup_economy_commands(bot: commands.Bot):
	"""Registra comandos de economía para usuarios"""
	
	@bot.tree.command(name="pews", description="Consulta tus puntos o los de otro usuario")
	@app_commands.describe(
		target="Usuario de Discord a consultar (opcional)",
		user_id="ID Universal del usuario a consultar (opcional)"
	)
	async def pews(
		interaction: discord.Interaction,
		target: Optional[discord.User] = None,
		user_id: Optional[int] = None
	):
		"""
		Comando /pews con 3 modos de uso:
		
		1. /pews                    → Ver tus propios puntos
		2. /pews @usuario           → Ver puntos de otro usuario de Discord
		3. /pews user_id:2          → Ver puntos por ID universal
		"""
		await interaction.response.defer()
		
		# Obtener configuración de moneda del servidor
		economy_config = get_economy_config(interaction.guild.id)
		currency_name = economy_config.get_currency_name()
		currency_symbol = economy_config.get_currency_symbol()
		
		# CASO 1: Sin argumentos - consultar propios puntos
		if target is None and user_id is None:
			result = await _show_own_balance(
				bot,
				interaction,
				currency_name,
				currency_symbol
			)
			# Si es un error, enviar como ephemeral
			if result.title and "❌" in result.title:
				await interaction.followup.send(embed=result, ephemeral=True)
			else:
				await interaction.followup.send(embed=result)
			return
		
		# CASO 2: Con @usuario - consultar puntos de otro usuario Discord
		if target is not None:
			result = await _show_discord_user_balance(
				bot,
				interaction,
				target,
				currency_name,
				currency_symbol
			)
			# Si es un error, enviar como ephemeral
			if result.title and "❌" in result.title:
				await interaction.followup.send(embed=result, ephemeral=True)
			else:
				await interaction.followup.send(embed=result)
			return
		
		# CASO 3: Con ID universal - consultar por ID global
		if user_id is not None:
			result = await _show_global_id_balance(
				bot,
				interaction,
				user_id,
				currency_name,
				currency_symbol
			)
			# Si es un error, enviar como ephemeral
			if result.title and "❌" in result.title:
				await interaction.followup.send(embed=result, ephemeral=True)
			else:
				await interaction.followup.send(embed=result)
			return


async def _show_own_balance(
	bot: commands.Bot,
	interaction: discord.Interaction,
	currency_name: str,
	currency_symbol: str
) -> discord.Embed:
	"""Muestra el balance propio del usuario"""
	# Buscar usuario
	user_lookup = find_user_by_discord_id(str(interaction.user.id))
	
	# Si no existe, registrarlo automáticamente
	if not user_lookup:
		try:
			user, discord_profile, is_new = get_or_create_discord_user(
				discord_id=str(interaction.user.id),
				discord_username=interaction.user.name,
				avatar_url=str(interaction.user.display_avatar.url)
			)
			# Buscar de nuevo después de crear
			user_lookup = find_user_by_discord_id(str(interaction.user.id))
			if not user_lookup:
				return discord.Embed(
					title="❌ Error",
					description="No se pudo crear tu cuenta. Intenta nuevamente.",
					color=discord.Color.red()
				)
		except Exception as e:
			return discord.Embed(
				title="❌ Error",
				description=f"Error al registrarte: {str(e)}",
				color=discord.Color.red()
			)
	
	# Obtener balance
	balance = get_user_balance_by_id(user_lookup.user_id)
	
	if not balance or not balance["user_exists"]:
		return discord.Embed(
			title="❌ Error",
			description="No se pudo obtener tu balance.",
			color=discord.Color.red()
		)
	
	# Crear embed con balance
	embed = discord.Embed(
		title=f"💰 Balance de {interaction.user.display_name}",
		description=f"**{currency_name}:** {balance['global_points']:,} {currency_symbol}",
		color=discord.Color.gold()
	)
	
	# ID y fecha en el footer
	now = datetime.now().strftime("%d/%m/%Y %H:%M")
	embed.set_footer(text=f"User Id: {user_lookup.user_id} • Consultado {now}")
	
	return embed


async def _show_discord_user_balance(
	bot: commands.Bot,
	interaction: discord.Interaction,
	target: discord.User,
	currency_name: str,
	currency_symbol: str
) -> discord.Embed:
	"""Muestra el balance de un usuario de Discord"""
	# Buscar usuario
	user_lookup = find_user_by_discord_id(str(target.id))
	
	# Si no existe, registrarlo automáticamente
	if not user_lookup:
		try:
			user, discord_profile, is_new = get_or_create_discord_user(
				discord_id=str(target.id),
				discord_username=target.name,
				avatar_url=str(target.display_avatar.url)
			)
			# Buscar de nuevo después de crear
			user_lookup = find_user_by_discord_id(str(target.id))
			if not user_lookup:
				return discord.Embed(
					title="❌ Error",
					description=f"No se pudo crear la cuenta de {target.mention}. Intenta nuevamente.",
					color=discord.Color.red()
				)
		except Exception as e:
			return discord.Embed(
				title="❌ Error",
				description=f"Error al registrar a {target.mention}: {str(e)}",
				color=discord.Color.red()
			)
	
	# Obtener balance
	balance = get_user_balance_by_id(user_lookup.user_id)
	
	if not balance or not balance["user_exists"]:
		return discord.Embed(
			title="❌ Error",
			description=f"No se pudo obtener el balance de {target.mention}.",
			color=discord.Color.red()
		)
	
	# Crear embed
	embed = discord.Embed(
		title=f"💰 Balance de {target.display_name}",
		description=f"**{currency_name}:** {balance['global_points']:,} {currency_symbol}",
		color=discord.Color.blue()
	)
	
	# ID y fecha en el footer
	now = datetime.now().strftime("%d/%m/%Y %H:%M")
	embed.set_footer(text=f"User Id: {user_lookup.user_id} • Consultado {now}")
	
	return embed


async def _show_global_id_balance(
	bot: commands.Bot,
	interaction: discord.Interaction,
	global_user_id: int,
	currency_name: str,
	currency_symbol: str
) -> discord.Embed:
	"""Muestra el balance de un usuario por ID universal"""
	# Buscar usuario por ID global
	user_lookup = find_user_by_global_id(global_user_id)
	
	if not user_lookup:
		return discord.Embed(
			title="❌ Usuario no encontrado",
			description=f"No existe ningún usuario con ID universal `{global_user_id}`.",
			color=discord.Color.red()
		)
	
	# Obtener balance
	balance = get_user_balance_by_id(user_lookup.user_id)
	
	if not balance or not balance["user_exists"]:
		return discord.Embed(
			title="❌ Error",
			description=f"No se pudo obtener el balance del usuario ID `{global_user_id}`.",
			color=discord.Color.red()
		)
	
	# Crear embed
	embed = discord.Embed(
		title=f"💰 Balance de {user_lookup.display_name}",
		description=f"**{currency_name}:** {balance['global_points']:,} {currency_symbol}",
		color=discord.Color.purple()
	)
	
	# Mostrar plataformas conectadas
	platforms_text = []
	if user_lookup.has_discord:
		platforms_text.append(f"✅ Discord: <@{user_lookup.discord_profile.discord_id}>")
	if user_lookup.has_youtube:
		platforms_text.append(f"✅ YouTube: {user_lookup.youtube_profile.youtube_username}")
	
	if platforms_text:
		embed.add_field(
			name="🔗 Plataformas",
			value="\n".join(platforms_text),
			inline=False
		)
	
	# ID y fecha en el footer
	now = datetime.now().strftime("%d/%m/%Y %H:%M")
	embed.set_footer(text=f"User Id: {global_user_id} • Consultado {now}")
	
	# Thumbnail si tiene Discord
	if user_lookup.discord_profile:
		try:
			discord_user = await bot.fetch_user(int(user_lookup.discord_profile.discord_id))
			embed.set_thumbnail(url=discord_user.display_avatar.url)
		except:
			pass
	
	return embed
