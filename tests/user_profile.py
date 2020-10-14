import sys

from gextension import Extension
from hmessage import Direction, HMessage
from hpacket import HPacket
import hparsers

extension_info = {
    "title": "User profile",
    "description": "G-Python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv)
ext.start()

def user_profile(message):
    profile = hparsers.HUserProfile(message.packet)
    print(profile)


ext.intercept(Direction.TO_CLIENT, user_profile, 1376)  # UserProfile
