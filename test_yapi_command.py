"""
Test rápido para verificar que el comando yapi está registrado.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

def test_yapi_registration():
    """Verifica que el comando yapi está registrado."""
    print("🔍 Verificando registro del comando /yapi...")
    
    try:
        from backend.console.commands.commands_general import COMMANDS
        
        # Verificar que yapi está en COMMANDS
        if "yapi" in COMMANDS:
            print("✅ Comando 'yapi' registrado en COMMANDS")
        else:
            print("❌ Comando 'yapi' NO encontrado en COMMANDS")
            return False
        
        # Verificar que cmd_yapi existe
        from backend.console.commands.commands_general import cmd_yapi
        print("✅ Función cmd_yapi importada correctamente")
        
        # Verificar que el comando yapi de YouTube existe
        from backend.console.commands.commands_youtube import YOUTUBE_COMMANDS
        if "yapi" in YOUTUBE_COMMANDS:
            print("✅ Comando 'yapi' existe en YOUTUBE_COMMANDS")
        else:
            print("❌ Comando 'yapi' NO encontrado en YOUTUBE_COMMANDS")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_commands_list():
    """Lista todos los comandos disponibles."""
    print("\n📋 Comandos registrados en el sistema:")
    
    try:
        from backend.console.commands.commands_general import COMMANDS
        
        for cmd_name in sorted(COMMANDS.keys()):
            print(f"   • {cmd_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Función principal."""
    print("=" * 60)
    print("Test de Comando /yapi")
    print("=" * 60)
    
    results = []
    
    results.append(("Registro de yapi", test_yapi_registration()))
    results.append(("Lista de comandos", test_commands_list()))
    
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
        print("✅ COMANDO /yapi LISTO PARA USAR")
        print("\n💡 Uso:")
        print("   1. python backend/app.py")
        print("   2. Escribe: yapi")
        print("   3. El sistema conectará YouTube e iniciará el listener")
        return 0
    else:
        print("❌ HAY PROBLEMAS CON EL COMANDO")
        return 1

if __name__ == "__main__":
    exit(main())
