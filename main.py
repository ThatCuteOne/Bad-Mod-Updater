import asyncio
from aioconsole import ainput
import asyncio
import json
import os
from pathlib import Path
import tracemalloc
import zipfile

import core.modrinth_api as api

import toml
tracemalloc.start()
from core.mod_manager import ModEntry
import core.mod_manager as mod_manager
import core.settings as settings



async def get_user_confirmation(prompt: str = "Confirm? (yes/no): ") -> bool:
    while True:
        user_input = (await input(prompt + "\n")).strip().lower()
        if user_input in ('y', 'yes'):
            return True
        elif user_input in ('n', 'no'):
            return False
        print("Please answer with 'yes' or 'no'")

async def get_metadata_from_jar(file) -> dict:
            with zipfile.ZipFile(settings.MODS_DIRECTORY / file, 'r') as jar:
            # detect mod loader
                # fabric
                if "fabric.mod.json" in jar.namelist():
                    with jar.open("fabric.mod.json") as f:
                        data = json.load(f)
                        return {
                            'id': data["id"],
                            'name': data["name"],
                        }
                # neoforge
                elif "META-INF/neoforge.mods.toml" in jar.namelist():
                    with jar.open("META-INF/neoforge.mods.toml") as f:
                        data = toml.loads(f.read().decode('utf-8'))
                        return {
                            'id': data['mods'][0]['modId'],
                            'name': data['mods'][0]['displayName'],
                        }
                # forge
                elif "META-INF/mods.toml" in jar.namelist():
                    with jar.open("META-INF/mods.toml") as f:
                        data = toml.loads(f.read().decode('utf-8'))
                        return {
                            'id': data['mods'][0]['modId'],
                            'name': data['mods'][0]['displayName'],
                        }
            
                raise ValueError("Unsupported mod format")

async def detect_version(hash,versions) -> dict:
    for v in versions:
        for f in v.get('files'):
            if f.get('primary') == True:
                if f['hashes'].get("sha512") == hash:
                    return {
                        "url": f.get("url"),
                        'dependencies': [
                            d.get("project_id")
                            for d in v['dependencies']
                            if d.get('dependency_type') == "required"
                        ]
                    }
    return None


async def _get_data_backup(mod:ModEntry):
    '''
    Tries to get the Version data from modrinth by extracting data from the file directly
    '''
    mod.jar_metadata = await get_metadata_from_jar(mod.filename)
    try:
         # get version data from direct link(using id specified in jar)
         response = await api.request(f"https://api.modrinth.com/v2/project/{mod.jar_metadata.get("id")}")
         versions = await api.request(f"https://api.modrinth.com/v2/project/{response.get("id")}/version")
         await mod.get_data_from_dict(await detect_version(await mod_manager.calc_hash(mod.filename),versions))
         await mod.get_data_from_dict(response)
         mod.mod_name = response.get("title")
         mod.versions = versions
         mod.project_id = response.get("id")
    except:
        try:
            # get version data via modrinth search
            response = await api.search(mod.jar_metadata.get("name"))
            if response.get('total_hits') == 0:
                return False
            result = response.get('hits')[0]
            versions = await api.request(f"https://api.modrinth.com/v2/project/{result.get('project_id')}/version")
            await mod.get_data_from_dict(await detect_version(await mod_manager.calc_hash(mod.filename),versions))
            await mod.get_data_from_dict(result)
            mod.mod_name = result.get("title")
            mod.versions = versions
        except Exception as e:
           # TODO make this stuffy do stuff
            #if not settings.NO_PROMPT:
            # if await get_user_confirmation(f"Couldn't automatically detect installed version for file {file}, do you want to proceed with installing '{data.get("mod_name")}' Confirm? (yes/no)"):
            return False
            raise TypeError

    
    return True

async def process_file(file,index):
    mod = ModEntry()
    mod.filename = file
    mod.index = index
    mod.hash = await mod_manager.calc_hash(file)
    for e in index.data:
        if e.get("hash") == mod.hash:
            await mod.get_data_from_dict(e)
            break
    else:
        if not await _get_data_backup(mod):
            return
            
    # replace old index entry with new one
    await mod.remove_from_index()
    await mod.write_to_index()
    if not mod.versions:
        mod.versions = await api.request(f"https://api.modrinth.com/v2/project/{mod.project_id}/version")
    await update_mod(mod)

async def update_mod(mod:ModEntry):
    print(mod.mod_name)
    # filter versions
    compatible_versions = []
    for v in mod.versions:
        if settings.MINECRAFT_VERSION in v["game_versions"] and settings.MOD_LOADER in v["loaders"]:
            compatible_versions.append(v)
    if not compatible_versions:
        return False
    # get newest by publishing date
    newest_version = sorted(compatible_versions, key=lambda x: x["date_published"],reverse=True)[0]

    for f in newest_version.get('files'):
        if f.get('primary') == True:
            if f['hashes'].get("sha512") == mod.hash:
                return True
            else:
                os.remove(settings.MODS_DIRECTORY / Path(mod.filename))
                await api.download_file(f.get('url'),settings.MODS_DIRECTORY / f.get('filename'))
                return True

async def main():
    index = mod_manager.index()
    files = set(f for f in os.listdir(settings.MODS_DIRECTORY) if f.endswith('.jar'))
    tasks = [process_file(file,index) for file in files]
    await asyncio.gather(*tasks)
    index.save()

if __name__ == "__main__":
    os.chdir(settings.MODS_DIRECTORY)
    asyncio.run(main())


