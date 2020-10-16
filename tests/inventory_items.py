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

inv = Inventory(ext)
# inventory items will be available under:
# inv.inventory_items           (list of HInventoryItem)


def request_inventory():
    print("Requesting inventory")
    inv.request()


def on_inventory_load(items):
    print("Found {} items!".format(len(items)))


ext.on_event('double_click', request_inventory)
inv.on_inventory_load(on_inventory_load)
