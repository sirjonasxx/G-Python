import socket

INCOMING_MESSAGES = {
    "ON_DOUBLE_CLICK": 1,
    "INFO_REQUEST": 2,
    "PACKET_INTERCEPT": 3,
    "FLAGS_CHECK": 4,
    "CONNECTION_START": 5,
    "CONNECTION_END": 6,
    "PACKET_TO_STRING_RESPONSE": 20,
    "STRING_TO_PACKET_RESPONSE": 21,
    "INIT": 7
}

OUTGOING_MESSAGES = {
    "EXTENSION_INFO": 1,
    "MANIPULATED_PACKET": 2,
    "REQUEST_FLAGS": 3,
    "SEND_MESSAGE": 4,
    "PACKET_TO_STRING_REQUEST": 20,
    "STRING_TO_PACKET_REQUEST": 21,
    "EXTENSION_CONSOLE_LOG": 98
}

EXTENSION_SETTINGS_DEFAULT = {"use_click_trigger": False, "can_leave": True, "can_delete": True}
EXTENSION_INFO_REQUIRED_FIELDS = ["title", "description", "version", "author"]

PORT_FLAG = ["--port", "-p"]
FILE_FLAG = ["--filename", "-f"]
COOKIE_FLAG = ["--auth-token", "-c"]

def fillSettings(settings, defaults):
    if settings is None:
        return defaults.copy()

    settings = settings.copy()
    for key, value in EXTENSION_SETTINGS_DEFAULT.items():
        if key not in settings or settings[key] is None:
            settings[key] = value

    return settings

def getArgument(args, flags):
    if type(flags) == str:
        flags = [flags]

    for potential_flag in flags:
        if potential_flag in args:
            index = flags.index(potential_flag)
            if 0 < index < len(args) - 1:
                return args[index + 1]

    return None


class Extension:
    def __init__(self, extension_info, args, extension_settings=None):
        extension_settings = fillSettings(extension_settings, EXTENSION_SETTINGS_DEFAULT)

        port = getArgument(args, PORT_FLAG)
        file = getArgument(args, FILE_FLAG)
        cookie = getArgument(args, COOKIE_FLAG)

        for key in EXTENSION_INFO_REQUIRED_FIELDS:
            if key not in extension_info:
                raise Exception('Extension info error: {} field missing'.format(key))

        if port is None:
            raise Exception('Port was not specified (argument example: -p 9092)')

        self.extension_info = extension_info
        self.port = port
        self.file = file
        self.cookie = cookie
        self.extension_settings = extension_settings


        gearth = socket.socket()
        gearth.connect(("127.0.0.1", self.port))

