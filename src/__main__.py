#!/usr/bin/env python3
import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import os
import logging
import zipfile
import networking
import aiofiles
import toml

import config

logging.basicConfig(level=logging.INFO,format='[%(asctime)s] [%(name)s/%(levelname)s] %(message)s',datefmt='%H:%M:%S')
logger = logging.getLogger("Mod Updater")

async def calcsha512(file):
    async with aiofiles.open(file,"rb") as f:
        content = await f.read()
        return hashlib.sha512(content).hexdigest()

async def get_modID_from_file(file):
    with zipfile.ZipFile(file, 'r') as jar:
    # detect mod loader
        if "fabric.mod.json" in jar.namelist():
            with jar.open("fabric.mod.json") as f:
                data = json.load(f)
                return data["id"]
        elif "META-INF/neoforge.mods.toml" in jar.namelist():
            with jar.open("META-INF/neoforge.mods.toml") as f:
                data = toml.loads(f.read().decode('utf-8'))
                return data['mods'][0]['modId']
        elif "META-INF/mods.toml" in jar.namelist():
            with jar.open("META-INF/mods.toml") as f:
                data = toml.loads(f.read().decode('utf-8'))
                return data['mods'][0]['modId']
        else:
            raise ValueError(f"Unsupported mod format: {file}")
        

class ModHandler():
    def __init__(self):
        self.mods: list = []
        self.new_index:list = []
        self.dependiencies:list = []

handler = ModHandler()

@dataclass
class DownloadTask():
    url : str
    filename: str
    old_mod : str | None

@dataclass
class Mod():
    hashsha512 : str
    modID : str
    filename : str = None
    versions: list = field(default_factory=list)
    version: str = None
    target_version:str = None
    dependency:bool = False
    parents:list = field(default_factory=list)
    download : DownloadTask = field(default_factory=lambda: DownloadTask(None, None, None))

async def convert_mod_to_indexEntry(mod:Mod)-> dict:
    return {
        "modID": mod.modID,
        "sha512" : mod.hashsha512,
        "version": mod.version
    }

async def process_search_result(hit:dict,mod:Mod):
    versions = await networking.modrinth_api_endpoint_request(f"project/{hit.get("project_id")}/version")
    try: 
        version = await hashmatch_in_versions(mod.hashsha512,versions)
        mod.modID = hit.get("project_id")
        mod.version = version.get("id")
        return True
    except Exception:
        return False


async def search_in_index(project_id:str):
    for entry in config.Index.indexlist:
        if entry.get("modID") == project_id:
            return entry


async def get_mod_files(directory_path):
    with os.scandir(directory_path) as entries:
        for entry in entries:
            if entry.is_file() and entry.name.endswith(".jar"):
                yield entry

async def hashmatch_in_versions(hash:str,versions:list):
    for v in versions:
        for f in v.get("files"):
            if f.get("primary") and f.get("hashes").get("sha512") == hash:
                return v
    raise Exception(f"No version Found for hash: {hash}")

async def discover_mod(file:os.DirEntry):
    mod = Mod(hashsha512 = (await calcsha512(file)),filename=file.name,modID=None,)
    for indexEntry in config.Index.indexlist:
        if indexEntry.get("sha512") == mod.hashsha512:
            logger.info(f"Mod found in index for file {file.name}")
            mod.modID = indexEntry.get("modID")
            mod.version = indexEntry.get("versionID")
            handler.mods.append(mod)
            return
    else:
        try:
            ID = await get_modID_from_file(file)
            try:
                mod.versions = await networking.modrinth_api_endpoint_request(f"project/{ID}/version")
                version = (await hashmatch_in_versions(mod.hashsha512,mod.versions))
                mod.modID = version.get("project_id")
                mod.version = version.get("id")
                handler.mods.append(mod)
            except Exception:
                hits = await networking.modrinth_api_endpoint_request("search",
                            params={
                                    "query": f"{ID}",
                                    "index": "relevance",
                                    "limit": config.SEARCH_DEPTH,
                                    "facets": f"""[["project_type:mod"],["categories:{config.LOADER}"],["versions:{config.MINECRAFT_VERSION}"]]"""
                  }
                )
                if hits.get("total_hits") <= 0:
                    logger.warning(f"Could not discover mod for file: {file.name}")
                    return
                search_tasks= []
                for hit in hits["hits"]:
                    search_tasks.append(process_search_result(hit,mod))
                res = await asyncio.gather(*search_tasks)
                if True in res:
                    handler.mods.append(mod)
                else:
                    logger.warning(f"Could not discover mod for file: {file.name}")
                    return
        except ValueError as e:
            logger.error(e)

