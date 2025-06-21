

from pathlib import Path
from typing import List
import requests

from core import settings


class ModrinthAPI():
    

    def get_newest_version(self,version:dict):
        """Returns the newest mod version(if compatible)
        Args:
            version(dict) : local mod version
        """
        return self.get_newest(self.get_project_versions(version['project_id']))


    def get_newest(self,results):
        compatible_versions = []
        for new_version in results:
            if settings.MINECRAFT_VERSION in new_version["game_versions"]:
                if settings.MOD_LOADER in new_version["loaders"]:
                    compatible_versions.append(new_version)
                    
        if not compatible_versions:
                return None
        else:
            a = sorted(compatible_versions, key=lambda x: x["date_published"],reverse=True)
            return a[0]
    @staticmethod
    def download_file(url: str, destination: Path) -> bool:
        response = requests.get(url)
        response.raise_for_status()
        with open(destination, "wb") as f:
            f.write(response.content)
    @staticmethod
    def search_mod(modname: str,loader: str = settings.MOD_LOADER,minecraft_version: str = settings.MINECRAFT_VERSION):
        params = {"query": f"{modname}","index": "relevance","limit": 1,"facets": f"""
                  [["project_type:mod"],["categories:{loader}"],["versions:{minecraft_version}"]]
                  """}
        response = requests.get("https://api.modrinth.com/v2/search", params)
        response.raise_for_status()
        results = response.json()["hits"]
        if not results:
            return False
        else:
            return results[0]
    @staticmethod
    def get_project_versions(project_id: str) -> List[dict]:
        url = f"https://api.modrinth.com/v2/project/{project_id}/version"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    @staticmethod
    def get_project_info(project_id: str):
        response = requests.get(f"https://api.modrinth.com/v2/project/{project_id}")
        response.raise_for_status()
        return response.json()