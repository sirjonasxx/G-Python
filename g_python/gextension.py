import copy
import socket
import sys
import threading
from enum import IntEnum, StrEnum
from typing import TypedDict, NotRequired, Callable

from .hpacket import HPacket
from .hmessage import HMessage, Direction

MINIMUM_GEARTH_VERSION: str = "1.4.1"


class IncomingMessages(IntEnum):
    ON_DOUBLE_CLICK = 1
    INFO_REQUEST = 2
    PACKET_INTERCEPT = 3
    FLAGS_CHECK = 4
    CONNECTION_START = 5
    CONNECTION_END = 6
    PACKET_TO_STRING_RESPONSE = 20
    STRING_TO_PACKET_RESPONSE = 21
    INIT = 7


class OutgoingMessages(IntEnum):
    EXTENSION_INFO = 1
    MANIPULATED_PACKET = 2
    REQUEST_FLAGS = 3
    SEND_MESSAGE = 4
    PACKET_TO_STRING_REQUEST = 20
    STRING_TO_PACKET_REQUEST = 21
    EXTENSION_CONSOLE_LOG = 98


class InterceptMethod(StrEnum):
    DEFAULT = 'default'
    ASYNC = 'async'
    ASYNC_MODIFY = 'async_modify'


class ConsoleColour(StrEnum):
    GREY = 'grey'
    LIGHTGREY = 'lightgrey'
    YELLOW = 'yellow'
    ORANGE = 'orange'
    WHITE = 'white'
    PURPLE = 'purple'
    BROWN = 'brown'
    PINK = 'pink'
    RED = 'red'
    BLACK = 'black'
    BLUE = 'blue'
    CYAN = 'cyan'
    GREEN = 'green'
    DARK_GREEN = 'darkergreen'


PORT_FLAG: list[str] = ["--port", "-p"]
FILE_FLAG: list[str] = ["--filename", "-f"]
COOKIE_FLAG: list[str] = ["--auth-token", "-c"]


class ExtensionInfo(TypedDict):
    title: str
    description: str
    version: str
    author: str


class ExtensionSettings(TypedDict):
    use_click_trigger: NotRequired[bool]
    can_leave: NotRequired[bool]
    can_delete: NotRequired[bool]


EXTENSION_SETTINGS_DEFAULT: ExtensionSettings = {"use_click_trigger": False, "can_leave": True, "can_delete": True}
EXTENSION_INFO_REQUIRED_FIELDS = ["title", "description", "version", "author"]


def fill_settings(settings: ExtensionSettings, defaults: ExtensionSettings):
    if settings is None:
        return defaults.copy()

    settings = settings.copy()
    for key, value in defaults.items():
        if key not in settings or settings[key] is None:
            settings[key] = value

    return settings


def get_argument(args: list[str], flags: list[str] | str):
    if type(flags) == str:
        flags = [flags]

    for potential_flag in flags:
        if potential_flag in args:
            index = args.index(potential_flag)
            if 0 <= index < len(args) - 1:
                return args[index + 1]

    return None


def run_callbacks(callbacks: list[Callable[[], None]]) -> None:
    for func in callbacks:
        func()