async def process_dependency(dependency:dict):
        mod = Mod(
                None,
                dependency.get("project_id"),
                dependency=True,
                target_version=dependency.get("version_id")
            )
        if dependency.get("dependency_type") == "required":
            entry = await search_in_index(dependency.get("project_id"))
            if entry is not None:
                mod.hashsha512 = entry.get("sha512")
                if dependency.get("version_id") is not None:
                        if entry.get("version") == dependency.get("version_id"):
                            return None
                        else:
                            mod.hashsha512 = entry.get("sha512")
                            return mod
                else:
                    return mod
            else:
                return mod
        else:
            return None

async def get_newest_version(versions):
    """
    returns newest compatible version
    """
    compatible_versions = []
    for v in versions:
        if config.MINECRAFT_VERSION in v.get("game_versions") and config.LOADER in v.get("loaders") and v.get("version_type") in config.VERSION_TYPES:
            compatible_versions.append(v)
    
    compatible_versions = sorted(compatible_versions, key=lambda x: x["date_published"],reverse=True)
    return compatible_versions[0]


async def fetch_dependencies():
    dependency_tasks= []
    current_depends = handler.dependiencies
    for d in current_depends:
        dependency_tasks.append(get_download_link(d))
        handler.dependiencies.pop(0)
        handler.mods.append(d)
    
    await asyncio.gather(*dependency_tasks)



async def get_download_link(mod:Mod):
    if mod.target_version:
        newest_version = await networking.modrinth_api_endpoint_request(f"project/{mod.modID}/version/{mod.target_version}")
    else:
        if not mod.versions:
            mod.versions = await networking.modrinth_api_endpoint_request(f"project/{mod.modID}/version")
        try:
            newest_version = await get_newest_version(mod.versions)
        except Exception as e:
            logger.error(f"No Compatible Version Found for mod {mod.modID}")
            handler.mods.remove(mod)
            handler.new_index.append(await convert_mod_to_indexEntry(mod))
            return 

    for f in newest_version.get("files"):
        if f.get("primary"):
            file = f
            break
    dependency_tasks = []
    for dependency in newest_version.get("dependencies"):
            dependency_tasks.append(process_dependency(dependency))
        
    dependencies = await asyncio.gather(*dependency_tasks)
    
    try:
        dependencies.remove(None)
    except:  # noqa: E722
        pass
    handler.dependiencies += dependencies



    if mod.hashsha512 == file.get("hashes").get("sha512"):
        handler.mods.remove(mod)
        handler.new_index.append(await convert_mod_to_indexEntry(mod))
    else:
        mod.download = DownloadTask(
                file.get("url"),
                file.get("filename"),
                mod.filename
            )
async def download_jar(mod:Mod):
    task = mod.download
    if await networking.download_jar(task.url,task.filename):
        if task.filename != task.old_mod and task.old_mod is not None:
            logger.info(f"Deleting {task.old_mod}")
            os.remove(f"./mods/{task.old_mod}")

        handler.new_index.append(await convert_mod_to_indexEntry(mod))

async def write_to_index():
    with open(config.MODS_DIR/".modIndex.json","w") as f:
        json.dump(handler.new_index,f,indent=2)


async def main():
    os.makedirs(config.MODS_DIR,exist_ok=True)
    logger.info("Discovering mods")
    
    discover_tasks = []

    async for f in get_mod_files(config.MODS_DIR):
        discover_tasks.append(discover_mod(f))
    
    await asyncio.gather(*discover_tasks)
            
    
    
    # get download tasks
    
    tasks = []
    for m in handler.mods:
        tasks.append(get_download_link(m))

    await asyncio.gather(*tasks)
    await fetch_dependencies()

    downloads = []
    for m in handler.mods:
        downloads.append(download_jar(m))
    
    await asyncio.gather(*downloads)

    await write_to_index()


    

    



if __name__ == "__main__":
    asyncio.run(main())