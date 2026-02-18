"""
Test script para ChatIdManager
Verifica que el módulo se importa y funciona correctamente.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

def test_imports():
    """Prueba que los imports funcionen."""
    print("🔍 Probando imports...")
    
    try:
        from backend.services.youtube_api import ChatIdManager, create_chat_id_manager
        print("✅ ChatIdManager importado correctamente")
        
        from backend.services.youtube_api.config import ChatIdManager
        print("✅ ChatIdManager (config) importado correctamente")
        
        return True
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        return False

def test_data_directory():
    """Verifica que el directorio de datos existe."""
    print("\n🔍 Verificando directorio de datos...")
    
    data_dir = root_dir / "backend" / "data" / "youtube_bot"
    
    if data_dir.exists():
        print(f"✅ Directorio existe: {data_dir}")
        
        # Listar archivos
        files = list(data_dir.glob("*"))
        if files:
            print(f"📁 Archivos encontrados: {len(files)}")
            for f in files:
                print(f"   - {f.name}")
        else:
            print("📁 Directorio vacío (se creará active_chat.json al usar)")
    else:
        print(f"📁 Directorio no existe aún: {data_dir}")
        print("   (Se creará automáticamente al primer uso)")
    
    return True

def test_module_structure():
    """Verifica la estructura del módulo."""
    print("\n🔍 Verificando estructura del módulo...")
    
    config_dir = root_dir / "backend" / "services" / "youtube_api" / "config"
    
    files_to_check = [
        "__init__.py",
        "chat_id_finder.py"
    ]
    
    all_exist = True
    for file in files_to_check:
        file_path = config_dir / file
        if file_path.exists():
            print(f"✅ {file}")
        else:
            print(f"❌ {file} NO ENCONTRADO")
            all_exist = False
    
    return all_exist

def main():
    """Función principal."""
    print("=" * 60)
    print("ChatIdManager - Test de Validación")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Directorio de datos", test_data_directory()))
    results.append(("Estructura del módulo", test_module_structure()))
    
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
        print("✅ TODOS LOS TESTS PASARON")
        print("\n📚 Para más información, ver: CHAT_ID_MANAGER_GUIDE.md")
        return 0
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        return 1

if __name__ == "__main__":
    exit(main())
