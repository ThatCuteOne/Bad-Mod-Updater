from dataclasses import asdict, dataclass
import datetime
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import hashlib
import zipfile
from config import settings
import toml

@dataclass
class ModFile:
    filename: str
    primary: bool
    hashes: Dict[str, str]
    url: str
    @staticmethod
    def load_file(file:Path):
        return dict(
            filename = str(file),
            hashes ={'sha512': ModFile.calculate_hash(file)},
            url = "", # get from api
            primary = True
            )
    @staticmethod
    def calculate_hash(file:Path):
        sha512_hash = hashlib.sha512()
        # Open the file in binary mode
        with open(settings.MODS_DIRECTORY / file, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha512_hash.update(byte_block)
        return sha512_hash.hexdigest()

@dataclass
class ModVersion:
    project_id: str
    modname: str
    game_versions: List[str]
    loaders: List[str]
    files: List[ModFile]
    date_published: str
    @classmethod
    def from_file(cls, mod_file: Path):
        """Create ModVersion from a mod file (JAR)."""
        try:
            metadata = cls._extract_metadata(mod_file)
            return dict(
                project_id = "", # Filled later from API
                modname=metadata['name'],
                game_versions=[],  # Filled later from API
                loaders=[],        # Filled later from API
                files=ModFile.load_file(mod_file),
                date_published=""  # Filled later from API
            )
        except Exception as e:
            #logger.error(f"Failed to parse {mod_file.name}: {e}")
            print(f"Failed to parse {mod_file.name}: {e}")
            return None
    @classmethod
    def from_dict(cls,dictionary,modname) -> 'ModVersion':
        return cls(
                project_id = dictionary['project_id'],
                modname=modname,
                game_versions=dictionary['game_versions'],
                loaders=dictionary['loaders'],
                files=[
                    ModFile(
                        filename=f["filename"],
                        hashes=f['hashes'],
                        url=f['url'],
                        primary=f.get('primary', False)
                    )
                    for f in dictionary['files']
                ],
                date_published=dictionary['date_published']
        )
    def to_dict(self):
        return {
            'project_id': self.project_id,
            'modname': self.modname,
            'game_versions': self.game_versions,
            'loaders': self.loaders,
            'files': [{
                'filename': f.filename,
                'hashes': f.hashes,
                'url': f.url,
                'primary': f.primary
            } for f in self.files],
            'date_published': self.date_published.isoformat() if hasattr(self.date_published, 'isoformat') else self.date_published
        }
    @staticmethod
    def _extract_metadata(mod_file: Path) -> Dict:
            with zipfile.ZipFile(settings.MODS_DIRECTORY / mod_file, 'r') as jar:
            # detect mod loader
                if "fabric.mod.json" in jar.namelist():
                    with jar.open("fabric.mod.json") as f:
                        data = json.load(f)
                        return {
                            'id': data["id"],
                            'name': data["name"]
                        }
                elif "META-INF/neoforge.mods.toml" in jar.namelist():
                    with jar.open("META-INF/neoforge.mods.toml") as f:
                        data = toml.loads(f.read().decode('utf-8'))
                        return {
                            'id': data['mods'][0]['modId'],
                            'name': data['mods'][0]['displayName']
                        }
                elif "META-INF/mods.toml" in jar.namelist():
                    with jar.open("META-INF/mods.toml") as f:
                        data = toml.loads(f.read().decode('utf-8'))
                        return {
                            'id': data['mods'][0]['modId'],
                            'name': data['mods'][0]['displayName']
                        }
            
                raise ValueError("Unsupported mod format")