import sys

import hparsers
from gextension import Extension
from hmessage import Direction

extension_info = {
    "title": "User profile",
    "description": "g_python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv)
ext.start()


def user_profile(message):
    profile = hparsers.HUserProfile(message.packet)
    print(profile)


ext.intercept(Direction.TO_CLIENT, user_profile, 'UserProfile')  # UserProfile
