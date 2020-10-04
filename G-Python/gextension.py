import socket
import threading
from time import sleep
from enum import Enum
from hpacket import HPacket


class INCOMING_MESSAGES(Enum):
    ON_DOUBLE_CLICK = 1
    INFO_REQUEST = 2
    PACKET_INTERCEPT = 3
    FLAGS_CHECK = 4
    CONNECTION_START = 5
    CONNECTION_END = 6
    PACKET_TO_STRING_RESPONSE = 20
    STRING_TO_PACKET_RESPONSE = 21
    INIT = 7


class OUTGOING_MESSAGES(Enum):
    EXTENSION_INFO = 1
    MANIPULATED_PACKET = 2
    REQUEST_FLAGS = 3
    SEND_MESSAGE = 4
    PACKET_TO_STRING_REQUEST = 20
    STRING_TO_PACKET_REQUEST = 21
    EXTENSION_CONSOLE_LOG = 98


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

        port = int(getArgument(args, PORT_FLAG))
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
        self.is_closed = True

        self.stream_lock = threading.Lock()

    def connection_thread(self):
        def read_packet():
            write_pos = 0

            length_buffer = bytearray(4)
            while write_pos < 4:
                n_read = self.sock.recv_into(memoryview(length_buffer)[write_pos:])
                if n_read == 0:
                    raise EOFError
                write_pos += n_read

            packet_length = int.from_bytes(length_buffer, byteorder='big')
            packet_buffer = length_buffer + bytearray(packet_length)

            while write_pos < 4 + packet_length:
                n_read = self.sock.recv_into(memoryview(packet_buffer)[write_pos:])
                if n_read == 0:
                    raise EOFError
                write_pos += n_read

            return HPacket.from_bytes(self, packet_buffer)

        while not self.is_closed:
            packet = read_packet()

            if packet.headerId() == INCOMING_MESSAGES.INFO_REQUEST:
                response = HPacket(self, OUTGOING_MESSAGES.EXTENSION_INFO)
                response\
                    .append_string(self.extension_info['title'])\
                    .append_string(self.extension_info['author'])\
                    .append_string(self.extension_info['version'])\
                    .append_string(self.extension_info['description'])\
                    .append_bool(self.extension_settings['use_click_trigger'])\
                    .append_bool(self.file is not None)\
                    .append_string('' if self.file is None else self.file) \
                    .append_string('' if self.cookie is None else self.cookie)\
                    .append_bool(self.extension_settings['can_leave'])\
                    .append_bool(self.extension_settings['can_delete'])

                self.send_to_stream(response)

    def send_to_stream(self, packet):
        self.stream_lock.acquire()
        self.sock.send(packet.bytearray)

        self.stream_lock.release()

    def start(self):
        self.sock = socket.socket()
        self.sock.connect(("127.0.0.1", self.port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.is_closed = False
        t = threading.Thread(target=self.connection_thread)
        t.start()
