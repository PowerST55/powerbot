"""
Sistema de Logging de Transacciones de Pews
Registra todas las transacciones (ganancias, pérdidas, transferencias, etc.)
"""
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

class TransactionLogger:
    """Logger para todas las transacciones de pews del sistema"""
    
    def __init__(self, data_dir: str = None):
        """Inicializa el logger de transacciones
        
        Args:
            data_dir: Directorio donde guardar los logs
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.transactions_file = os.path.join(self.data_dir, 'transactions_log.json')
        self.load_transactions()
    
    def load_transactions(self) -> List[Dict]:
        """Carga las transacciones desde el archivo JSON"""
        try:
            with open(self.transactions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    def save_transactions(self, transactions: List[Dict]):
        """Guarda las transacciones al archivo JSON"""
        with open(self.transactions_file, 'w', encoding='utf-8') as f:
            json.dump(transactions, f, indent=4, ensure_ascii=False)
    
    def _get_timestamp(self) -> str:
        """Obtiene el timestamp actual en formato ISO (sin microsegundos)"""
        tz = timezone(timedelta(hours=-5))  # Zona horaria UTC-5
        return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    
    def log_transaction(
        self,
        user_id: str,
        username: str,
        platform: str,  # 'youtube' o 'discord'
        transaction_type: str,  # 'gamble_win', 'gamble_loss', 'slot_win', 'slot_loss', 'transfer_send', 'transfer_receive', 'reward', 'punishment', 'store_purchase', 'account_link', 'apsall', 'code_redeem', 'tts'
        amount: float,
        balance_after: float
    ):
        """Registra una transacción
        
        Args:
            user_id: ID del usuario (YouTube o Discord)
            username: Nombre del usuario
            platform: 'youtube' o 'discord'
            transaction_type: Tipo de transacción
            amount: Cantidad de pews (puede ser negativa)
            balance_after: Saldo después de la transacción
        """
        # Ignorar log de message_gain
        if transaction_type == 'message_gain':
            return
        
        transactions = self.load_transactions()
        
        transaction = {
            'timestamp': self._get_timestamp(),
            'user_id': str(user_id),
            'username': username,
            'platform': platform,
            'type': transaction_type,
            'amount': round(amount, 2),
            'balance_after': round(balance_after, 2)
        }
        
        transactions.append(transaction)
        self.save_transactions(transactions)
        
        # Imprimir en consola en formato legible
        self._print_transaction(transaction)
    
    def _print_transaction(self, transaction: Dict):
        """Imprime la transacción en un formato legible"""
        user_id = transaction['user_id']
        username = transaction['username']
        platform = transaction['platform'].upper()
        amount = transaction['amount']
        balance_after = transaction['balance_after']
        tipo = transaction['type']
        
        # Determinar símbolo según ganancia/pérdida
        if amount > 0:
            symbol = "✅ +"
        elif amount < 0:
            symbol = "❌"
        else:
            symbol = "🔄 ±"
        
        # Formatear el log
        log_msg = f"[{platform}] ID: {user_id} | @{username} | {tipo} {symbol}{abs(amount):.1f}₱ | Saldo final: {balance_after:.1f}₱"
        print(log_msg)
    
    def get_user_transactions(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Obtiene todas las transacciones de un usuario
        
        Args:
            user_id: ID del usuario
            limit: Límite de transacciones a retornar (últimas N)
            
        Returns:
            Lista de transacciones del usuario
        """
        transactions = self.load_transactions()
        user_transactions = [t for t in transactions if str(t['user_id']) == str(user_id)]
        
        if limit:
            return user_transactions[-limit:]
        return user_transactions
    
    def get_transactions_by_type(self, transaction_type: str, limit: Optional[int] = None) -> List[Dict]:
        """Obtiene transacciones por tipo
        
        Args:
            transaction_type: Tipo de transacción
            limit: Límite de transacciones
            
        Returns:
            Lista de transacciones del tipo especificado
        """
        transactions = self.load_transactions()
        filtered = [t for t in transactions if t['type'] == transaction_type]
        
        if limit:
            return filtered[-limit:]
        return filtered
    
    def get_transactions_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Obtiene transacciones dentro de un rango de fechas
        
        Args:
            start_date: Fecha de inicio (formato ISO)
            end_date: Fecha de fin (formato ISO)
            
        Returns:
            Lista de transacciones en el rango
        """
        transactions = self.load_transactions()
        filtered = [
            t for t in transactions
            if start_date <= t['timestamp'] <= end_date
        ]
        return filtered
    
    def get_user_summary(self, user_id: str) -> Dict:
        """Obtiene un resumen de transacciones de un usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Dict con estadísticas del usuario
        """
        transactions = self.get_user_transactions(user_id)
        
        if not transactions:
            return {
                'user_id': user_id,
                'total_transactions': 0,
                'total_gained': 0.0,
                'total_lost': 0.0,
                'net_change': 0.0,
                'current_balance': 0.0
            }
        
        total_gained = sum(t['amount'] for t in transactions if t['amount'] > 0)
        total_lost = abs(sum(t['amount'] for t in transactions if t['amount'] < 0))
        
        last_transaction = transactions[-1]
        current_balance = last_transaction['balance_after']
        
        return {
            'user_id': user_id,
            'username': transactions[-1]['username'],
            'total_transactions': len(transactions),
            'total_gained': round(total_gained, 2),
            'total_lost': round(total_lost, 2),
            'net_change': round(total_gained - total_lost, 2),
            'current_balance': current_balance,
            'first_transaction': transactions[0]['timestamp'],
            'last_transaction': transactions[-1]['timestamp']
        }
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Obtiene un leaderboard de usuarios por ganancias netas
        
        Args:
            limit: Cantidad de usuarios a retornar
            
        Returns:
            Lista de usuarios ordenados por ganancias netas
        """
        transactions = self.load_transactions()
        
        # Agrupar por usuario
        user_data = {}
        for t in transactions:
            user_id = t['user_id']
            if user_id not in user_data:
                user_data[user_id] = {
                    'username': t['username'],
                    'net_change': 0.0,
                    'transactions': 0,
                    'balance': t['balance_after']
                }
            user_data[user_id]['net_change'] += t['amount']
            user_data[user_id]['transactions'] += 1
            user_data[user_id]['balance'] = t['balance_after']
        
        # Ordenar por ganancias netas
        leaderboard = sorted(
            user_data.values(),
            key=lambda x: x['net_change'],
            reverse=True
        )
        
        return leaderboard[:limit]
