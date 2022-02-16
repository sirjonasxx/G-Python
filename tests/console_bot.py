import sys

from g_python.gbot import ConsoleBot, HBotProfile
from g_python.gextension import Extension

extension_info = {
    "title": "Console Bot",
    "description": "",
    "version": "1.0",
    "author": "b@u@o",
}

ext = Extension(extension_info, sys.argv)
ext.start()


def ping():
    bot.send("Pong!")


# you don't need to initialize settings, just if you want to customize
settings = HBotProfile(username="Custom Bot", motto="Custom Motto")

bot = ConsoleBot(ext, prefix=":", bot_settings=settings)
bot.add_command("ping", ping)
