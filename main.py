from core.settings import check_dependencies

from core.mod_manager import ModManager

check_dependencies()

update = ModManager()
update.update_all()
