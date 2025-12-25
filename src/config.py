import logging
from pathlib import Path

logger = logging.getLogger("Config")

MODS_DIR = Path("mods")
logger.info(MODS_DIR)
LOADER = "fabric"
MINECRAFT_VERSIONS = ["1.21.8"]
SEARCH_DEPTH = 5
VERSION_TYPES = ["release","beta","alpha"]
