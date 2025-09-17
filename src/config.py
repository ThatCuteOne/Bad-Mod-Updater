import json
import logging
from pathlib import Path

logger = logging.getLogger("Config")

MODS_DIR = Path("mods")
logger.info(MODS_DIR)
LOADER = "fabric"
MINECRAFT_VERSION = "1.21.8"
SEARCH_DEPTH = 5
VERSION_TYPES = ["release","beta","alpha"]

def load_index():
    try:
        with open(MODS_DIR/".modIndex.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("No index file found. Creating new one")
        with open(MODS_DIR/".modIndex.json", "w") as f:
            f.write("[]")
        return []

class Index():
    indexlist: list = load_index()