import sys

from gextension import Extension
from hmessage import Direction, HMessage
from hpacket import HPacket
import hparsers

extension_info = {
    "title": "Room stuff",
    "description": "G-Python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv)
ext.start()

room_users = {}


def load_room_users(message):
    users = hparsers.HEntity.parse(message.packet)
    for user in users:
        room_users[user.index] = user

    print(list(map(str, users)))


def clear_room_users(_):
    room_users.clear()


floor_furni = []
wall_furni = []


def floor_furni_load(message):
    global floor_furni
    floor_furni = hparsers.HFloorItem.parse(message.packet)

    print("Found {} floor furniture in room".format(len(floor_furni)))


def wall_furni_load(message):
    global wall_furni
    wall_furni = hparsers.HWallItem.parse(message.packet)

    print("Found {} wall furniture in room".format(len(wall_furni)))


ext.intercept(Direction.TO_CLIENT, load_room_users, 2029)       # RoomUsers
ext.intercept(Direction.TO_CLIENT, clear_room_users, 3968)      # RoomModel (clear users / new room entered)

ext.intercept(Direction.TO_CLIENT, floor_furni_load, 2944)      # RoomFloorItems
ext.intercept(Direction.TO_CLIENT, wall_furni_load, 703)        # RoomWallItems
