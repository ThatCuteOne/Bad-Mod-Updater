import hashlib
import json
import os
from typing import Dict, Optional, Union
import zipfile

import requests
import toml


class Modindex:
    def __init__(self,filename=".index.json"):
        self.filename = filename
        self.index = []
        self.load()
    def load(self):
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
        except FileNotFoundError:
            self.index = []
    def save(self):
        with open(self.filename, 'w') as f:
            json.dump(self.index, f, indent=2)

    def write(self, version:dict, modname:str):
        """Adds a new version to the index if no duplicates exist.
        
        Checks for duplicates by:
        Primary file's SHA512 hash (must be globally unique)
        
        Args:
            version (dict): The version data to add.
            modname (str): The name of the mod this version belongs to.
        
        Raises:
            ValueError: If the version has no primary file.
            IndexError: If a duplicate version or file is found.
        """
        # Extract primary file (required)
        primary_files = [f for f in version.get('files', []) if f.get('primary')]
        if not primary_files:
            raise ValueError("Version must have a primary file!")
        primary_sha512 = primary_files[0]['hashes']['sha512']
        
        for existing in self.index:
            # Check if primary file SHA512 already exists (globally)
            for existing_file in existing.get('files', []):
                if (existing_file.get('primary') and 
                    existing_file.get('hashes', {}).get('sha512') == primary_sha512):
                    raise IndexError(f"Duplicate primary file (SHA512: {primary_sha512[:8]}...)")
        
        version_with_modname = version.copy()
        version_with_modname['modname'] = modname
        self.index.append(version_with_modname)
        self.save()
        return True
    def remove(self, identifier: Union[str, Dict], by_hash: bool = False) -> bool:
        """
        Remove an entry from the index.
        
        Args:
            identifier: Either:
                - A file path (str) to remove by SHA512 hash
                - A version dictionary to remove by direct comparison
                - A project ID (str) to remove all versions of a mod
            by_hash: If True and identifier is str, treat as direct SHA512 hash
        
        Returns:
            bool: True if entry was found and removed, False otherwise
        """
        removed = False
        
        if isinstance(identifier, str):
            if by_hash:
                # Remove by direct hash string
                target_hash = identifier
            else:
                # Remove by file path (calculate hash)
                if not os.path.exists(identifier):
                    print(f"Error: File {identifier} not found")
                    return False
                target_hash = self.calculate_sha512(identifier)
                
            # Remove all versions containing this file hash
            self.index = [
                version for version in self.index
                if not any(
                    f.get('hashes', {}).get('sha512') == target_hash
                    for f in version.get('files', [])
                )
            ]
            removed = len(self.index) != len(self.index)  # Check if any were removed
            
        elif isinstance(identifier, dict):
            # Remove by direct dictionary comparison
            original_length = len(self.index)
            self.index = [v for v in self.index if v != identifier]
            removed = len(self.index) < original_length
            
        if removed:
            self.save()
        return removed
                    


    def calculate_sha512(self,file_path:str):
        sha512_hash = hashlib.sha512()
        
        # Open the file in binary mode
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha512_hash.update(byte_block)
        return sha512_hash.hexdigest()

    def search(self, file_path: str) -> Optional[dict]:
            """
            Search for index entry matching the file's hash.
            
            Args:
                file_path: Path to the mod file to search for
                
            Returns:
                The version dictionary if found, None otherwise
            """
            try:
                file_hash = self.calculate_sha512(file_path)
                
                for version in self.index:
                    if not isinstance(version, dict):
                        continue
                        
                    files = version.get('files', [])
                    if not isinstance(files, list):
                        continue
                        
                    for f in files:
                        if not isinstance(f, dict):
                            continue
                            
                        hashes = f.get('hashes', {})
                        if not isinstance(hashes, dict):
                            continue
                            
                        if hashes.get('sha512') == file_hash:
                            return version
                            
                return None
                
            except Exception as e:
                print(f"Error searching for {file_path}: {e}")
                return None




class VersionEntry:
    def search_modname(self):
        """Request search for modname at the api

        """
        url = "https://api.modrinth.com/v2/search"
        params = {
                "query": f"{self.modname}",
                "index": "relevance",
                "limit": 1,
                "facets": f"""
                [
                    [
                        "project_type:mod"
                    ],
                    [
                        "categories:{self.loader}"
                    ],
                    [
                        "versions:{self.minecraft_version}"
                    ]
                ]
                """
        }

        response = requests.get(url, params)
        response.raise_for_status()
        results = response.json()["hits"]
        if not results:
            return None
        else:
            return results[0]
        
    def get_newest_version(self):
        """Returns the newest mod version(if compatible)
        Args:
            id(str) : id of the modrinth project
        """
        id = self.version.get('project_id')
        url = f"https://api.modrinth.com/v2/project/{id}/version"
        response = requests.get(url)
        response.raise_for_status()
        results = response.json()

        compatible_versions = []

        for version in results:
            if self.minecraft_version in version["game_versions"]:
                if self.loader in version["loaders"]:
                    compatible_versions.append(version)
        if not compatible_versions:
                return None
        else:
            return max(compatible_versions, key=lambda x: x["date_published"])
        
    def download_mod(self):
        response = requests.get(self.version["files"][0].get("url"))
        response.raise_for_status()
        with open(self.version["files"][0].get("filename"), "wb") as f:
            f.write(response.content)
    def __init__(self, filename: str,loader:str,minecraft_version:str):
        self.filename = filename
        self.loader = loader
        self.minecraft_version = minecraft_version
        self.modname = ""
        self.jar = 0
        self.version = None
        
        # Initialize from Modindex if available
        dex = Modindex()
        try:
            index_entry = dex.search(filename)
            self.modname = index_entry.get('modname')
            if index_entry and isinstance(index_entry,dict):
                self.version = index_entry
                self.version = self.get_newest_version()
                return

        except Exception as e:
            print(f"Error initializing from Modindex: {e}")

        # Fall back to reading from JAR
        
        try:
            self.modname = self.read_jar(filename)
            search_result = self.search_modname()
            if search_result:
                self.version = search_result
                self.version = self.get_newest_version()
                self.jar = 1
            self.version = self.get_newest_version()
            self.jar = 1
        except Exception as e:
            print(f"Error reading JAR file: {e}")
        return None
    def read_jar(self,filename):
        with zipfile.ZipFile(filename, 'r') as jar:
        # detect mod loader
            if "fabric.mod.json" in jar.namelist():
                file_inside_jar = "fabric.mod.json"
                loadertype = 1
            elif "META-INF/neoforge.mods.toml" in jar.namelist():
                file_inside_jar = "META-INF/neoforge.mods.toml"
                loadertype = 2
            elif "META-INF/mods.toml" in jar.namelist():
                file_inside_jar = "META-INF/mods.toml"
                loadertype = 3
            
            with jar.open(file_inside_jar) as file:
                content_bytes = file.read()
        moddata = content_bytes.decode('utf-8')
        if loadertype == 1: 
            mod_name = (json.loads(moddata))["name"]
            return mod_name
        elif loadertype == 2 or loadertype == 3:
            return (toml.loads(moddata))['mods'][0]['displayName']
        

def a():
    print("asdasfasfasfsafsa")