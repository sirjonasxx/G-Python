import sys

from g_python.gextension import Extension
from g_python.hmessage import Direction

extension_info = {
    "title": "Extension console",
    "description": "just an example",
    "version": "2.0",
    "author": "Lande"
}

ext = Extension(extension_info, sys.argv)
ext.start()


def speech_out(msg):
    text, bubble, id = msg.packet.read('sii')

    ext.write_to_console(f"Message send -> message : '{text}', bubble : {bubble}")


def speech_in(msg):
    index, text, _, bubble, _, id = msg.packet.read('isiiii')

    ext.write_to_console(f"Message receive -> index : {index}, message : {text}, bubble : {bubble}", color='blue', mention_title=False)


ext.intercept(Direction.TO_SERVER, speech_out, 'Chat')
ext.intercept(Direction.TO_CLIENT, speech_in, 'Chat')

'''
    mention_title=True -> Show the name of the extension before the message ( True by default )
    color='black' -> Color of the text ( Black by default )
'''