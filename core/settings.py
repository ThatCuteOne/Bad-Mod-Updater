import importlib
import subprocess
import sys
import json
import logging
import os
from pathlib import Path


REQUIRED_PACKAGES = [
    'requests',
    'toml',
    'colorama',
    'aiofiles',
    'httpx'
]

def install_package(package):
    """Install a package using pip."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def check_dependencies():
    """Check if all required packages are installed."""
    missing_packages = []
    for package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package.split('>')[0].split('<')[0].split('=')[0])
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Installing missing dependencies: {', '.join(missing_packages)}")
        for package in missing_packages:
            try:
                install_package(package)
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package}: {e}")
                sys.exit(1)

check_dependencies()

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

# create config
DEFAULT_CONFIG = {
    "minecraft_version": "1.21.7",
    "mod_loader": "fabric",
    "mods_directory": "./mods",
    "index_file": ".index.json"
}

try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
        print(f"Loaded configuration from {CONFIG_FILE}")
except FileNotFoundError:
    # Create default config if file doesn't exist
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)
    print(f"Created new configuration file at {CONFIG_FILE}")
    config = DEFAULT_CONFIG.copy()

#load data
MINECRAFT_VERSION = config['minecraft_version']
MOD_LOADER = config['mod_loader']
MODS_DIRECTORY = Path(__file__).parent.parent / (config['mods_directory'])
INDEX_FILE = MODS_DIRECTORY / config['index_file']

# Ensure mods directory exists
MODS_DIRECTORY.mkdir(exist_ok=True)