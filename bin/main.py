import os
import index

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)
os.makedirs("../mods", exist_ok=True)
os.chdir("../mods")

minecraft_version = "1.21.6"
loader = "fabric"

def get_mod_files():
    return [f for f in os.listdir() if f.endswith('.jar')]

def update_mod(file_path: str, dex: index.Modindex) -> bool:
    """Update a single mod file."""
    try:
        version = index.VersionEntry(file_path, loader, minecraft_version)
        if not version.version:
            print(f"No version found for {file_path}")
            return False
        print(f"Updating Mod: {version.modname}")
        # Remove old file
        dex.remove(file_path)
        os.remove(file_path)
        
        # Download new version
        version.download_mod()
        
        # Update index
        dex.write(version.version, version.modname)
        
        return True
        
    except Exception as e:
        print(f"Failed to update {file_path}: {e}")
        return False

def mod_updater():
    dex = index.Modindex()
    success_count = 0
    mod_files = get_mod_files()
    if not mod_files:
        print("No mod files found to update")
        return
    for mod_file in mod_files:
        if update_mod(mod_file, dex):
            success_count += 1

if __name__ == "__main__":
    mod_updater()