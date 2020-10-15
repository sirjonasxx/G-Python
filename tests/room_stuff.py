import sys

from gextension import Extension
from htools import RoomFurni, RoomUsers

extension_info = {
    "title": "Room stuff",
    "description": "G-Python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv)
ext.start()

room_furni = RoomFurni(ext)
room_furni.on_floor_furni_load(lambda furni: print("Found {} floor furniture in room".format(len(furni))))
room_furni.on_wall_furni_load(lambda furni: print("Found {} wall furniture in room".format(len(furni))))

room_users = RoomUsers(ext)
room_users.on_new_users(lambda users: print(list(map(str, users))))
