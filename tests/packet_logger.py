import sys

from gextension import Extension
from hmessage import Direction

extension_info = {
    "title": "Packet Logger",
    "description": "g_python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv)
ext.start()


def all_packets(message):
    packet = message.packet
    s = packet.g_string(ext)
    expr = packet.g_expression(ext)
    print('{} --> {}'.format(message.direction.name, s))
    if expr != '':
        print(expr)
    print('------------------------------------')


ext.intercept(Direction.TO_CLIENT, all_packets)
ext.intercept(Direction.TO_SERVER, all_packets)