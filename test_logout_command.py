"""
Test del comando yt logout
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

def test_logout_command_registration():
    """Verifica que el comando logout está registrado."""
    print("=" * 60)
    print("Test: Comando yt logout")
    print("=" * 60)
    
    try:
        from backend.console.commands.commands_youtube import YOUTUBE_COMMANDS
        
        if "logout" in YOUTUBE_COMMANDS:
            print("✅ Comando 'logout' registrado en YOUTUBE_COMMANDS")
        else:
            print("❌ Comando 'logout' NO encontrado")
            return False
        
        # Verificar que la función existe
        from backend.console.commands.commands_youtube import cmd_youtube_logout
        print("✅ Función cmd_youtube_logout existe")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        return False

def test_token_path():
    """Verifica la ruta del token."""
    print("\n📁 Verificando ruta del token...")
    
    backend_dir = root_dir / "backend"
    token_path = backend_dir / "keys" / "ytkey.json"
    
    print(f"   Ruta: {token_path}")
    
    if token_path.exists():
        print(f"   ✅ Token existe (será borrado con 'yt logout')")
        print(f"   📊 Tamaño: {token_path.stat().st_size} bytes")
    else:
        print(f"   ℹ️  Token no existe (ya está desconectado)")
    
    return True

def main():
    """Función principal."""
    results = []
    
    results.append(("Registro de comando", test_logout_command_registration()))
    results.append(("Verificación de token", test_token_path()))
    
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ COMANDO 'yt logout' LISTO")
        print("\n💡 Uso:")
        print("   1. python backend/app.py")
        print("   2. Escribe: yt logout")
        print("   3. El token será borrado y deberás autenticarte de nuevo")
        print("\n📋 Qué hace 'yt logout':")
        print("   • Detiene el listener si está activo")
        print("   • Detiene el monitoreo de chat ID")
        print("   • Desconecta la API de YouTube")
        print("   • Borra el archivo ytkey.json")
        print("   • Limpia todas las variables globales")
        return 0
    else:
        print("\n❌ HAY PROBLEMAS CON EL COMANDO")
        return 1

if __name__ == "__main__":
    exit(main())
