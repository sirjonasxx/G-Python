import sys

from gextension import Extension
from hmessage import Direction, HMessage
from hpacket import HPacket
import hparsers

extension_info = {
    "title": "Packets example",
    "description": "G-Python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv)
ext.start()


print(ext.request_flags())

def on_walk(message):
    # packet = message.packet
    # x = packet.read_int()
    # y = packet.read_int()
    (x, y) = message.packet.read('ii')
    print("Walking to x:{}, y={}".format(x, y))

    # send packet to server from HPacket() object
    ext.send_to_server(HPacket(1843, 1)) # wave

    # 2 ways of sending packets from string representations
    ext.send_to_client(HPacket.from_string('{l}{u:1411}{i:0}{s:"hi"}{i:0}{i:23}{i:0}{i:2}', ext))
    ext.send_to_client(HPacket.from_string('[0][0][0][26][5][131][0][0][0][0][0][2]ho[0][0][0][0][0][0][0][3][0][0][0][0][0][0][0][2]', ext))


def on_speech(message):
    (text, color, index) = message.packet.read('sii')
    message.is_blocked = (text == 'blocked')    # block packet if speech equals "blocked"
    print("User said: {}".format(text))


ext.intercept(Direction.TO_SERVER, on_walk, 3536)
ext.intercept(Direction.TO_SERVER, on_speech, 2547)


packet = HPacket(1231, "hi", 5, "old", False, True, "lol")
result = packet.g_expression(ext)  # get G-Earth's predicted expression for the packet above
print(result)