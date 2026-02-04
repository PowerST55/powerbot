"""
Sistema de apuestas (Gamble y Tragamonedas) - Lógica modular
"""

import random
import json
import os
from typing import Tuple, Dict, List


def calculate_gamble_result(bet_amount: float) -> Tuple[int, float, float, str]:
    """
    Calcula el resultado de una apuesta basada en un número aleatorio.
    Retorna ganancia con dos decimales para permitir premios fraccionarios.
    
    Args:
        bet_amount: Cantidad apostada
        
    Returns:
        Tuple[roll, ganancia_neta, multiplicador, rango]: 
            - roll: número aleatorio (1-100)
            - ganancia_neta: cantidad neta ganada/perdida (puede ser negativa, 2 decimales)
            - multiplicador: porcentaje de retorno (0.0 a 4.0)
            - rango: descripción del rango de premio
    """
    # Generar número aleatorio del 1 al 100
    roll = random.randint(1, 100)
    
    # Determinar multiplicador y rango según la tabla de premios
    if roll <= 25:  # 0-25
        multiplicador = 0.0
        rango = "0-25: Perdiste todo 💀"
    elif roll <= 40:  # 26-40
        multiplicador = 0.5
        rango = "26-40: Recuperaste el 50% 😰"
    elif roll <= 55:  # 41-55
        multiplicador = 1.0
        rango = "41-55: Reembolso completo 😐"
    elif roll <= 70:  # 56-70
        multiplicador = 1.3
        rango = "56-70: Ganaste 30% extra 😊"
    elif roll <= 85:  # 71-85
        multiplicador = 1.6
        rango = "71-85: Ganaste 60% extra! 🎉"
    elif roll <= 95:  # 86-95
        multiplicador = 2.0
        rango = "86-95: ¡Duplicaste tu apuesta! 🤑"
    elif roll <= 99:  # 96-99
        multiplicador = 2.5
        rango = "96-99: ¡¡PREMIO GRANDE!! 💰💰"
    else:  # 100
        multiplicador = 4.0
        rango = "100: ¡¡¡JACKPOT!!! 🎰🎰🎰"
    
    # Calcular payout total y ganancia neta
    payout_total = round(bet_amount * multiplicador, 2)
    ganancia_neta = round(payout_total - bet_amount, 2)
    
    return roll, ganancia_neta, multiplicador, rango


def validate_gamble(user_points: float, bet_amount: float, max_bet: float = None) -> Tuple[bool, str]:
    """
    Valida si un usuario puede realizar una apuesta.
    
    Args:
        user_points: Puntos actuales del usuario
        bet_amount: Cantidad que desea apostar
        max_bet: Límite máximo de apuesta (opcional)
        
    Returns:
        Tuple[es_valido, mensaje_error]: 
            - es_valido: True si puede apostar, False si no
            - mensaje_error: Mensaje descriptivo del error (vacío si es válido)
    """
    if bet_amount <= 0:
        return False, "❌ Debes apostar al menos 1 pew."
    
    if max_bet is not None and bet_amount > max_bet:
        return False, f"❌ El límite máximo de apuesta es **{max_bet:,}₱**. Intentaste apostar **{bet_amount:,.2f}₱**."
    
    if user_points < bet_amount:
        return False, f"❌ No tienes suficientes pews. Tienes: **{user_points:,.2f}** pews."
    
    return True, ""


