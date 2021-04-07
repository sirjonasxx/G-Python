import sys

from g_python.gextension import Extension
from g_python.htools import RoomFurni, RoomUsers

extension_info = {
    "title": "Room stuff",
    "description": "g_python test",
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

# current room users & furniture are always available under:
# room_furni.floor_furni        (list of HFloorItem)
# room_furni.wall_furni         (list of HWallItem)
# room_users.room_users         (list of HEntitity)

# you can also request the users/furniture with the .request() method