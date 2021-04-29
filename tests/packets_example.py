import sys
from time import sleep

from g_python.gextension import Extension
from g_python.hmessage import Direction, HMessage
from g_python.hpacket import HPacket

extension_info = {
    "title": "Packets example",
    "description": "g_python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv, {"use_click_trigger": True})

def on_click():
    ext.send_to_server("{out:MoveAvatar}{i:5}{i:17}")


ext.on_event('double_click', on_click)
ext.start()


def on_walk(message):
    # packet = message.packet
    # x = packet.read_int()
    # y = packet.read_int()
    (x, y) = message.packet.read('ii')
    print("Walking to x:{}, y={}".format(x, y))

    # send packet to server from HPacket() object
    # ext.send_to_server(HPacket(1843, 1)) # wave
    ext.send_to_server(HPacket('RoomUserAction', 1))  # wave

    # 2 ways of sending packets from string representations
    ext.send_to_client('{l}{u:1411}{i:0}{s:"hi"}{i:0}{i:23}{i:0}{i:2}')
    ext.send_to_client(HPacket.from_string('[0][0][0][26][5][131][0][0][0][0][0][2]ho[0][0][0][0][0][0][0][3][0][0][0][0][0][0][0][2]', ext))


# intercepted async, you can't modify it
def on_speech(message):
    sleep(4)
    (text, color, index) = message.packet.read('sii')
    print("User said: {}, 4 seconds ago".format(text))

# intercepted async, but you can modify it
def on_shout(message : HMessage):
    sleep(2)
    (text, color) = message.packet.read('si')
    message.is_blocked = (text == 'blocked')  # block packet if speech equals "blocked"
    print("User shouted: {}, 2 seconds ago".format(text))
    message.packet.replace_string(6, "G - " + text)

ext.intercept(Direction.TO_SERVER, on_walk, 'RoomUserWalk')
ext.intercept(Direction.TO_SERVER, on_speech, 'RoomUserTalk', mode='async')
ext.intercept(Direction.TO_SERVER, on_shout, 'RoomUserShout', mode='async_modify')

packet = HPacket(1231, "hi", 5, "old", False, True, "lol")
result = packet.g_expression(ext)  # get G-Earth's predicted expression for the packet above
print(result)