def get_gamble_summary(username: str, bet_amount: float, roll: int, ganancia_neta: float, 
                       multiplicador: float, rango: str, puntos_finales: float) -> Dict:
    """
    Genera un resumen formateado del resultado del gamble.
    
    Args:
        username: Nombre del usuario
        bet_amount: Cantidad apostada
        roll: Número obtenido
        ganancia_neta: Ganancia neta (puede ser negativa)
        multiplicador: Multiplicador aplicado
        rango: Descripción del rango
        puntos_finales: Puntos totales después del gamble
        
    Returns:
        Dict con información del resultado formateada
    """
    # Determinar emoji según resultado
    if ganancia_neta > 0:
        resultado_emoji = "✅"
        color = "verde"
    elif ganancia_neta == 0:
        resultado_emoji = "🔄"
        color = "amarillo"
    else:
        resultado_emoji = "❌"
        color = "rojo"
    
    # Formatear ganancia
    if ganancia_neta > 0:
        ganancia_texto = f"+{ganancia_neta:,.2f}"
    elif ganancia_neta == 0:
        ganancia_texto = "±0"
    else:
        ganancia_texto = f"{ganancia_neta:,.2f}"
    
    return {
        "username": username,
        "bet_amount": bet_amount,
        "roll": roll,
        "ganancia_neta": ganancia_neta,
        "ganancia_texto": ganancia_texto,
        "multiplicador": multiplicador,
        "rango": rango,
        "puntos_finales": puntos_finales,
        "resultado_emoji": resultado_emoji,
        "color": color
    }


# ==================== MÁQUINA TRAGAMONEDAS ====================

# Tabla de pagos y probabilidades para la máquina tragamonedas
SLOT_PAYOUTS = {
    "🍒": {"x3": 2.5, "x2": 1.05, "prob": 0.35},
    "🍍": {"x3": 4.0, "x2": 1.1, "prob": 0.25},
    "🍎": {"x3": 6.0, "x2": 1.2, "prob": 0.15},
    "🍇": {"x3": 10.0, "x2": 1.4, "prob": 0.08},
    "🥭": {"x3": 20.0, "x2": 1.8, "prob": 0.04},
    "🔔": {"x3": 30.0, "x2": 2.2, "prob": 0.02},
    "💎": {"x3": 999.0, "x2": 99.0, "prob": 0.01},
}

SLOT_SYMBOLS = list(SLOT_PAYOUTS.keys())
SLOT_WEIGHTS = [SLOT_PAYOUTS[s]["prob"] for s in SLOT_SYMBOLS]

# Archivo para almacenar multiplicadores de suerte
LUCK_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'slot_luck.json'))


