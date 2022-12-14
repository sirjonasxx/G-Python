import socket
import sys
import threading
from enum import Enum
from .hpacket import HPacket
from .hmessage import HMessage, Direction

MINIMUM_GEARTH_VERSION = "1.4.1"


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


EXTENSION_SETTINGS_DEFAULT = {
    "use_click_trigger": False, "can_leave": True, "can_delete": True}
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


def get_argument(args, flags: str):
    if isinstance(flags, str):
        flags = [flags]

    for potential_flag in flags:
        if potential_flag in args:
            index = args.index(potential_flag)
            if 0 <= index < len(args) - 1:
                return args[index + 1]

    return None


class Extension:
    def __init__(self, extension_info, args, extension_settings=None, silent=False):
        if not silent:
            print(
                f"WARNING: This version of G-Python requires G-Earth >= {MINIMUM_GEARTH_VERSION}", file=sys.stderr)

        extension_settings = fill_settings(
            extension_settings, EXTENSION_SETTINGS_DEFAULT)

        if get_argument(args, PORT_FLAG) is None:
            raise Exception(
                'Port was not specified (argument example: -p 9092)')

        for key in EXTENSION_INFO_REQUIRED_FIELDS:
            if key not in extension_info:
                raise Exception(f'Extension info error: {key} field missing')

        port = int(get_argument(args, PORT_FLAG))
        file = get_argument(args, FILE_FLAG)
        cookie = get_argument(args, COOKIE_FLAG)

        self.__sock = None
        self._lost_packets = 0
        self.__await_connect_packet = None

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
        self.__intercept_listeners = {
            Direction.TO_CLIENT: {-1: []}, Direction.TO_SERVER: {-1: []}}

        self.__request_lock = threading.Lock()
        self.__response_barrier = threading.Barrier(2)
        self.__response = None

        self.__manipulation_lock = threading.Lock()
        self.__manipulation_event = threading.Event()
        self.__manipulate_messages = []

    def __read_gearth_packet(self):
        write_pos = 0

        length_buffer = bytearray(4)
        while write_pos < 4:
            n_read = self.__sock.recv_into(
                memoryview(length_buffer)[write_pos:])
            if n_read == 0:
                raise EOFError
            write_pos += n_read

        packet_length = int.from_bytes(length_buffer, byteorder='big')
        packet_buffer = length_buffer + bytearray(packet_length)

        while write_pos < 4 + packet_length:
            n_read = self.__sock.recv_into(
                memoryview(packet_buffer)[write_pos:])
            if n_read == 0:
                raise EOFError
            write_pos += n_read

        return HPacket.from_bytes(packet_buffer)

    def __packet_manipulation_thread(self):
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

            for p_id in potential_intercept_ids:
                if p_id in self.__intercept_listeners[habbo_message.direction]:
                    for func in self.__intercept_listeners[habbo_message.direction][p_id]:
                        func(habbo_message)
                        habbo_packet.reset()

            response_packet = HPacket(
                OUTGOING_MESSAGES.MANIPULATED_PACKET.value)
            response_packet.append_string(
                repr(habbo_message), head=4, encoding='iso-8859-1')
            self.__send_to_stream(response_packet)

    def __connection_thread(self):
        t = threading.Thread(target=self.__packet_manipulation_thread)
        t.start()

        while not self.is_closed():
            try:
                packet = self.__read_gearth_packet()
            except Exception:
                if not self.is_closed():
                    self.stop()
                return

            message_type = INCOMING_MESSAGES(packet.header_id())
            if message_type == INCOMING_MESSAGES.INFO_REQUEST:
                response = HPacket(OUTGOING_MESSAGES.EXTENSION_INFO.value)
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

            elif message_type == INCOMING_MESSAGES.CONNECTION_START:
                host, port, hotel_version, client_identifier, client_type = packet.read(
                    "sisss")
                self.__parse_packet_infos(packet)

                self.connection_info = {'host': host, 'port': port, 'hotel_version': hotel_version,
                                        'client_identifier': client_identifier, 'client_type': client_type}

                self.__raise_event('connection_start')

                if self.__await_connect_packet:
                    self.__await_connect_packet = False
                    self.__start_barrier.wait()

            elif message_type == INCOMING_MESSAGES.CONNECTION_END:
                self.__raise_event('connection_end')
                self.connection_info = None
                self.packet_infos = None

            elif message_type == INCOMING_MESSAGES.FLAGS_CHECK:
                size = packet.read_int()
                flags = [packet.read_string() for _ in range(size)]
                self.__response = flags
                self.__response_barrier.wait()

            elif message_type == INCOMING_MESSAGES.INIT:
                self.__raise_event('init')
                self.write_to_console(
                    'g_python extension "{}" sucessfully initialized'.format(
                        self._extension_info['title']),
                    'green',
                    False
                )

                self.__await_connect_packet = packet.read_bool()
                if not self.__await_connect_packet:
                    self.__start_barrier.wait()

            elif message_type == INCOMING_MESSAGES.ON_DOUBLE_CLICK:
                self.__raise_event('double_click')

            elif message_type == INCOMING_MESSAGES.PACKET_INTERCEPT:
                habbo_msg_as_string = packet.read_string(
                    head=4, encoding='iso-8859-1')
                habbo_message = HMessage.reconstruct_from_java(
                    habbo_msg_as_string)
                self.__manipulation_lock.acquire()
                self.__manipulate_messages.append(habbo_message)
                self.__manipulation_lock.release()
                self.__manipulation_event.set()

            elif message_type == INCOMING_MESSAGES.PACKET_TO_STRING_RESPONSE:
                string = packet.read_string(head=4, encoding='iso-8859-1')
                expression = packet.read_string(head=4, encoding='utf-8')
                self.__response = (string, expression)
                self.__response_barrier.wait()

            elif message_type == INCOMING_MESSAGES.STRING_TO_PACKET_RESPONSE:
                packet_string = packet.read_string(
                    head=4, encoding='iso-8859-1')
                self.__response = HPacket.reconstruct_from_java(packet_string)
                self.__response_barrier.wait()

    def __parse_packet_infos(self, packet: HPacket):
        incoming = {}
        outgoing = {}

        length = packet.read_int()
        for _ in range(length):
            header_id, p_hash, name, structure, is_outgoing, source = packet.read(
                'isssBs')
            name = name if name != 'NULL' else None
            p_hash = p_hash if p_hash != 'NULL' else None
            structure = structure if structure != 'NULL' else None

            elem = {'Id': header_id, 'Name': name, 'Hash': p_hash,
                    'Structure': structure, 'Source': source}

            packet_dict = outgoing if is_outgoing else incoming
            if header_id not in packet_dict:
                packet_dict[header_id] = []
            packet_dict[header_id].append(elem)

            if p_hash is not None:
                if p_hash not in packet_dict:
                    packet_dict[p_hash] = []
                packet_dict[p_hash].append(elem)

            if name is not None:
                if name not in packet_dict:
                    packet_dict[name] = []
                packet_dict[name].append(elem)

        self.packet_infos = {Direction.TO_CLIENT: incoming,
                             Direction.TO_SERVER: outgoing}

    def __send_to_stream(self, packet):
        self.__stream_lock.acquire()
        self.__sock.send(packet.bytearray)
        self.__stream_lock.release()

    def __callbacks(self, callbacks):
        for func in callbacks:
            func()

    def __raise_event(self, event_name):
        if event_name in self.__events:
            t = threading.Thread(target=self.__callbacks,
                                 args=(self.__events[event_name],))
            t.start()

    def __send(self, direction, packet: HPacket):
        if not self.is_closed():

            old_settings = None
            if packet.is_incomplete_packet():
                old_settings = (packet.header_id(),
                                packet.is_edited, packet.incomplete_identifier)
                packet.fill_id(direction, self)

            if self.connection_info is None:
                self._lost_packets += 1
                print(
                    "Could not send packet because G-Earth isn't connected to a client", file=sys.stderr)
                return False

            if packet.is_corrupted():
                self._lost_packets += 1
                print('Could not send corrupted', file=sys.stderr)
                return False

            if packet.is_incomplete_packet():
                self._lost_packets += 1
                print('Could not send incomplete packet', file=sys.stderr)
                return False

            wrapper_packet = HPacket(OUTGOING_MESSAGES.SEND_MESSAGE.value, direction == Direction.TO_SERVER,
                                     len(packet.bytearray), bytes(packet.bytearray))
            self.__send_to_stream(wrapper_packet)

            if old_settings is not None:
                packet.replace_short(4, old_settings[0])
                packet.incomplete_identifier = old_settings[2]
                packet.is_edited = old_settings[1]

            return True
        else:
            self._lost_packets += 1
            return False

    def is_closed(self):
        """
        :return: true if no extension isn't connected with G-Earth
        """
        return self.__sock is None or self.__sock.fileno() == -1

    def send_to_client(self, packet):
        """
        Sends a message to the client
        :param packet: a HPacket() or a string representation
        """

        if isinstance(packet, str):
            packet = self.string_to_packet(packet)
        self.__send(Direction.TO_CLIENT, packet)

    def send_to_server(self, packet):
        """
        Sends a message to the server
        :param packet: a HPacket() or a string representation
        """

        if isinstance(packet, str):
            packet = self.string_to_packet(packet)
        self.__send(Direction.TO_SERVER, packet)

    def on_event(self, event_name: str, func):
        """
        implemented event names: double_click, connection_start, connection_end,init. When this
        even occurs, a callback is being done to "func"
        """
        if event_name in self.__events:
            self.__events[event_name].append(func)
        else:
            self.__events[event_name] = [func]

    def intercept(self, direction: Direction, callback, p_id=-1, mode='default'):
        """
        :param direction: Direction.TOCLIENT or Direction.TOSERVER
        :param callback: function that takes HMessage as an argument
        :param id: header_id / hash / name
        :param mode: can be: * default (blocking)
                             * async (async, can't modify packet, doesn't disturb packet flow)
                             * async_modify (async, can modify, doesn't block other packets, disturbs packet flow)
        :return:
        """
        original_callback = callback

        def callback_async(hmessage: HMessage):
            copy = HMessage(hmessage.packet, hmessage.direction,
                            hmessage.hindex, hmessage.is_blocked)
            t = threading.Thread(target=original_callback, args=[copy])
            t.start()

        def callback_async_mod(hmessage: HMessage):
            hmessage.is_blocked = True
            copy = HMessage(hmessage.packet, hmessage.direction,
                            hmessage.hindex, False)
            t = threading.Thread(target=callback_send, args=[copy])
            t.start()

        def callback_send(hmessage: HMessage):
            original_callback(hmessage)
            if not hmessage.is_blocked:
                self.__send(hmessage.direction, hmessage.packet)

        if mode == 'async':
            callback = callback_async

        if mode == 'async_modify':
            callback = callback_async_mod

        if p_id not in self.__intercept_listeners[direction]:
            self.__intercept_listeners[direction][p_id] = []
        self.__intercept_listeners[direction][p_id].append(callback)

    def remove_intercept(self, p_id=-1):
        """
        Clear intercepts per id or all of them when none is given
        """

        if p_id == -1:
            for direction, identifier in self.__intercept_listeners.items():
                del self.__intercept_listeners[direction][identifier]
        else:
            for direction in self.__intercept_listeners:
                if p_id in self.__intercept_listeners[direction]:
                    del self.__intercept_listeners[direction][p_id]

    def start(self):
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

    def stop(self):
        """
        Aborts an existing connection with G-Earth
        """
        if not self.is_closed():
            self.__sock.close()
        else:
            raise Exception("Attempted to close extension that wasn't running")

    def write_to_console(self, text, color='black', mention_title=True):
        """
        Writes a message to the G-Earth console
        """
        title = (self._extension_info['title'] + ' --> ') if mention_title else ''
        message = f"[{color}]{title}{text}"
        packet = HPacket(
            OUTGOING_MESSAGES.EXTENSION_CONSOLE_LOG.value, message)
        self.__send_to_stream(packet)

    def __await_response(self, request):
        self.__request_lock.acquire()
        self.__send_to_stream(request)
        self.__response_barrier.wait()
        result = self.__response
        self.__response = None
        self.__request_lock.release()
        return result

    def packet_to_string(self, packet: HPacket):
        request = HPacket(OUTGOING_MESSAGES.PACKET_TO_STRING_REQUEST.value)
        request.append_string(repr(packet), 4, 'iso-8859-1')

        return self.__await_response(request)[0]

    def packet_to_expression(self, packet: HPacket):
        request = HPacket(OUTGOING_MESSAGES.PACKET_TO_STRING_REQUEST.value)
        request.append_string(repr(packet), 4, 'iso-8859-1')

        return self.__await_response(request)[1]

    def string_to_packet(self, string: str) -> HPacket:
        request = HPacket(OUTGOING_MESSAGES.STRING_TO_PACKET_REQUEST.value)
        request.append_string(string, 4)

        return self.__await_response(request)

    def request_flags(self):
        return self.__await_response(HPacket(OUTGOING_MESSAGES.REQUEST_FLAGS.value))
