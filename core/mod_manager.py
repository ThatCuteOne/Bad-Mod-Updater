from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import List
from venv import logger
import zipfile
from colorama import init, Fore, Style
init()
import toml
from core import settings
from core.modrinth_api import ModrinthAPI

class User():
    def ask_yes_no(question):
        while True:
            answer = input(f"{question} (yes/no): ").strip().lower()
            if answer in {"yes", "y"}:
                return True
            elif answer in {"no", "n"}:
                return False
            elif answer == "":
                return False
            else:
                print("Please enter 'yes' or 'no'.")
    @staticmethod
    def print_right_text(left_text,right_text):
        available_space = os.get_terminal_size().columns - len(left_text) - len(right_text)
        print(left_text + " " * max(0, available_space) + right_text)
    @staticmethod
    def print_rgb_colorama(text, rgb_int):
        r = (rgb_int >> 16) & 0xFF  # Red component
        g = (rgb_int >> 8) & 0xFF   # Green component
        b = rgb_int & 0xFF           # Blue component
        print(f"\033[38;2;{r};{g};{b}m{text}{Style.RESET_ALL}")

class ModEntry():
    @staticmethod
    def load_file(file:Path):
        return dict(
            filename = str(file),
            hashes ={'sha512': ModEntry.calculate_hash(file)},
            url = "", # get from api
            primary = True
            )
    
    def get_metadata_from_jar(self,file):
            with zipfile.ZipFile(settings.MODS_DIRECTORY / file, 'r') as jar:
            # detect mod loader
                if "fabric.mod.json" in jar.namelist():
                    with jar.open("fabric.mod.json") as f:
                        data = json.load(f)
                        return {
                            'id': data["id"],
                            'name': data["name"],
                            'sha512': self.calculate_hash(file)
                        }
                elif "META-INF/neoforge.mods.toml" in jar.namelist():
                    with jar.open("META-INF/neoforge.mods.toml") as f:
                        data = toml.loads(f.read().decode('utf-8'))
                        return {
                            'id': data['mods'][0]['modId'],
                            'name': data['mods'][0]['displayName'],
                            'sha512': self.calculate_hash(file)
                        }
                elif "META-INF/mods.toml" in jar.namelist():
                    with jar.open("META-INF/mods.toml") as f:
                        data = toml.loads(f.read().decode('utf-8'))
                        return {
                            'id': data['mods'][0]['modId'],
                            'name': data['mods'][0]['displayName'],
                            'sha512': self.calculate_hash(file)
                        }
            
                raise ValueError("Unsupported mod format")
    @staticmethod
    def calculate_hash(file:Path):
        sha512_hash = hashlib.sha512()
        # Open the file in binary mode
        with open(settings.MODS_DIRECTORY / file, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha512_hash.update(byte_block)
        return sha512_hash.hexdigest()
    @staticmethod
    def _get_primary_file(version: dict):
        """Get the primary file from a version."""
        primary_files = [f for f in version["files"] if f['primary']]
        if not primary_files:
            raise ValueError(f"Version {version["metadata"]["title"]} has no primary file")
        return primary_files[0]
    def _get_required_dependencies(version: dict):
        """Get the all required dependencies from a version."""
        required_dependencies = [f for f in version["dependencies"] if f['dependency_type'] == "required"]
        if not required_dependencies:
            logger.info(f"Version {version["metadata"]["title"]} has no required dependencies")
        return required_dependencies
    @staticmethod
    def _add_mod_file(version):
        version['mod_file'] = ModEntry._get_primary_file(version)
        return version

class ModIndex():
    def __init__(self, index_file: Path = settings.INDEX_FILE):
        self.index_file = index_file
        self.versions: List[dict] = []
        self.load()
    def load(self) -> None:
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self.versions = json.load(f)
        except FileNotFoundError:
            logger.warning("Couldn't find index file. Creating new one")
            self.versions = []
            open(self.index_file, 'w', encoding='utf-8')
            self.save()
        except json.JSONDecodeError as a:
            self.versions = []
            logger.error(f"Couldn't load index file:\n {a}")
    def save(self) -> None:
        with open(self.index_file, 'w') as f:
            json.dump([v for v in self.versions], f, indent=2)
    def remove_by_hash(self,target_hash):
        new_index = []
        for existing in self.versions:
            # get modversion from index by matching hash
            for existing_file in existing['files']:
                if (existing_file['primary'] and not
                    existing_file['hashes'].get('sha512') == target_hash):
                        new_index.append(existing)
        self.versions = new_index
        self.save()
    def add_version(self,version):
        self.versions.append(version)
        self.save()
    @staticmethod
    def search_in_index(index,file):
        target_hash = ModEntry.calculate_hash(file)
        
        try:
            for entry in index:
                # Find the primary file in the files array
                primary_file = next(
                    (f for f in entry.get('files', []) if f.get('primary', False)),
                    None
                )
                if primary_file and primary_file['hashes']['sha512'] == target_hash:
                    return entry
        except Exception as e:
            logger.error(f"Error searching index: {e}")
        logger.warning(f"No version found in index for file {file}")
        return None
    def key_in_versions(self,key:str,target_key):
            for entry in self.versions:
                if entry[f'{key}'] == target_key:
                    return entry
            return False
                

class ModManager():
    def __init__(self):
        self.index = ModIndex()
        self.api = ModrinthAPI()
        self.user = User()
    def get_mod(self,version:dict):
        new_version = self.api.get_newest_version(version)
        if not new_version:
            print(f"Couln't find compatible version for selected Minecraft Version: '{settings.MINECRAFT_VERSION}' and Loader: '{settings.MOD_LOADER}'")
            return False
        self.resolve_dependencies(new_version)
        for file in new_version['files']:
            if file["hashes"]['sha512'] == version['mod_file']["hashes"]['sha512'] and file["primary"] == True:
                print("Newest Version is already installed")
            else:
                new_version['mod_file'] = file
                new_version['metadata'] = version['metadata']
                self.user.print_right_text(f"Found New Version '{new_version['version_number']}' for mod '{version['metadata']['title']}'","Installing...")
                self.install_mod(new_version,version)
                return True
    def remove_orphan_dependencies(self,entries):
        print("removeing orphans")
        referenced_ids = set()
        removed_mod_files = []
        for entry in entries:
            for dep in entry.get("dependencies", []):
                referenced_ids.add(dep["project_id"])
            if entry.get("installed_via_dependency_handler", False):
                for parent in entry.get("parents", []):
                    referenced_ids.add(parent)

        filtered_entries = []
        for entry in entries:
            if not entry.get("installed_via_dependency_handler", False) or entry["project_id"] in referenced_ids:
                print(f"not orphan:{entry["mod_file"]["filename"]}")
                filtered_entries.append(entry)
            else:
                removed_mod_files.append(entry["mod_file"]["filename"])
                os.remove(settings.MODS_DIRECTORY / entry["mod_file"]["filename"])
        return filtered_entries,removed_mod_files
    def verifiy_index(self,mod_files):
        new_index = []
        for i in self.index.versions:
            for f in mod_files:
                if ModEntry.calculate_hash(f) == i['mod_file']['hashes']['sha512']:
                    new_index.append(i)
        self.index.versions, removed_mod_files = self.remove_orphan_dependencies(new_index)
        self.index.save()
        mod_files -= set(removed_mod_files)
        return mod_files
        

    def resolve_dependencies(self,parent_version:dict):
        print('resoving dependencies...')
        dependencies = [
            d for d in parent_version['dependencies']
            if d['dependency_type'] == "required"
        ]
        if not dependencies:
            print("No required dependencies found")
            return False
        for dependency in dependencies:
            d = self.index.key_in_versions('project_id',dependency['project_id'])
            if d:
                try:
                    d['parents'].append(parent_version['project_id'])
                except KeyError:
                    d['parents'] = [parent_version['project_id']]
                print(f"Dependency '{d['metadata']['title']}' is already installed")
            else:
                version = self.api.get_newest_version(dependency)
                if not version:
                    print(f"Couln't find compatible version for selected Minecraft Version: '{settings.MINECRAFT_VERSION}' and Loader: '{settings.MOD_LOADER}'")
                    return False
                version['metadata'] =  self.api.get_project_info(version['project_id'])
                if 'parents' not in version or not isinstance(version['parents'], list):
                    version['parents'] = []
                version['parents'].append(parent_version['project_id'])
                print(f"Installing dependency '{version['metadata']['title']}'")
                version["installed_via_dependency_handler"] = True
                self.install_new_mod(version)
                self.resolve_dependencies(version)

    def install_new_mod(self,version:dict):
        version = ModEntry._add_mod_file(version)
        self.api.download_file(version['mod_file']['url'],settings.MODS_DIRECTORY / version['mod_file']['filename'])
        self.index.add_version(version)
            
    def install_mod(self,new_version,old_version):
        self.api.download_file(new_version['mod_file']['url'],settings.MODS_DIRECTORY / new_version['mod_file']['filename'])
        self.index.remove_by_hash(old_version['mod_file']['hashes']['sha512'])
        os.remove(settings.MODS_DIRECTORY / old_version['mod_file']['filename'])
        self.index.add_version(new_version)

    def get_mod_from_file(self,file):
        metadata = ModEntry.get_metadata_from_jar(ModEntry(),file)
        project = self.api.search_mod(metadata['name'])
        if not project:
            return False
        versions = self.api.get_project_versions(project['project_id'])
        version = self.index.search_in_index(versions,file)
        
        if not version:
            new_version = self.api.get_newest(versions)
            if User.ask_yes_no(f"Couldn't automatically get installed version, do you want to proceed with installing '{project['title']}' version: '{new_version['version_number']}'"):
                for f in new_version['files']:
                        if f["primary"]:
                            new_version['mod_file'] = f
                            new_version['metadata'] = project
                            self.install_mod(new_version,{'mod_file':{'hashes':{'sha512':metadata['sha512']},'filename':file}})
                            return True
        else:
            for f in version['files']:
                if f["primary"]:
                    version['mod_file'] = f
            version['metadata'] = project
            print(f"Automatically detected installed version for mod '{project['title']}' version: '{version['version_number']}'")
            self.index.add_version(version)
            return self.get_mod(version)



    def update_mod(self,modfile):
        data = self.index.search_in_index(self.index.versions, modfile)
        if data:
            print(f"Mod:'{data['metadata']['title']}'")
            return self.get_mod(data)
        else:
            self.get_mod_from_file(modfile)

    def get_mod_files(self) -> List[Path]:
        return set(f for f in os.listdir(settings.MODS_DIRECTORY) if f.endswith('.jar'))

    def update_all(self) -> int:
        mod_files = self.get_mod_files()
        if not mod_files:
            print("No mod files found to update")
            return 0
        success_count = 0
        mod_files = self.verifiy_index(mod_files)
        for mod_file in mod_files:
            if self.update_mod(mod_file):
                success_count += 1
                
        print(f"Updated {success_count}/{len(mod_files)} mods successfully")
        return success_count