def load_luck_multipliers() -> Dict[str, float]:
    """Carga los multiplicadores de suerte de todos los usuarios."""
    try:
        with open(LUCK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_luck_multipliers(luck_data: Dict[str, float]):
    """Guarda los multiplicadores de suerte."""
    os.makedirs(os.path.dirname(LUCK_FILE), exist_ok=True)
    with open(LUCK_FILE, 'w', encoding='utf-8') as f:
        json.dump(luck_data, f, indent=4, ensure_ascii=False)


def get_user_luck_multiplier(user_id: str) -> float:
    """Obtiene el multiplicador de suerte actual del usuario."""
    luck_data = load_luck_multipliers()
    return float(luck_data.get(str(user_id), 1.0))


def update_user_luck_multiplier(user_id: str, multiplier: float):
    """Actualiza el multiplicador de suerte del usuario."""
    luck_data = load_luck_multipliers()
    luck_data[str(user_id)] = round(max(1.0, multiplier), 2)  # Mínimo 1.0
    save_luck_multipliers(luck_data)


def reset_user_luck_multiplier(user_id: str):
    """Resetea el multiplicador de suerte del usuario a 1.0."""
    update_user_luck_multiplier(user_id, 1.0)


def increment_user_luck_multiplier(user_id: str, increment: float = 0.1):
    """Incrementa el multiplicador de suerte del usuario (cuando pierde)."""
    current = get_user_luck_multiplier(user_id)
    update_user_luck_multiplier(user_id, current + increment)


def spin_slots(bet_amount: int, user_id: str) -> Tuple[List[str], int, float, str, bool, float]:
    """
    Realiza una tirada de la máquina tragamonedas.
    
    Args:
        bet_amount: Cantidad apostada
        user_id: ID del usuario para aplicar su multiplicador de suerte
        
    Returns:
        Tuple[combo, ganancia_neta, multiplicador_aplicado, descripcion, es_ganancia, luck_multiplier]:
            - combo: Lista de 3 emojis resultado
            - ganancia_neta: Cantidad neta ganada/perdida
            - multiplicador_aplicado: Multiplicador usado (sin suerte)
            - descripcion: Descripción del resultado
            - es_ganancia: Si fue una ganancia
            - luck_multiplier: Multiplicador de suerte usado
    """
    # Obtener multiplicador de suerte del usuario
    luck_multiplier = get_user_luck_multiplier(user_id)
    
    # Primero determinar el tipo de resultado (70% pérdida, 20% X2, 10% X3)
    result_type = random.choices(
        ['loss', 'x2', 'x3'],
        weights=[0.70, 0.20, 0.10],
        k=1
    )[0]
    
    # Normalizar probabilidades relativas para seleccionar símbolo
    prob_sum = sum(SLOT_PAYOUTS[s]["prob"] for s in SLOT_SYMBOLS)
    relative_weights = [SLOT_PAYOUTS[s]["prob"] / prob_sum for s in SLOT_SYMBOLS]
    
    if result_type == 'loss':
        # Sin premio: 3 símbolos diferentes (asegurar que NO haya dos iguales)
        combo = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        while combo[0] == combo[1] or combo[1] == combo[2] or combo[0] == combo[2]:
            combo = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        
        ganancia_neta = -bet_amount
        return combo, ganancia_neta, 0.0, "Sin premio", False, luck_multiplier
    
    elif result_type == 'x2':
        # Premio X2: 2 símbolos iguales
        symbol = random.choices(SLOT_SYMBOLS, weights=relative_weights, k=1)[0]
        combo = [symbol, symbol, random.choice(SLOT_SYMBOLS)]
        # Mezclar para que no siempre estén juntos
        while combo[2] == symbol:
            combo[2] = random.choice(SLOT_SYMBOLS)
        random.shuffle(combo)
        
        multiplicador = SLOT_PAYOUTS[symbol]["x2"]
        payout = int(bet_amount * multiplicador * luck_multiplier)
        ganancia_neta = payout - bet_amount
        
        return combo, ganancia_neta, multiplicador, f"{symbol} X2", True, luck_multiplier
    
    else:  # x3
        # Jackpot: 3 símbolos iguales
        symbol = random.choices(SLOT_SYMBOLS, weights=relative_weights, k=1)[0]
        combo = [symbol, symbol, symbol]
        
        multiplicador = SLOT_PAYOUTS[symbol]["x3"]
        payout = int(bet_amount * multiplicador * luck_multiplier)
        ganancia_neta = payout - bet_amount
        
        return combo, ganancia_neta, multiplicador, f"{symbol} X3", True, luck_multiplier


def get_slot_summary(username: str, bet_amount: int, combo: List[str], ganancia_neta: int,
                     multiplicador: float, descripcion: str, es_ganancia: bool, 
                     luck_multiplier: float, puntos_finales: int) -> Dict:
    """
    Genera un resumen formateado del resultado de la tragamonedas.
    
    Args:
        username: Nombre del usuario
        bet_amount: Cantidad apostada
        combo: Lista de 3 emojis del resultado
        ganancia_neta: Ganancia neta
        multiplicador: Multiplicador aplicado
        descripcion: Descripción del resultado
        es_ganancia: Si fue ganancia
        luck_multiplier: Multiplicador de suerte usado
        puntos_finales: Puntos totales después
        
    Returns:
        Dict con información del resultado formateada
    """
    # Determinar tipo de resultado (X2, X3, o Pérdida)
    if not es_ganancia:
        tipo_resultado = "loss"
        resultado_emoji = "🎰"
        color = "rojo"
    elif "X2" in descripcion:
        tipo_resultado = "x2"
        resultado_emoji = "🎰"
        color = "amarillo"
    else:  # X3
        tipo_resultado = "x3"
        resultado_emoji = "🎰"
        color = "verde"
    
    # Formatear ganancia/pérdida dinámicamente
    if ganancia_neta > 0:
        ganancia_perdida_label = "Ganancia"
        ganancia_perdida_texto = f"+{ganancia_neta:,}"
    elif ganancia_neta == 0:
        ganancia_perdida_label = "Balance"
        ganancia_perdida_texto = "±0"
    else:
        ganancia_perdida_label = "Pérdida"
        ganancia_perdida_texto = f"{ganancia_neta:,}"
    
    # Formatear combo
    combo_display = " ".join(combo)
    
    # Determinar payout total
    payout_total = bet_amount + ganancia_neta
    
    return {
        "username": username,
        "bet_amount": bet_amount,
        "combo": combo,
        "combo_display": combo_display,
        "ganancia_neta": ganancia_neta,
        "ganancia_perdida_label": ganancia_perdida_label,
        "ganancia_perdida_texto": ganancia_perdida_texto,
        "multiplicador": multiplicador,
        "descripcion": descripcion,
        "es_ganancia": es_ganancia,
        "puntos_finales": puntos_finales,
        "resultado_emoji": resultado_emoji,
        "color": color,
        "tipo_resultado": tipo_resultado,
        "luck_multiplier": luck_multiplier,
        "payout_total": payout_total
    }


# ==================== PIEDRA PAPEL TIJERAS ====================

def validate_ppt_game(player1_points: int, player2_points: int, bet_amount: int) -> Tuple[bool, str]:
    """
    Valida que ambos jugadores tengan puntos suficientes para jugar.
    
    Args:
        player1_points: Puntos del jugador 1
        player2_points: Puntos del jugador 2
        bet_amount: Cantidad apostada por cada jugador
        
    Returns:
        Tuple[es_valido, mensaje_error]
    """
    if bet_amount <= 0:
        return False, "❌ La apuesta debe ser mayor a 0 pews."
    
    if player1_points < bet_amount:
        return False, "❌ No tienes suficientes pews para apostar."
    
    if player2_points < bet_amount:
        return False, f"❌ El rival no tiene suficientes pews. Necesita mínimo {bet_amount} pews."
    
    return True, ""


def determine_ppt_winner(player1_choice: str, player2_choice: str) -> Tuple[int, str]:
    """
    Determina el ganador de Piedra Papel Tijeras.
    
    Args:
        player1_choice: Opción del jugador 1 (piedra, papel, tijeras)
        player2_choice: Opción del jugador 2 (piedra, papel, tijeras)
        
    Returns:
        Tuple[ganador, descripcion]:
            - ganador: 1 si gana player1, 2 si gana player2, 0 si es empate
            - descripcion: Descripción del resultado
    """
    player1_choice = player1_choice.lower()
    player2_choice = player2_choice.lower()
    
    # Empate
    if player1_choice == player2_choice:
        return 0, f"¡Empate! Ambos eligieron {player1_choice}. Los puntos se devuelven."
    
    # Piedra gana a Tijeras
    if player1_choice == "piedra" and player2_choice == "tijeras":
        return 1, "🪨 Piedra aplasta Tijeras."
    if player2_choice == "piedra" and player1_choice == "tijeras":
        return 2, "🪨 Piedra aplasta Tijeras."
    
    # Papel gana a Piedra
    if player1_choice == "papel" and player2_choice == "piedra":
        return 1, "📄 Papel cubre Piedra."
    if player2_choice == "papel" and player1_choice == "piedra":
        return 2, "📄 Papel cubre Piedra."
    
    # Tijeras gana a Papel
    if player1_choice == "tijeras" and player2_choice == "papel":
        return 1, "✂️ Tijeras cortan Papel."
    if player2_choice == "tijeras" and player1_choice == "papel":
        return 2, "✂️ Tijeras cortan Papel."
    
    return 0, "Opción inválida"


def get_ppt_emoji(choice: str) -> str:
    """Retorna el emoji correspondiente a la opción."""
    choice = choice.lower()
    emojis = {
        "piedra": "🪨",
        "papel": "📄",
        "tijeras": "✂️"
    }
    return emojis.get(choice, "❓")