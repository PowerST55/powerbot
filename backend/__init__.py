"""
Backend module for PowerBot
"""

# Lazy imports - only import when needed
def __getattr__(name):
    if name == 'AccountLinkingManager':
        from .account_linking import AccountLinkingManager
        return AccountLinkingManager
    elif name == 'TransactionLogger':
        from .transaction_logger import TransactionLogger
        return TransactionLogger
    elif name == 'Database':
        from .database import Database
        return Database
    elif name == 'UserManager':
        from .usermanager import UserManager
        return UserManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'AccountLinkingManager',
    'TransactionLogger',
    'Database',
    'UserManager',
]
