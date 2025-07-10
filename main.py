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



# async def get_user_confirmation(prompt: str = "Confirm? (yes/no): ") -> bool:
#     while True:
#         user_input = (await input(prompt + "\n")).strip().lower()
#         if user_input in ('y', 'yes'):
#             return True
#         elif user_input in ('n', 'no'):
#             return False
#         print("Please answer with 'yes' or 'no'")

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

async def detect_version(data,versions) -> dict:
    for v in versions:
        for f in v.get('files'):
            if f.get('primary') == True:
                if f['hashes'].get("sha512") == data.get('hash'):
                    data['url'] = f.get("url")
                    data['dependencies'] = [
                        d.get("project_id")
                        for d in v['dependencies']
                        if d.get('dependency_type') == "required"
                    ]
                    return data
    raise LookupError


async def _get_data_backup(file):
    '''
    Tries to get the Version data from modrinth by extracting data from the file directly
    '''
    file_data = await get_metadata_from_jar(file)
    try:
         # get version data from direct link(using id specified in jar)
         response = await api.request(f"https://api.modrinth.com/v2/project/{file_data.get("id")}")
         data = {
             "color" : response.get("color"),
             "project_id": response.get("id"),
             "mod_name" : response.get("title"),
             "filename": str(file)
         } 
         data["hash"] = await mod_manager.calc_hash(file)
         versions = await api.request(f"https://api.modrinth.com/v2/project/{data.get('project_id')}/version")
         data  = await detect_version(data,versions )
         
    except:
        try:
            # get version data via modrinth search
            response = await api.search(file_data.get("name"))
            if response.get('total_hits') == 0:
                return False
            response = response.get('hits')[0]
            data = {
             "color" : response.get("color"),
             "project_id": response.get("project_id"),
             "mod_name" : response.get("title"),
             "filename": str(file)
         }
            data["hash"] = await mod_manager.calc_hash(file)
            versions = await api.request(f"https://api.modrinth.com/v2/project/{data.get('project_id')}/version")
            data = await detect_version(data,versions)
        except LookupError:
            if settings.AUTOINSTALL_SEARCH == False:
                raise Exception

            # TODO make this stuffy do stuff
            # if await get_user_confirmation(f"Couldn't automatically detect installed version for file {file}, do you want to proceed with installing '{data.get("mod_name")}' Confirm? (yes/no)"):
            #     data = {
            #         "color" : response.get("color"),
            #         "project_id": response.get("project_id"),
            #         "mod_name" : response.get("title"),
            #         "filename": str(file)
            #     }
            pass
        except Exception as e:
            print(e)
            raise TypeError


    
    return ModEntry(data), versions

async def process_file(file,index):
    versions = None
    data = None
    file_hash = await mod_manager.calc_hash(file)
    for e in index.data:
        if e.get("hash") == file_hash:
            data = e
    if data:
        mod = ModEntry(data)
    else:
        try:
            mod, versions = await _get_data_backup(file)
        except TypeError:
            return False
    await mod.remove_from_index(index)
    await mod.write_to_index(index)
    if not versions:
        versions = await api.request(f"https://api.modrinth.com/v2/project/{mod.project_id}/version")
    print(f"{mod.mod_name} \n {mod.color} \n{mod.dependency}\n{mod.filename}\n{mod.hash}\n{mod.project_id}\n{mod.url}")
    await update_mod(mod,versions)

async def update_mod(mod:ModEntry,versions):
    # filter versions
    compatible_versions = []
    for v in versions:
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