class Extension:
    def __init__(self, extension_info: ExtensionInfo, args: list[str],
                 extension_settings: None | ExtensionSettings = None, silent: bool = False):
        if not silent:
            print("WARNING: This version of G-Python requires G-Earth >= {}".format(MINIMUM_GEARTH_VERSION),
                  file=sys.stderr)
            print("abc")

        extension_settings = fill_settings(extension_settings, EXTENSION_SETTINGS_DEFAULT)

        if get_argument(args, PORT_FLAG) is None:
            raise Exception('Port was not specified (argument example: -p 9092)')

        for key in EXTENSION_INFO_REQUIRED_FIELDS:
            if key not in extension_info:
                raise Exception('Extension info error: {} field missing'.format(key))

        port = int(get_argument(args, PORT_FLAG))
        file = get_argument(args, FILE_FLAG)
        cookie = get_argument(args, COOKIE_FLAG)

        self.__sock = None
        self.__lost_packets = 0

        self._extension_info = extension_info
        self.__port = port
        self.__file = file
        self.__cookie = cookie
        self._extension_settings = extension_settings

        self.connection_info = None
        self.packet_infos = None

        self.__start_barrier = threading.Barrier(2)
        self.__start_lock = threading.Lock()
        self.__stream_lock = threading.Lock()

        self.__events = {}
        self.__intercept_listeners = {Direction.TO_CLIENT: {-1: []}, Direction.TO_SERVER: {-1: []}}

        self.__request_lock = threading.Lock()
        self.__response_barrier = threading.Barrier(2)
        self.__response = None

        self.__manipulation_lock = threading.Lock()
        self.__manipulation_event = threading.Event()
        self.__manipulate_messages = []

    def __read_gearth_packet(self) -> HPacket:
        write_pos = 0

        length_buffer = bytearray(4)
        while write_pos < 4:
            n_read = self.__sock.recv_into(memoryview(length_buffer)[write_pos:])
            if n_read == 0:
                raise EOFError
            write_pos += n_read

        packet_length = int.from_bytes(length_buffer, byteorder='big')
        packet_buffer = length_buffer + bytearray(packet_length)

        while write_pos < 4 + packet_length:
            n_read = self.__sock.recv_into(memoryview(packet_buffer)[write_pos:])
            if n_read == 0:
                raise EOFError
            write_pos += n_read

        return HPacket.from_bytes(packet_buffer)

    def __packet_manipulation_thread(self) -> None:
        while not self.is_closed():
            habbo_message = None
            while habbo_message is None and not self.is_closed():
                if len(self.__manipulate_messages) > 0:
                    self.__manipulation_lock.acquire()
                    habbo_message = self.__manipulate_messages.pop(0)
                    self.__manipulation_lock.release()
                    self.__manipulation_event.clear()
                else:
                    self.__manipulation_event.wait(0.002)
                    self.__manipulation_event.clear()

            if self.is_closed():
                return

            habbo_packet = habbo_message.packet
            habbo_packet.default_extension = self

            for func in self.__intercept_listeners[habbo_message.direction][-1]:
                func(habbo_message)
                habbo_packet.reset()

            header_id = habbo_packet.header_id()
            potential_intercept_ids = {header_id}
            if self.packet_infos is not None and header_id in self.packet_infos[habbo_message.direction]:
                for elem in self.packet_infos[habbo_message.direction][header_id]:
                    if elem['Name'] is not None:
                        potential_intercept_ids.add(elem['Name'])
                    if elem['Hash'] is not None:
                        potential_intercept_ids.add(elem['Hash'])

            for identifier in potential_intercept_ids:
                if identifier in self.__intercept_listeners[habbo_message.direction]:
                    for func in self.__intercept_listeners[habbo_message.direction][identifier]:
                        func(habbo_message)
                        habbo_packet.reset()

            response_packet = HPacket(OutgoingMessages.MANIPULATED_PACKET.value)
            response_packet.append_string(repr(habbo_message), head=4, encoding='iso-8859-1')
            self.__send_to_stream(response_packet)

    def __connection_thread(self) -> None:
        t = threading.Thread(target=self.__packet_manipulation_thread)
        t.start()

        while not self.is_closed():
            try:
                packet = self.__read_gearth_packet()
            except EOFError:
                if not self.is_closed():
                    self.stop()
                return

            message_type = IncomingMessages(packet.header_id())
            if message_type == IncomingMessages.INFO_REQUEST:
                response = HPacket(OutgoingMessages.EXTENSION_INFO.value)
                response \
                    .append_string(self._extension_info['title']) \
                    .append_string(self._extension_info['author']) \
                    .append_string(self._extension_info['version']) \
                    .append_string(self._extension_info['description']) \
                    .append_bool(self._extension_settings['use_click_trigger']) \
                    .append_bool(self.__file is not None) \
                    .append_string('' if self.__file is None else self.__file) \
                    .append_string('' if self.__cookie is None else self.__cookie) \
                    .append_bool(self._extension_settings['can_leave']) \
                    .append_bool(self._extension_settings['can_delete'])

                self.__send_to_stream(response)

            elif message_type == IncomingMessages.CONNECTION_START:
                host, port, hotel_version, client_identifier, client_type = packet.read("sisss")
                self.__parse_packet_infos(packet)

                self.connection_info = {'host': host, 'port': port, 'hotel_version': hotel_version,
                                        'client_identifier': client_identifier, 'client_type': client_type}

                self.__raise_event('connection_start')

                if self.__await_connect_packet:
                    self.__await_connect_packet = False
                    self.__start_barrier.wait()

            elif message_type == IncomingMessages.CONNECTION_END:
                self.__raise_event('connection_end')
                self.connection_info = None
                self.packet_infos = None

            elif message_type == IncomingMessages.FLAGS_CHECK:
                size = packet.read_int()
                flags = [packet.read_string() for _ in range(size)]
                self.__response = flags
                self.__response_barrier.wait()

            elif message_type == IncomingMessages.INIT:
                self.__raise_event('init')
                self.write_to_console(
                    'g_python extension "{}" sucessfully initialized'.format(self._extension_info['title']),
                    ConsoleColour.GREEN,
                    False
                )

                self.__await_connect_packet = packet.read_bool()
                if not self.__await_connect_packet:
                    self.__start_barrier.wait()

            elif message_type == IncomingMessages.ON_DOUBLE_CLICK:
                self.__raise_event('double_click')

            elif message_type == IncomingMessages.PACKET_INTERCEPT:
                habbo_msg_as_string = packet.read_string(head=4, encoding='iso-8859-1')
                habbo_message = HMessage.reconstruct_from_java(habbo_msg_as_string)
                self.__manipulation_lock.acquire()
                self.__manipulate_messages.append(habbo_message)
                self.__manipulation_lock.release()
                self.__manipulation_event.set()

            elif message_type == IncomingMessages.PACKET_TO_STRING_RESPONSE:
                string = packet.read_string(head=4, encoding='iso-8859-1')
                expression = packet.read_string(head=4, encoding='utf-8')
                self.__response = (string, expression)
                self.__response_barrier.wait()

            elif message_type == IncomingMessages.STRING_TO_PACKET_RESPONSE:
                packet_string = packet.read_string(head=4, encoding='iso-8859-1')
                self.__response = HPacket.reconstruct_from_java(packet_string)
                self.__response_barrier.wait()

    def __parse_packet_infos(self, packet: HPacket) -> None:
        incoming = {}
        outgoing = {}

        length = packet.read_int()
        for _ in range(length):
            header_id, hash_code, name, structure, is_outgoing, source = packet.read('isssBs')
            name = name if name != 'NULL' else None
            hash_code = hash_code if hash_code != 'NULL' else None
            structure = structure if structure != 'NULL' else None

            elem = {'Id': header_id, 'Name': name, 'Hash': hash_code, 'Structure': structure, 'Source': source}

            packet_dict = outgoing if is_outgoing else incoming
            if header_id not in packet_dict:
                packet_dict[header_id] = []
            packet_dict[header_id].append(elem)

            if hash_code is not None:
                if hash_code not in packet_dict:
                    packet_dict[hash_code] = []
                packet_dict[hash_code].append(elem)

            if name is not None:
                if name not in packet_dict:
                    packet_dict[name] = []
                packet_dict[name].append(elem)

        self.packet_infos = {Direction.TO_CLIENT: incoming, Direction.TO_SERVER: outgoing}

    def __send_to_stream(self, packet: HPacket) -> None:
        self.__stream_lock.acquire()
        self.__sock.send(packet.bytearray)
        self.__stream_lock.release()

    def __raise_event(self, event_name: str) -> None:
        if event_name in self.__events:
            t = threading.Thread(target=run_callbacks, args=(self.__events[event_name],))
            t.start()

    def __send(self, direction: Direction, packet: HPacket) -> bool:
        if not self.is_closed():

            old_settings = None
            if packet.is_incomplete_packet():
                old_settings = (packet.header_id(), packet.is_edited, packet.incomplete_identifier)
                packet.fill_id(direction, self)

            if self.connection_info is None:
                self.__lost_packets += 1
                print("Could not send packet because G-Earth isn't connected to a client", file=sys.stderr)
                return False

            if packet.is_corrupted():
                self.__lost_packets += 1
                print('Could not send corrupted', file=sys.stderr)
                return False

            if packet.is_incomplete_packet():
                self.__lost_packets += 1
                print('Could not send incomplete packet', file=sys.stderr)
                return False

            wrapper_packet = HPacket(OutgoingMessages.SEND_MESSAGE.value, direction == Direction.TO_SERVER,
                                     len(packet.bytearray), bytes(packet.bytearray))
            self.__send_to_stream(wrapper_packet)

            if old_settings is not None:
                packet.replace_short(4, old_settings[0])
                packet.incomplete_identifier = old_settings[2]
                packet.is_edited = old_settings[1]

            return True
        else:
            self.__lost_packets += 1
            return False

    def is_closed(self) -> bool:
        """
        :return: true if no extension isn't connected with G-Earth
        """
        return self.__sock is None or self.__sock.fileno() == -1

    def send_to_client(self, packet: HPacket | str) -> bool:
        """
        Sends a message to the client
        :param packet: a HPacket() or a string representation
        """

        if type(packet) is str:
            packet = self.string_to_packet(packet)
        return self.__send(Direction.TO_CLIENT, packet)

    def send_to_server(self, packet: HPacket | str) -> bool:
        """
        Sends a message to the server
        :param packet: a HPacket() or a string representation
        """

        if type(packet) is str:
            packet = self.string_to_packet(packet)
        return self.__send(Direction.TO_SERVER, packet)

    def on_event(self, event_name: str, func: Callable) -> None:
        """
        implemented event names: double_click, connection_start, connection_end,init. When this
        even occurs, a callback is being done to "func"
        """
        if event_name in self.__events:
            self.__events[event_name].append(func)
        else:
            self.__events[event_name] = [func]

    def intercept(self, direction: Direction, callback: Callable[[HMessage], None], identifier: int | str = -1,
                  mode: InterceptMethod = InterceptMethod.DEFAULT) -> None:
        """
        :param direction: Direction.TOCLIENT or Direction.TOSERVER
        :param callback: function that takes HMessage as an argument
        :param identifier: header_id / hash / name
        :param mode: can be: * default (blocking)
                             * async (async, can't modify packet, doesn't disturb packet flow)
                             * async_modify (async, can modify, doesn't block other packets, disturbs packet flow)
        :return:
        """
        original_callback = callback

        if mode == 'async':
            def new_callback(hmessage: HMessage) -> None:
                copied = copy.copy(hmessage)
                t = threading.Thread(target=original_callback, args=[copied])
                t.start()

            callback = new_callback

        if mode == 'async_modify':
            def callback_send(hmessage: HMessage) -> None:
                original_callback(hmessage)
                if not hmessage.is_blocked:
                    self.__send(hmessage.direction, hmessage.packet)

            def new_callback(hmessage: HMessage) -> None:
                hmessage.is_blocked = True
                copied = copy.copy(hmessage)
                copied.is_blocked = False
                t = threading.Thread(target=callback_send, args=[copied])
                t.start()

            callback = new_callback

        if identifier not in self.__intercept_listeners[direction]:
            self.__intercept_listeners[direction][identifier] = []
        self.__intercept_listeners[direction][identifier].append(callback)

    def remove_intercept(self, intercept_id: int | str = -1) -> None:
        """
        Clear intercepts per id or all of them when none is given
        """

        if intercept_id == -1:
            for direction in self.__intercept_listeners:
                for identifier in self.__intercept_listeners[direction]:
                    del self.__intercept_listeners[direction][identifier]
        else:
            for direction in self.__intercept_listeners:
                if intercept_id in self.__intercept_listeners[direction]:
                    del self.__intercept_listeners[direction][intercept_id]

    def start(self) -> None:
        """
        Tries to set up a connection with G-Earth
        """
        self.__start_lock.acquire()
        if self.is_closed():
            self.__sock = socket.socket()
            self.__sock.connect(("127.0.0.1", self.__port))
            self.__sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            t = threading.Thread(target=self.__connection_thread)
            t.start()
            self.__start_barrier.wait()
        else:
            self.__start_lock.release()
            raise Exception("Attempted to run already-running extension")
        self.__start_lock.release()

    def stop(self) -> None:
        """
        Aborts an existing connection with G-Earth
        """
        if not self.is_closed():
            self.__sock.close()
        else:
            raise Exception("Attempted to close extension that wasn't running")

    def write_to_console(self, text, color: ConsoleColour = ConsoleColour.BLACK, mention_title: bool = True) -> None:
        """
        Writes a message to the G-Earth console
        """
        message = '[{}]{}{}'.format(color, (self._extension_info['title'] + ' --> ') if mention_title else '', text)
        packet = HPacket(OutgoingMessages.EXTENSION_CONSOLE_LOG.value, message)
        self.__send_to_stream(packet)

    def __await_response(self, request: HPacket) -> str | list[str] | HPacket:
        self.__request_lock.acquire()
        self.__send_to_stream(request)
        self.__response_barrier.wait()
        result = self.__response
        self.__response = None
        self.__request_lock.release()
        return result

    def packet_to_string(self, packet: HPacket) -> str:
        request = HPacket(OutgoingMessages.PACKET_TO_STRING_REQUEST.value)
        request.append_string(repr(packet), 4, 'iso-8859-1')

        return self.__await_response(request)[0]

    def packet_to_expression(self, packet: HPacket) -> str:
        request = HPacket(OutgoingMessages.PACKET_TO_STRING_REQUEST.value)
        request.append_string(repr(packet), 4, 'iso-8859-1')

        return self.__await_response(request)[1]

    def string_to_packet(self, string: str) -> HPacket:
        request = HPacket(OutgoingMessages.STRING_TO_PACKET_REQUEST.value)
        request.append_string(string, 4)

        return self.__await_response(request)

    def request_flags(self) -> list[str]:
        return self.__await_response(HPacket(OutgoingMessages.REQUEST_FLAGS.value))
