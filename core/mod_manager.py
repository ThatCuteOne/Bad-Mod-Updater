

import hashlib
from pathlib import Path


class index():
    def __init__(self):
        self.data = []

async def calc_hash(file:Path):
    with open(file,'rb') as f:
        return hashlib.sha512(f.read()).hexdigest()


class ModEntry():
    def __init__(self,data:dict):
        self.color = data.get("color")
        self.hash = data.get("hash")
        self.dependency = data.get("dependency")
        self.project_id = data.get("project_id")
        self.mod_name = data.get("mod_name")
        self.url = data.get("url")
        self.filename = data.get('filename')
        try:
            self.dependencies = data.get("dependencies")
        except:
            pass