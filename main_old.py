
import requests
import json
import os
import zipfile
from tqdm import tqdm
import time
import toml


abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.makedirs("./mods", exist_ok=True)
os.chdir(dname+"/mods")

mod_name = "fabric api"
loader = "fabric"
minecraft_version = "1.21.4"


def ask_yes_no(question):
    while True:
        answer = input(f"{question} (yes/no): ").strip().lower()
        if answer in {"yes", "y"}:
            return True
        elif answer in {"no", "n"}:
            return False
        else:
            print("Please enter 'yes' or 'no'.")


def search_for_mod_by_name(modname):
        
    url = "https://api.modrinth.com/v2/search"
    params = {
            "query": f"{modname}",
            "index": "relevance",
            "limit": 5,
            "facets": f"""
            [
                [
                    "project_type:mod"
                ],
                [
                    "categories:{loader}"
                ],
                [
                    "versions:{minecraft_version}"
                ]
            ]
            """
    }

    response = requests.get(url, params)
    print(f"Seaching for {modname}...")
    response.raise_for_status()
    results = response.json()["hits"]
    if not results:
        print( f"No compatible versions found for Minecraft {minecraft_version} and {loader} loader for Mod: '{mod_name}'")
        return None
    else:
        return results[0]
def get_newest_version(id):
    url = f"https://api.modrinth.com/v2/project/{id}/version"
    response = requests.get(url)
    response.raise_for_status()
    results = response.json()

    compatible_versions = []

    for version in results:
        if minecraft_version in version["game_versions"]:
            if loader in version["loaders"]:
                compatible_versions.append(version)
    if not compatible_versions:
            print( f"No compatible versions found for Minecraft {minecraft_version} and {loader} loader for Mod '{mod_name}'")
            return None
    else:
        return max(compatible_versions, key=lambda x: x["date_published"])

def download_mod(url,filename):
    response = requests.get(url)
    response.raise_for_status()
    with open(filename, "wb") as f:
        f.write(response.content)
def write_to_index(version):
    global mod_name
    try:
        with open('.index.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
         data = []
    version = version.copy()
    version['mod_name'] = mod_name
    data.append(version)
    with open('.index.json', 'w') as f:
        json.dump(data, f, indent=2)

def get_new_mod():
    mod = search_for_mod_by_name(mod_name)
    print("Found mod:"+ mod["title"])
    mod_version = get_newest_version(mod["project_id"])
    download_mod(mod_version["files"][0]["url"],mod_version["files"][0]["filename"])
    write_to_index(mod_version)

def search_in_index(file):
    try:
        with open('.index.json', 'r', encoding='utf-8') as f:
            mod_versions = json.load(f)
    except FileNotFoundError:
         data = []
         with open('.index.json', 'w') as f:
                json.dump(data, f, indent=2)
         return None , None
    for mod_version in mod_versions:
         for file_entry in mod_version["files"]:
            if str(file) in file_entry["filename"]:
                return mod_version,mod_version["mod_name"]
    return None , None
    
    
def remove_from_index(version):
    with open('.index.json', 'r', encoding='utf-8') as f:
        mod_versions = json.load(f)
    target_hash = version["files"][0]["hashes"]["sha512"]
    updated_versions = [
            mod_version for mod_version in mod_versions
            if not any(
                file_entry["hashes"]["sha512"] == target_hash
                for file_entry in mod_version.get("files", [])
            )
        ]
    with open('.index.json', 'w', encoding='utf-8') as f:
        json.dump(updated_versions, f, indent=2)

def get_modname(file):
    global mod_name
    with zipfile.ZipFile(str(file), 'r') as jar:
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
    return None





def update_mods():
    for file in os.listdir():
        if file.endswith(".jar"):
            global mod_name
            version_in_index, mod_name = search_in_index(file)
            if not version_in_index:
                 print(f"file {str(file)} couldnt be found in index")
                 print("Extracting mod name from jar and searching on Modrinth...")
                 mod = search_for_mod_by_name(get_modname(file))
                 if not mod:
                     print(f"No Mod could be found for file {str(file)}")
                 else:
                     print(f"Mod Found!: {mod["title"]}")
                     if ask_yes_no("Do you want to Download it?"):
                        mod_version = get_newest_version(mod["project_id"])
                        os.remove(file)
                        download_mod(mod_version["files"][0]["url"],mod_version["files"][0]["filename"])
                        write_to_index(mod_version)
                     else:
                        print("Skipping..")

            else:
                newest_version = get_newest_version(version_in_index["project_id"])
                if not newest_version:
                    pass
                elif version_in_index["files"][0]["hashes"]["sha512"] == newest_version["files"][0]["hashes"]["sha512"]:
                    print(f"Newest Version for Mod '{mod_name} {newest_version["version_number"]}' is already installed")
                else:
                    print(f"Found Newer Version: {newest_version["version_number"]} for Mod {version_in_index["name"]}")
                    print("Installing...")
                    os.remove(file)
                    download_mod(newest_version["files"][0]["url"],newest_version["files"][0]["filename"])
                    remove_from_index(version_in_index)
                    write_to_index(newest_version)
    print("Done all mods are Up To Date!")




if __name__ == "__main__":
    update_mods()

    #get_new_mod()
