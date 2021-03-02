import socket
import threading
from enum import Enum
from .hpacket import HPacket
from .hmessage import HMessage, Direction
import json


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
    for key, value in defaults.items():
        if key not in settings or settings[key] is None:
            settings[key] = value

    return settings


def get_argument(args, flags):
    if type(flags) == str:
        flags = [flags]

    for potential_flag in flags:
        if potential_flag in args:
            index = args.index(potential_flag)
            if 0 <= index < len(args) - 1:
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

        self.__sock = None
        self.__lost_packets = 0

        self._extension_info = extension_info
        self.__port = port
        self.__file = file
        self.__cookie = cookie
        self._extension_settings = extension_settings

        self.connection_info = None
        self.harble_api = None

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

    def __read_gearth_packet(self):
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
            hash, name = None, None
            if self.harble_api is not None and header_id in self.harble_api[habbo_message.direction]:
                hash = self.harble_api[habbo_message.direction][header_id]['Hash']
                name = self.harble_api[habbo_message.direction][header_id]['Name']
                if name == '' or name == 'null':
                    name = None

            for id in [header_id, hash, name]:
                if id is not None and id in self.__intercept_listeners[habbo_message.direction]:
                    for func in self.__intercept_listeners[habbo_message.direction][id]:
                        func(habbo_message)
                        habbo_packet.reset()

            response_packet = HPacket(OUTGOING_MESSAGES.MANIPULATED_PACKET.value)
            response_packet.append_string(repr(habbo_message), head=4, encoding='iso-8859-1')
            self.__send_to_stream(response_packet)

    def __connection_thread(self):
        t = threading.Thread(target=self.__packet_manipulation_thread)
        t.start()

        while not self.is_closed():
            try:
                packet = self.__read_gearth_packet()
            except:
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
                host = packet.read_string()
                port = packet.read_int()
                hotel_version = packet.read_string()
                harble_messages_path = packet.read_string()
                client_type = packet.read_string()
                self.connection_info = {'host': host, 'port': port, 'hotel_version': hotel_version,
                                        'client_type': client_type, 'harble_messages_path': harble_messages_path}

                if harble_messages_path != '' and harble_messages_path != 'null':
                    self.__harble_api_init()

                self.__raise_event('connection_start')

            elif message_type == INCOMING_MESSAGES.CONNECTION_END:
                self.__raise_event('connection_end')
                self.connection_info = None
                self.harble_api = None

            elif message_type == INCOMING_MESSAGES.FLAGS_CHECK:
                size = packet.read_int()
                flags = [packet.read_string() for _ in range(size)]
                self.__response = flags
                self.__response_barrier.wait()

            elif message_type == INCOMING_MESSAGES.INIT:
                self.__raise_event('init')
                self.write_to_console(
                    'g_python extension "{}" sucessfully initialized'.format(self._extension_info['title']),
                    'green',
                    False
                )
                self.__start_barrier.wait()

            elif message_type == INCOMING_MESSAGES.ON_DOUBLE_CLICK:
                self.__raise_event('double_click')

            elif message_type == INCOMING_MESSAGES.PACKET_INTERCEPT:
                habbo_msg_as_string = packet.read_string(head=4, encoding='iso-8859-1')
                habbo_message = HMessage.reconstruct_from_java(habbo_msg_as_string)
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
                packet_string = packet.read_string(head=4, encoding='iso-8859-1')
                self.__response = HPacket.reconstruct_from_java(packet_string)
                self.__response_barrier.wait()

    def __harble_api_init(self):
        try:
            path = self.connection_info['harble_messages_path']
            with open(path) as f:

                def generate_harble_dict(json_list):
                    dict = {}
                    for elem in json_list:
                        dict[elem['Id']] = elem
                        dict[elem['Hash']] = elem
                        name = elem['Name']
                        if name is not None and name != '' and name != 'null':
                            dict[name] = elem
                    return dict

                harble_api_json = json.load(f)
                incoming_json = harble_api_json['Incoming']
                outgoing_json = harble_api_json['Outgoing']
                incoming = generate_harble_dict(incoming_json)
                outgoing = generate_harble_dict(outgoing_json)

                self.harble_api = {Direction.TO_CLIENT: incoming, Direction.TO_SERVER: outgoing}
        except:
            self.harble_api = None
            self.write_to_console('Failed parsing HarbleAPI', 'red')

    def __send_to_stream(self, packet):
        self.__stream_lock.acquire()
        self.__sock.send(packet.bytearray)
        self.__stream_lock.release()

    def __raise_event(self, event_name):
        if event_name in self.__events:
            for func in self.__events[event_name]:
                func()

    def __send(self, direction, packet: HPacket):
        if not self.is_closed():

            old_settings = None
            if packet.is_harble_api_packet():
                old_settings = (packet.header_id(), packet.is_edited, packet.harble_id)
                packet.fill_id(direction, self)

            if packet.is_corrupted():
                self.__lost_packets += 1
                print('Could not send corrupted packet')
                return False

            wrapper_packet = HPacket(OUTGOING_MESSAGES.SEND_MESSAGE.value, direction == Direction.TO_SERVER,
                                     len(packet.bytearray), bytes(packet.bytearray))
            self.__send_to_stream(wrapper_packet)

            if old_settings is not None:
                packet.replace_short(4, old_settings[0])
                packet.harble_id = old_settings[2]
                packet.is_edited = old_settings[1]

            return True
        else:
            self.__lost_packets += 1
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

        if type(packet) is str:
            packet = self.string_to_packet(packet)
        self.__send(Direction.TO_CLIENT, packet)

    def send_to_server(self, packet):
        """
        Sends a message to the server
        :param packet: a HPacket() or a string representation
        """

        if type(packet) is str:
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

    def intercept(self, direction: Direction, callback, id=-1, mode='default'):
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

        if mode == 'async':
            def new_callback(hmessage : HMessage):
                copy = HMessage(hmessage.packet, hmessage.direction, hmessage._index, hmessage.is_blocked)
                t = threading.Thread(target=original_callback, args=[copy])
                t.start()
            callback = new_callback

        if mode == 'async_modify':
            def callback_send(hmessage : HMessage):
                original_callback(hmessage)
                if not hmessage.is_blocked:
                    self.__send(hmessage.direction, hmessage.packet)

            def new_callback(hmessage : HMessage):
                hmessage.is_blocked = True
                copy = HMessage(hmessage.packet, hmessage.direction, hmessage._index, False)
                t = threading.Thread(target=callback_send, args=[copy])
                t.start()
            callback = new_callback

        if id not in self.__intercept_listeners[direction]:
            self.__intercept_listeners[direction][id] = []
        self.__intercept_listeners[direction][id].append(callback)

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
        message = '[{}]{}{}'.format(color, (self._extension_info['title'] + ' --> ') if mention_title else '', text)
        packet = HPacket(OUTGOING_MESSAGES.EXTENSION_CONSOLE_LOG.value, message)
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

    def string_to_packet(self, string):
        request = HPacket(OUTGOING_MESSAGES.STRING_TO_PACKET_REQUEST.value)
        request.append_string(string, 4)

        return self.__await_response(request)

    def request_flags(self):
        return self.__await_response(HPacket(OUTGOING_MESSAGES.REQUEST_FLAGS.value))
