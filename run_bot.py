#!/usr/bin/env python3
"""
Wrapper para iniciar el bot con UTF-8 configurado correctamente
"""

import os
import sys
import io

# Configurar encoding UTF-8 para stdout/stderr
if sys.platform == "win32":
    # En Windows, usar UTF-8 para los streams
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ejecutar start.py
if __name__ == "__main__":
    from start import main
    main()
