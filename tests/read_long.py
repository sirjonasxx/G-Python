import sys

from g_python.gextension import Extension
from g_python.hmessage import Direction

extension_info = {
    "title": "long example LOL",
    "description": "g_python test",
    "version": "1.0",
    "author": "Hellsin6"
}

ext = Extension(extension_info, sys.argv)
ext.start()


def StuffDataUpdate(message):
    (x, y, z) = message.packet.read('lis')
    print('StuffDataUpdate', x, y, z)

    furni_id = message.packet.read_long(6)
    print('read_long', furni_id)


ext.intercept(Direction.TO_CLIENT, StuffDataUpdate, 88)