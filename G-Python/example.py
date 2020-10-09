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


print(ext.request_flags())

def on_walk(message):
    # packet = message.packet
    # x = packet.read_int()
    # y = packet.read_int()
    (x, y) = message.packet.read('ii')
    print("Walking to x:{}, y={}".format(x, y))
    ext.send_to_server(HPacket(1843, 1)) # wave

    # 2 ways of sending packets from string representations
    ext.send_to_client(HPacket.from_string('{l}{u:1411}{i:0}{s:"hi"}{i:0}{i:23}{i:0}{i:2}', ext))
    ext.send_to_client(HPacket.from_string('[0][0][0][26][5][131][0][0][0][0][0][2]ho[0][0][0][0][0][0][0][3][0][0][0][0][0][0][0][2]', ext))


def on_speech(message):
    (text, color, index) = message.packet.read('sii')
    message.is_blocked = (text == 'blocked')
    print("User said: {}".format(text))


def all_packets(message):
    packet = message.packet
    s = packet.g_string(ext)
    expr = packet.g_expression(ext)
    print('{} --> {}'.format(message.direction.name, s))
    if expr != '':
        print(expr)
    print('------------------------------------')


ext.intercept(Direction.TO_SERVER, on_walk, 3536)
ext.intercept(Direction.TO_SERVER, on_speech, 2547)

ext.intercept(Direction.TO_CLIENT, all_packets)
ext.intercept(Direction.TO_SERVER, all_packets)


packet = HPacket(1231, "hi", 5, "old", False, True, "lol")
result = packet.g_expression(ext)
print(result)