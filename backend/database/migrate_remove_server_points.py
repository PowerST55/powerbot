"""
Migración: Eliminar tabla server_points
==========================================

Este script elimina completamente la tabla server_points de la base de datos.
Solo quedan los puntos globales en la tabla 'wallets'.

Fecha: 2026-02-13
Razón: Bot trabajará en un solo servidor, no se necesita separación por servidor
"""
import sqlite3
from pathlib import Path

# Ruta a la base de datos
DB_PATH = Path(__file__).parent.parent / "data" / "powerbot.db"


def migrate():
    """Ejecuta la migración para eliminar server_points"""
    print("🔧 Iniciando migración: Eliminar server_points")
    print(f"📁 Base de datos: {DB_PATH}")
    
    if not DB_PATH.exists():
        print("❌ No se encontró la base de datos")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Verificar si la tabla existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='server_points'
        """)
        
        if not cursor.fetchone():
            print("✅ La tabla 'server_points' no existe, no hay nada que hacer")
            return
        
        # 2. Contar registros antes de eliminar
        cursor.execute("SELECT COUNT(*) as count FROM server_points")
        count = cursor.fetchone()["count"]
        print(f"📊 Registros en server_points: {count}")
        
        # 3. Eliminar la tabla
        print("🗑️  Eliminando tabla server_points...")
        cursor.execute("DROP TABLE IF EXISTS server_points")
        
        # 4. Commit cambios
        conn.commit()
        print("✅ Tabla 'server_points' eliminada exitosamente")
        print("💡 Ahora solo se usan puntos globales (tabla 'wallets')")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        conn.rollback()
    finally:
        conn.close()


def verify():
    """Verifica que la migración se aplicó correctamente"""
    print("\n🔍 Verificando migración...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verificar que server_points no existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='server_points'
        """)
        
        if cursor.fetchone():
            print("❌ ERROR: La tabla 'server_points' todavía existe")
        else:
            print("✅ Verificado: Tabla 'server_points' eliminada")
        
        # Verificar que wallets existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='wallets'
        """)
        
        if cursor.fetchone():
            print("✅ Verificado: Tabla 'wallets' (puntos globales) existe")
        else:
            print("❌ ERROR: La tabla 'wallets' no existe")
            
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("MIGRACIÓN: Eliminar server_points")
    print("=" * 60)
    
    migrate()
    verify()
    
    print("\n" + "=" * 60)
    print("✅ Migración completada")
    print("=" * 60)
    print("\n💡 Consejos:")
    print("   - Los puntos globales siguen en 'wallets'")
    print("   - El sistema es ahora más simple")
    print("   - Reinicia el bot para aplicar los cambios")
