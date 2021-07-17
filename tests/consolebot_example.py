import sys

from g_python.gextension import Extension
from g_python_bot import ChatBot

extension_info = {
    "title": "ConsoleBot",
    "description": "Make extension ez without ui",
    "version": "1.0",
    "author": "denio4321"
}

ext = Extension(extension_info, sys.argv)
ext.start()


def pong():
    console_bot.send_message("pong")


def ping():
    console_bot.send_message("ping")


# Creates the object
console_bot = ChatBot(ext, botname="ConsoleBot-Example")
# Defines the command and the call functions
console_bot.on_command(':ping', pong)
console_bot.on_command(':pong', ping)

# Runs the bot
console_bot.start()
# Sends a welcome message once connected
console_bot.send_message("Hi! Nice to meet you! This is a example bot.")
