import sys

from g_python import hparsers
from g_python.gextension import Extension
from g_python.hmessage import Direction

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


ext.intercept(Direction.TO_CLIENT, user_profile, 'ExtendedProfile')
