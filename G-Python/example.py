import sys

from gextension import Extension
from hmessage import Direction, HMessage
from hpacket import HPacket

extension_info = {
    "title": "G-Python",
    "description": "Test python extension",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv)
ext.on_event('double_click', lambda: print('Extension has been clicked'))
ext.on_event('init', lambda: print('Initialized with g-earth'))
ext.on_event('connection_start', lambda: print('Connected with: {}:{}'.format(ext.connection_info['host'], ext.connection_info['port'])))
ext.on_event('connection_end', lambda: print('Connection ended'))

ext.start()


def on_walk(message):
    packet = message.packet
    x = packet.read_int()
    y = packet.read_int()
    print("walking to x:{}, y={}".format(x, y))
    message.is_blocked = True

    ext.send_to_server(
        HPacket(ext, 2547, "hello", 0, 0)
    )


ext.intercept(Direction.TO_SERVER, on_walk, 3536)
