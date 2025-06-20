import os
from pathlib import Path

# Configuration
MINECRAFT_VERSION = "1.20.3"
MOD_LOADER = "fabric"
MODS_DIRECTORY = Path(__file__).parent.parent / "mods"
INDEX_FILE = MODS_DIRECTORY / ".index.json"

# Ensure mods directory exists
MODS_DIRECTORY.mkdir(exist_ok=True)