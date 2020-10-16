import sys

from g_python.gextension import Extension
from g_python.htools import Inventory

extension_info = {
    "title": "Inventory items",
    "description": "g_python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv, {"use_click_trigger": True})
ext.start()

inventory = Inventory(ext)


def request_inventory():
    print("Requesting inventory")
    inventory.request()


def on_inventory_load(items):
    print("Found {} items!".format(len(items)))


ext.on_event('double_click', request_inventory)
inventory.on_inventory_load(on_inventory_load)
