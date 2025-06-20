from dataclasses import asdict
import json
import os
import logging
from pathlib import Path
from typing import List, Optional
from .models import ModFile, ModVersion
from .api_client import ModrinthAPI
from config import settings

class ModIndex:
    def __init__(self, index_file: Path = settings.INDEX_FILE):
        self.index_file = index_file
        self.versions: List[ModVersion] = []
        self.load()
        
    def load(self) -> None:
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self.versions = json.load(f)
        except FileNotFoundError:
            self.versions = []
            open(self.index_file, 'w', encoding='utf-8')
            self.save()
        except json.JSONDecodeError:
            os.remove(self.index_file)
            
        
    def save(self) -> None:
        print("save")
        with open(self.index_file, 'w') as f:
            json.dump([v for v in self.versions], f, indent=2)

    def getmetadata(self,file:Path):
        f = ModFile.load_file(file=file)
        if not f:
            return None
        target_hash = f['hashes'].get("sha512")
        try:
            for existing in self.versions:
                # get modversion from index by matching hash
                for existing_file in existing['files']:
                    if (existing_file['primary'] and 
                        existing_file['hashes'].get('sha512') == target_hash):
                            return existing
        except Exception as e:
            print(f"No version found in index {e}")
            return None
        #return ModVersion(f)

    def add_version(self, version: dict) -> bool:
        print("Adding Version to index")
        # Extract primary file (required)
        primary_files = [f for f in version['files'] if f['primary']]
        if not primary_files:
            raise ValueError("Version must have a primary file!")
        primary_sha512 = primary_files[0]['hashes']["sha512"]
        
        for existing in self.versions:
            # Check if primary file SHA512 already exists (globally)
            for existing_file in existing.get('files'):
                if (existing_file["primary"] and 
                    existing_file['hashes']['sha512'] == primary_sha512):
                    raise IndexError(f"Duplicate primary file (SHA512: {primary_sha512[:8]}...)")
        self.versions.append(version)
        try:
            self.save()
            print("yay")
        except Exception as a:
            print(f"-w- {a}")
        
    def remove_version(self, hash) -> bool:
        initial_count = len(self.versions)
        self.versions = [
            v for v in self.versions
            if not self._matches_hash(v,hash)
        ]

        removed = len(self.versions) < initial_count
        if removed:
            self.save()
        elif not removed and initial_count > 0:
            raise ValueError(f"No version found with primary file hash: {hash[:8]}...")
        return removed
    
    def _get_primary_file(self, version: dict) -> ModFile:
        """Get the primary file from a version."""
        primary_files = [f for f in version["files"] if f['primary']]
        if not primary_files:
            raise ValueError(f"Version {version.modname} has no primary file")
        return primary_files[0]
    
    def _has_duplicate(self, sha512_hash: str) -> bool:
        """Check if a file with this hash already exists."""
        return any(
            f.hashes.get('sha512') == sha512_hash
            for v in self.versions
            for f in v['files']
            if f.primary
        )
    def _matches_hash(self, version: ModVersion, target_hash: str) -> bool:
        """Check if version has a file matching the target hash."""
        return any(
            f.hashes.get('sha512') == target_hash
            for f in version['files']
        )


class ModUpdater:
    def __init__(self):
        self.index = ModIndex()
        self.api = ModrinthAPI()
        
    def get_mod_files(self) -> List[Path]:
        return [f for f in os.listdir(settings.MODS_DIRECTORY) if f.endswith('.jar')]
    
    def get_mod_from_index(self,current):
        new = self.api.get_newest_version(current)
        self.api.download_file()


    def get_mod_from_modname(self,file):
        print("Getting mod from search")
        data = ModVersion.from_file(file)
        searched_mod = self.api.search_mod(data.get('modname'))
        new_version = self.api.get_newest_version(searched_mod.get('project_id'))
        new_file = self.index._get_primary_file(new_version)
   
        try:
            self.api.download_file(new_file['url'],(settings.MODS_DIRECTORY / new_file['filename']))
            self.index.add_version(new_version)
            os.remove(settings.MODS_DIRECTORY / file)
        except Exception as e:
            print(f">w<: {e}")



    def update_mod(self, mod_file: Path) -> bool:
        """Update a single mod file to its latest version."""
        try:
            current_version = self.index.getmetadata(mod_file)
            if not current_version:
                self.get_mod_from_modname(mod_file)
            else:
                self.get_mod_from_index(current_version)
            
        except Exception as e:
            print(f"Failed to update {mod_file}: {e}")
            return False
        
    def update_all(self) -> int:
        mod_files = self.get_mod_files()
        if not mod_files:
            #logger.info("No mod files found to update")
            return 0
        success_count = 0
        for mod_file in mod_files:
            if self.update_mod(mod_file):
                success_count += 1
                
        #logger.info(f"Updated {success_count}/{len(mod_files)} mods successfully")
        return success_count