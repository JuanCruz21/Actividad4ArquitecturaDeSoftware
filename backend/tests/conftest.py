"""Configuración común de las pruebas.

Cada ejecución usa un directorio de datos temporal para no tocar las bases de
datos reales del prototipo. La variable de entorno se fija antes de importar
cualquier módulo de ``labcloud``, porque la ruta se resuelve en tiempo de
importación.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("LABCLOUD_DATA_DIR", tempfile.mkdtemp(prefix="labcloud-pruebas-"))
os.environ.setdefault("LABCLOUD_LOG_LEVEL", "WARNING")
