from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot import on_command
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="hello",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

weather = on_command("hello")
status = on_command("status")

@weather.handle()
async def handle_function():
    await weather.finish("world")

@status.handle()
async def return_status():
    await status.finish("Bot 还活着")