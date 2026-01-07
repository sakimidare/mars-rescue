import nonebot
from pathlib import Path
from nonebot.adapters.onebot.v11 import Adapter

nonebot.init()

driver = nonebot.get_driver()
adapters = nonebot.get_adapters()

driver.register_adapter(Adapter)

nonebot.load_plugin(Path("./mars_rescue/plugins/hello"))
nonebot.load_plugin(Path("./mars_rescue/plugins/image_similarity"))
nonebot.load_builtin_plugin("echo")

nonebot.run()