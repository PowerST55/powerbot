"""
Migración: Eliminar columna 'points' obsoleta de discord_profile.

Los puntos ahora se gestionan en:
- wallets (puntos globales)
- server_points (puntos por servidor)

Esta columna en discord_profile está obsoleta y debe eliminarse.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "powerbot.db"


def migrate():
    """Elimina la columna 'points' de discord_profile."""
    print("🔄 Iniciando migración: Eliminar columna 'points' de discord_profile")
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # 1. Verificar si la columna existe
        cursor.execute("PRAGMA table_info(discord_profile)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "points" not in column_names:
            print("✅ La columna 'points' ya no existe. Migración no necesaria.")
            return
        
        print(f"   Columnas actuales: {', '.join(column_names)}")
        print("   ⚠️  Encontrada columna obsoleta 'points'")
        
        # 2. Crear tabla temporal sin la columna 'points'
        print("   📝 Creando tabla temporal...")
        cursor.execute("""
            CREATE TABLE discord_profile_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                discord_id TEXT NOT NULL UNIQUE,
                discord_username TEXT,
                avatar_url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # 3. Copiar datos (excluyendo la columna 'points')
        print("   📦 Copiando datos...")
        cursor.execute("""
            INSERT INTO discord_profile_new 
                (id, user_id, discord_id, discord_username, avatar_url, created_at, updated_at)
            SELECT 
                id, user_id, discord_id, discord_username, avatar_url, created_at, updated_at
            FROM discord_profile
        """)
        
        rows_copied = cursor.rowcount
        print(f"   ✅ {rows_copied} filas copiadas")
        
        # 4. Eliminar tabla antigua
        print("   🗑️  Eliminando tabla antigua...")
        cursor.execute("DROP TABLE discord_profile")
        
        # 5. Renombrar tabla nueva
        print("   📝 Renombrando tabla nueva...")
        cursor.execute("ALTER TABLE discord_profile_new RENAME TO discord_profile")
        
        # 6. Commit cambios
        conn.commit()
        
        # 7. Verificar resultado
        cursor.execute("PRAGMA table_info(discord_profile)")
        new_columns = cursor.fetchall()
        new_column_names = [col[1] for col in new_columns]
        
        print(f"\n✅ Migración completada exitosamente")
        print(f"   Columnas finales: {', '.join(new_column_names)}")
        print(f"   Filas migradas: {rows_copied}")
        
    except Exception as e:
        print(f"\n❌ Error durante la migración: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
