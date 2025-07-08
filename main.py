import asyncio
# from core.settings import check_dependencies
import tracemalloc
tracemalloc.start()
from core.mod_manager import ModManager

# check_dependencies()

update = ModManager()


async def main():
    files = update.get_mod_files()
    tasks = [update.update_mod(file) for file in files]
    await asyncio.gather(*tasks)

asyncio.run(main())


