import sys

from g_python.gextension import Extension
from g_python.hunitytools import UnityRoomUsers, UnityRoomFurni

extension_info = {
    "title": "Room stuff unity",
    "description": "g_python test",
    "version": "1.2",
    "author": "sirjonasxx & Hellsin6"
}

ext = Extension(extension_info, sys.argv)
ext.start()


def print_furnis(furnis):
    for furni in furnis:
        print("furno", furni.id, furni.type_id, furni.tile, furni.owner)


room_users = UnityRoomUsers(ext)
room_users.on_new_users(lambda users: print(list(map(str, users))))

room_furni = UnityRoomFurni(ext)
room_furni.on_floor_furni_load(lambda furnis: print_furnis(furnis))
