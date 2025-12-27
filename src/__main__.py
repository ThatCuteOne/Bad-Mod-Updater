#!/usr/bin/env python3
import asyncio
from dataclasses import dataclass, field
import hashlib
import os
import logging
import networking
import aiofiles

import config

logging.basicConfig(level=logging.INFO,format='[%(asctime)s] [%(name)s/%(levelname)s] %(message)s',datefmt='%H:%M:%S')
logger = logging.getLogger("Mod Updater")

async def calcsha512(file):
    async with aiofiles.open(file,"rb") as f:
        content = await f.read()
        return hashlib.sha512(content).hexdigest()
        

class ModHandler():
    def __init__(self):
        self.mods: list = []
        self.hashes:list = []
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
    download : DownloadTask = field(default_factory=lambda: DownloadTask)



async def get_mod_files(directory_path):
    with os.scandir(directory_path) as entries:
        for entry in entries:
            if entry.is_file() and entry.name.endswith(".jar"):
                yield entry

async def discover_mod(file:os.DirEntry):
    mod = Mod(hashsha512 = (await calcsha512(file)),filename=file.name,modID=None)
    handler.hashes.append(mod.hashsha512)
    return mod



async def get_download_link(mod:Mod,data:dict):
    new_version = data[mod.hashsha512]
    if not new_version:
        return
    for f in new_version["files"]:
        if f["primary"]:
            modfile = f
            break
    if modfile["hashes"]["sha512"] == mod.hashsha512:
        return
    mod.download = DownloadTask(
        filename=modfile["filename"],
        url=modfile["url"],
        old_mod=mod.filename
    )
    

async def download_jar(mod:Mod):
    task = mod.download
    if isinstance(task,DownloadTask):
        if await networking.download_jar(task.url,task.filename):
            if task.filename != task.old_mod and task.old_mod is not None:
                logger.info(f"Deleting {task.old_mod}")
                os.remove(f"./mods/{task.old_mod}")


async def main():
    os.makedirs(config.MODS_DIR,exist_ok=True)
    logger.info("Discovering mods")
    
    async for f in get_mod_files(config.MODS_DIR):
        handler.mods.append(await discover_mod(f))
                
    # get download tasks
    data = await networking.modrinth_api_post_newest_versions(handler.hashes)



    tasks = []
    for m in handler.mods:
        tasks.append(get_download_link(m,data))

    await asyncio.gather(*tasks)

    downloads = []
    for m in handler.mods:
        downloads.append(download_jar(m))
    
    await asyncio.gather(*downloads)

    

    



if __name__ == "__main__":
    asyncio.run(main())