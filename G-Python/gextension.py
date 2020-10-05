import socket
import threading
from time import sleep
from enum import Enum
from hpacket import HPacket
from hmessage import HMessage


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


def fill_settings(settings, defaults):
    if settings is None:
        return defaults.copy()

    settings = settings.copy()
    for key, value in EXTENSION_SETTINGS_DEFAULT.items():
        if key not in settings or settings[key] is None:
            settings[key] = value

    return settings


def get_argument(args, flags):
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
        extension_settings = fill_settings(extension_settings, EXTENSION_SETTINGS_DEFAULT)

        if get_argument(args, PORT_FLAG) is None:
            raise Exception('Port was not specified (argument example: -p 9092)')

        for key in EXTENSION_INFO_REQUIRED_FIELDS:
            if key not in extension_info:
                raise Exception('Extension info error: {} field missing'.format(key))

        port = int(get_argument(args, PORT_FLAG))
        file = get_argument(args, FILE_FLAG)
        cookie = get_argument(args, COOKIE_FLAG)

        self.extension_info = extension_info
        self.port = port
        self.file = file
        self.cookie = cookie
        self.extension_settings = extension_settings
        self.is_closed = True

        self.connection_info = None

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
            try:
                packet = read_packet()
            except:
                return
            print(packet)

            if packet.headerId() == INCOMING_MESSAGES.INFO_REQUEST.value:
                response = HPacket(self, OUTGOING_MESSAGES.EXTENSION_INFO.value)
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
            elif packet.headerId() == INCOMING_MESSAGES.CONNECTION_START.value:
                host = packet.read_string()
                port = packet.read_int()
                hotel_version = packet.read_string()
                harble_messages_path = packet.read_string()
                self.connection_info = {'host': host, 'port': port, 'hotel_version': hotel_version,
                                        'harble_messages_path': harble_messages_path}

                # callback
            elif packet.headerId() == INCOMING_MESSAGES.CONNECTION_END.value:
                # callback
                self.connection_info = None
            elif packet.headerId() == INCOMING_MESSAGES.FLAGS_CHECK.value:
                size = packet.read_int()
                flags = [packet.read_string() for _ in range(size)]
                # callback
            elif packet.headerId() == INCOMING_MESSAGES.INIT.value:
                # callback
                self.write_to_console(
                    'G-Python extension "{}" sucessfully initialized'.format(self.extension_info['title']),
                    'green',
                    False
                )
            elif packet.headerId() == INCOMING_MESSAGES.ON_DOUBLE_CLICK.value:
                # callback
                pass
            elif packet.headerId() == INCOMING_MESSAGES.PACKET_INTERCEPT.value:
                habbo_msg_as_string = packet.read_string(head=4, encoding='iso-8859-1')
                habbo_message = HMessage.reconstruct_from_java(self, habbo_msg_as_string)
                habbo_packet = habbo_message.packet

                # callbacks

                response_packet = HPacket(self, OUTGOING_MESSAGES.MANIPULATED_PACKET.value)
                response_packet.append_string(repr(habbo_message), head=4, encoding='iso-8859-1')
                self.send_to_stream(response_packet)



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


    def write_to_console(self, text, color='black', mention_title=True):
        message = '[{}]{}{}'.format(color, (self.extension_info['title'] + ' --> ') if mention_title else '', text)
        packet = HPacket(self, OUTGOING_MESSAGES.EXTENSION_CONSOLE_LOG.value, message)
        self.send_to_stream(packet)