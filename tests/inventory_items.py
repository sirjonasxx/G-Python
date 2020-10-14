import sys

from gextension import Extension
from hmessage import Direction, HMessage
from hpacket import HPacket
import hparsers

extension_info = {
    "title": "Inventory items",
    "description": "G-Python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv, {"use_click_trigger": True})
ext.start()

loaded = False
is_loading = False
inventory_items = []
inventory_items_buffer = []

def user_inventory_load(message : HMessage):
    packet = message.packet
    total, current = packet.read('ii')
    packet.reset()

    items = hparsers.HInventoryItem.parse(packet)

    if current == 0:            # fresh inventory load
        inventory_items_buffer.clear()
        is_loading = True

    inventory_items_buffer.extend(items)
    print("Loading inventory.. ({}/{})".format(current + 1, total))

    if current == total - 1:    # latest packet
        is_loading = False
        loaded = True
        inventory_items = list(inventory_items_buffer)
        inventory_items_buffer.clear()

        print("Found {} items!".format(len(inventory_items)))


def request_inventory():
    print("Requesting inventory")
    ext.send_to_server(HPacket(2499))       # RequestInventoryItems


ext.on_event('double_click', request_inventory)
ext.intercept(Direction.TO_CLIENT, user_inventory_load, 331)   # InventoryItems