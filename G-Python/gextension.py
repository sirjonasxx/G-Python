import socket
import threading
from enum import Enum
from hpacket import HPacket
from hmessage import HMessage, Direction


# i -> implemented
# x -> todo

class INCOMING_MESSAGES(Enum):
    ON_DOUBLE_CLICK = 1             # i
    INFO_REQUEST = 2                # i
    PACKET_INTERCEPT = 3            # i
    FLAGS_CHECK = 4                 # x
    CONNECTION_START = 5            # i
    CONNECTION_END = 6              # i
    PACKET_TO_STRING_RESPONSE = 20  # x
    STRING_TO_PACKET_RESPONSE = 21  # x
    INIT = 7                        # i


class OUTGOING_MESSAGES(Enum):
    EXTENSION_INFO = 1              # i
    MANIPULATED_PACKET = 2          # i
    REQUEST_FLAGS = 3               # x
    SEND_MESSAGE = 4                # i
    PACKET_TO_STRING_REQUEST = 20   # x
    STRING_TO_PACKET_REQUEST = 21   # x
    EXTENSION_CONSOLE_LOG = 98      # i


EXTENSION_SETTINGS_DEFAULT = {"use_click_trigger": False, "can_leave": True, "can_delete": True}
EXTENSION_INFO_REQUIRED_FIELDS = ["title", "description", "version", "author"]

PORT_FLAG = ["--port", "-p"]
FILE_FLAG = ["--filename", "-f"]
COOKIE_FLAG = ["--auth-token", "-c"]


def fill_settings(settings, defaults):
    if settings is None:
        return defaults.copy()

    settings = settings.copy()
    for key, value in defaults.items():
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

        self._extension_info = extension_info
        self.__port = port
        self.__file = file
        self.__cookie = cookie
        self._extension_settings = extension_settings
        self.is_closed = True

        self.connection_info = None

        self.__stream_lock = threading.Lock()

        self.__events = {}
        self.__intercept_listeners = {Direction.TO_CLIENT: {-1:[]}, Direction.TO_SERVER: {-1:[]}}

    def __read_gearth_packet(self):
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

    def __connection_thread(self):
        while not self.is_closed:
            try:
                packet = self.__read_gearth_packet()
            except:
                if not self.is_closed:
                    self.close()
                return
            #print(packet)

            if packet.header_id() == INCOMING_MESSAGES.INFO_REQUEST.value:
                response = HPacket(self, OUTGOING_MESSAGES.EXTENSION_INFO.value)
                response\
                    .append_string(self._extension_info['title'])\
                    .append_string(self._extension_info['author'])\
                    .append_string(self._extension_info['version'])\
                    .append_string(self._extension_info['description'])\
                    .append_bool(self._extension_settings['use_click_trigger'])\
                    .append_bool(self.__file is not None)\
                    .append_string('' if self.__file is None else self.__file) \
                    .append_string('' if self.__cookie is None else self.__cookie)\
                    .append_bool(self._extension_settings['can_leave'])\
                    .append_bool(self._extension_settings['can_delete'])

                self.__send_to_stream(response)

            elif packet.header_id() == INCOMING_MESSAGES.CONNECTION_START.value:
                host = packet.read_string()
                port = packet.read_int()
                hotel_version = packet.read_string()
                harble_messages_path = packet.read_string()
                self.connection_info = {'host': host, 'port': port, 'hotel_version': hotel_version,
                                        'harble_messages_path': harble_messages_path}
                self.__raise_event('connection_start')

            elif packet.header_id() == INCOMING_MESSAGES.CONNECTION_END.value:
                self.__raise_event('connection_end')
                self.connection_info = None

            elif packet.header_id() == INCOMING_MESSAGES.FLAGS_CHECK.value:
                size = packet.read_int()
                flags = [packet.read_string() for _ in range(size)]
                # callback

            elif packet.header_id() == INCOMING_MESSAGES.INIT.value:
                self.__raise_event('init')
                self.write_to_console(
                    'G-Python extension "{}" sucessfully initialized'.format(self._extension_info['title']),
                    'green',
                    False
                )

            elif packet.header_id() == INCOMING_MESSAGES.ON_DOUBLE_CLICK.value:
                self.__raise_event('double_click')

            elif packet.header_id() == INCOMING_MESSAGES.PACKET_INTERCEPT.value:
                habbo_msg_as_string = packet.read_string(head=4, encoding='iso-8859-1')
                habbo_message = HMessage.reconstruct_from_java(self, habbo_msg_as_string)
                habbo_packet = habbo_message.packet

                for func in self.__intercept_listeners[habbo_message.direction][-1]:
                    func(habbo_message)
                    habbo_packet.reset()

                header_id = habbo_packet.header_id()
                if header_id in self.__intercept_listeners[habbo_message.direction]:
                    for func in self.__intercept_listeners[habbo_message.direction][header_id]:
                        func(habbo_message)
                        habbo_packet.reset()

                response_packet = HPacket(self, OUTGOING_MESSAGES.MANIPULATED_PACKET.value)
                response_packet.append_string(repr(habbo_message), head=4, encoding='iso-8859-1')
                self.__send_to_stream(response_packet)

    def __send_to_stream(self, packet):
        self.__stream_lock.acquire()
        self.sock.send(packet.bytearray)
        self.__stream_lock.release()

    def __raise_event(self, event_name):
        if event_name in self.__events:
            for func in self.__events[event_name]:
                func()

    def __send(self, direction, packet):
        wrapper_packet = HPacket(self, OUTGOING_MESSAGES.SEND_MESSAGE.value, direction == Direction.TO_SERVER,
                         len(packet.bytearray), bytes(packet.bytearray))
        self.__send_to_stream(wrapper_packet)

    def send_to_client(self, packet):
        self.__send(Direction.TO_CLIENT, packet)

    def send_to_server(self, packet):
        self.__send(Direction.TO_SERVER, packet)

    def on_event(self, event_name, func):
        """ implemented event names:
            * double_click
            * connection_start
            * connection_end
            * init
            """
        if event_name in self.__events:
            self.__events[event_name].append(func)
        else:
            self.__events[event_name] = [func]

    def intercept(self, direction, callback, id=-1):
        # todo: id could be hash/name from HarbleAPI
        if id not in self.__intercept_listeners[direction]:
            self.__intercept_listeners[direction][id] = []
        self.__intercept_listeners[direction][id].append(callback)

    def start(self):
        self.sock = socket.socket()
        self.sock.connect(("127.0.0.1", self.__port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.is_closed = False
        t = threading.Thread(target=self.__connection_thread)
        t.start()

    def close(self):
        self.is_closed = True

    def write_to_console(self, text, color='black', mention_title=True):
        message = '[{}]{}{}'.format(color, (self._extension_info['title'] + ' --> ') if mention_title else '', text)
        packet = HPacket(self, OUTGOING_MESSAGES.EXTENSION_CONSOLE_LOG.value, message)
        self.__send_to_stream(packet)