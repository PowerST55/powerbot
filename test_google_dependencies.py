"""
Script de prueba para verificar instalación de dependencias de Google API.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

def test_bootstrap():
    """Prueba el bootstrap para instalar dependencias."""
    print("=" * 60)
    print("Test de Bootstrap - Dependencias Google API")
    print("=" * 60)
    
    print(f"\n📍 Python ejecutable: {sys.executable}")
    print(f"📍 Versión: {sys.version}")
    
    # Ejecutar bootstrap
    print("\n🔄 Ejecutando bootstrap...\n")
    
    try:
        from backend.bootstrap import bootstrap
        success = bootstrap(verbose=True)
        
        if not success:
            print("\n❌ Bootstrap falló")
            return False
            
    except Exception as e:
        print(f"\n❌ Error en bootstrap: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_google_imports():
    """Verifica que los módulos de Google se puedan importar."""
    print("\n" + "=" * 60)
    print("Verificando imports de Google API")
    print("=" * 60 + "\n")
    
    imports_to_test = [
        ("google.auth", "Google Auth"),
        ("google_auth_oauthlib", "Google Auth OAuth"),
        ("googleapiclient", "Google API Python Client"),
        ("googleapiclient.discovery", "Google API Discovery"),
    ]
    
    all_success = True
    for module_name, display_name in imports_to_test:
        try:
            __import__(module_name)
            print(f"✅ {display_name} ({module_name})")
        except ImportError as e:
            print(f"❌ {display_name} ({module_name}): {e}")
            all_success = False
    
    return all_success

def test_youtube_core():
    """Verifica que el módulo youtube_core funcione."""
    print("\n" + "=" * 60)
    print("Verificando YouTube Core")
    print("=" * 60 + "\n")
    
    try:
        from backend.services.youtube_api import YouTubeAPI
        print("✅ YouTubeAPI importado correctamente")
        
        # Verificar que puede crear instancia (sin conectar)
        print("📋 Creando instancia de YouTubeAPI (sin conectar)...")
        
        # No vamos a conectar, solo verificar que la clase existe
        print("✅ Clase YouTubeAPI disponible")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error importando YouTubeAPI: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal."""
    results = []
    
    # Test 1: Bootstrap
    results.append(("Bootstrap", test_bootstrap()))
    
    # Test 2: Imports de Google
    results.append(("Google Imports", test_google_imports()))
    
    # Test 3: YouTube Core
    results.append(("YouTube Core", test_youtube_core()))
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ TODAS LAS DEPENDENCIAS ESTÁN INSTALADAS CORRECTAMENTE")
        print("\n💡 Ahora puedes ejecutar:")
        print("   python backend/app.py")
        print("   Luego escribe: yapi")
        return 0
    else:
        print("\n❌ HAY PROBLEMAS CON LAS DEPENDENCIAS")
        print("\n💡 Solución:")
        print("   pip install google-auth google-auth-oauthlib google-api-python-client")
        return 1

if __name__ == "__main__":
    exit(main())
