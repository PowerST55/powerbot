"""
Script de diagnóstico: verifica qué paquetes faltan según el bootstrap.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

print("=" * 60)
print("Diagnóstico de Dependencias")
print("=" * 60)

# Leer pyproject.toml
try:
    import tomllib
except ImportError:
    import tomli as tomllib

pyproject_path = root_dir / "pyproject.toml"
with open(pyproject_path, "rb") as f:
    pyproject = tomllib.load(f)

dependencies = pyproject.get("project", {}).get("dependencies", [])

print(f"\n📋 Total de dependencias en pyproject.toml: {len(dependencies)}\n")

# Verificar cada una
missing = []
installed = []

for dep in dependencies:
    # Extraer nombre del paquete
    name = dep.split(";")[0].split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
    
    # Mapeos especiales
    import_names = {
        "prompt-toolkit": "prompt_toolkit",
        "python-dotenv": "dotenv",
        "discord.py": "discord",
        "google-auth": "google.auth",
        "google-auth-oauthlib": "google_auth_oauthlib",
        "google-api-python-client": "googleapiclient",
    }
    
    import_name = import_names.get(name, name.replace("-", "_"))
    
    # Verificar si está instalado
    try:
        __import__(import_name)
        print(f"✅ {name:<35} (importa como: {import_name})")
        installed.append(name)
    except ImportError:
        print(f"❌ {name:<35} (importa como: {import_name})")
        missing.append(dep)

# Resumen
print("\n" + "=" * 60)
print(f"✅ Instalados: {len(installed)}/{len(dependencies)}")
print(f"❌ Faltantes:  {len(missing)}/{len(dependencies)}")
print("=" * 60)

if missing:
    print("\n⚠️  Paquetes faltantes:\n")
    for pkg in missing:
        print(f"   • {pkg}")
    print(f"\n💡 Instalar con:\n   pip install {' '.join(missing)}")
else:
    print("\n✅ ¡Todas las dependencias están instaladas!")
