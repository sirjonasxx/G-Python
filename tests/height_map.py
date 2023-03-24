import sys

from g_python.gextension import Extension
from g_python.hmessage import Direction
from g_python.hparsers import HHeightMap

extension_info = {
    "title": "Heightmap",
    "description": "just an example",
    "version": "1.0",
    "author": "WiredSPast"
}

ext = Extension(extension_info, sys.argv)
ext.start()


def on_height_map(msg):
    heightmap = HHeightMap(msg.packet)
    print(heightmap.get_tile(10, 10))


ext.intercept(Direction.TO_CLIENT, on_height_map, 'HeightMap')
