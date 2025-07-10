import json
import core.settings as settings

import hashlib
from pathlib import Path


class index():
    def __init__(self):
        self.data = self.load()
    async def write(self,new_data:dict):
        self.data.append(new_data)
    def save(self):
        with open(settings.INDEX_FILE, 'w') as f:
            json.dump(self.data, f, indent=2)
    def load(self) -> list:
        try:
            with open(settings.INDEX_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            open(settings.INDEX_FILE, 'w', encoding='utf-8')
            return []
        except json.JSONDecodeError as a:
            return []
    async def remove_by_hash(self,hash):
        new_index = []
        for e in self.data:
            if e.get("hash") == hash:
                pass
            else:
                new_index.append(e)
        self.data = new_index
                



async def calc_hash(file:Path):
    with open(file,'rb') as f:
        return hashlib.sha512(f.read()).hexdigest()


class ModEntry():
    def __init__(self):
        self.color = None
        self.hash = None
        self.dependency = None
        self.project_id = None
        self.mod_name = None
        self.url = None
        self.filename = None
        self.versions = None
        self.dependencies = None

    async def write_to_index(self):
        await self.index.write(await self.convert_to_dict())
    async def remove_from_index(self):
        await self.index.remove_by_hash(self.hash)

    async def convert_to_dict(self):
        return {
            "color" : self.color,
            "hash": self.hash,
            "dependency": self.dependency,
            "project_id": self.project_id,
            "mod_name": self.mod_name,
            "url":self.url,
            "dependencies" : self.dependencies

        }
    async def get_data_from_dict(self, data: dict):
        for attr in data:
            if hasattr(self, attr):
                setattr(self, attr, data[attr])
    # async def get_data_from_dict(self,data:dict):
    #     self.color = data.get("color")
    #     self.hash = data.get("hash")
    #     self.dependency = data.get("dependency")
    #     self.project_id = data.get("project_id")
    #     self.mod_name = data.get("mod_name")
    #     self.url = data.get("url")
    #     self.filename = data.get('filename')
    #     self.versions = data.get('versions')
    #     self.dependencies = data.get("dependencies")