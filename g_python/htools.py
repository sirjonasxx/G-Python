from .gextension import Extension
from .hmessage import HMessage, Direction
from .hpacket import HPacket
from .hparsers import HEntity, HFloorItem, HWallItem, HInventoryItem, HUserUpdate
import sys
import threading


def validate_headers(ext: Extension, parser_name, headers):
    def validate():
        for (header, dir) in headers:
            if header is None:
                error = "Missing headerID/Name in '{}'".format(parser_name)
                print(error, file=sys.stderr)
                ext.write_to_console(error, "red")
            if isinstance(header, str) and (ext.packet_infos is None or header not in ext.packet_infos[dir]):
                error = "Invalid headerID/Name in '{}': {}".format(parser_name, header)
                print(error, file=sys.stderr)
                ext.write_to_console(error, "red")

    ext.on_event('connection_start', validate)
    if ext.connection_info is not None:
        validate()


class RoomUsers:
    def __init__(self, ext: Extension, room_users='Users', room_model='RoomReady', remove_user='UserRemove',
                 request='GetHeightMap', status='UserUpdate'):
        validate_headers(ext, 'RoomUsers', [
            (room_users, Direction.TO_CLIENT),
            (room_model, Direction.TO_CLIENT),
            (remove_user, Direction.TO_CLIENT),
            (request, Direction.TO_SERVER)])

        self.room_users = {}
        self.__callback_new_users = None
        self.__callback_remove_user = None

        self.__ext = ext
        self.__request_id = request
        self.__lock = threading.Lock()
        self.lock = self.__lock

        ext.intercept(Direction.TO_CLIENT, self.__load_room_users, room_users)
        ext.intercept(Direction.TO_CLIENT, self.__clear_room_users, room_model)  # (clear users / new room entered)
        ext.intercept(Direction.TO_CLIENT, self.__remove_user, remove_user)
        ext.intercept(Direction.TO_CLIENT, self.__on_status, status)


    def __remove_user(self, message: HMessage):
        self.__start_remove_user_processing_thread(int(message.packet.read_string()))

    def __start_remove_user_processing_thread(self, index: int):
        thread = threading.Thread(target=self.__process_remove_user, args=(index,))
        thread.start()

    def __process_remove_user(self, index: int):
        self.__lock.acquire()
        try:
            if index in self.room_users:
                if self.__callback_remove_user is not None:
                    self.__callback_remove_user(self.room_users[index])
                del self.room_users[index]
        finally:
            self.__lock.release()

    def __load_room_users(self, message: HMessage):
        users = HEntity.parse(message.packet)
        self.__start_user_processing_thread(users)

        if self.__callback_new_users is not None:
            self.__callback_new_users(users)

    def __start_user_processing_thread(self, entities):
        thread = threading.Thread(target=self.__process_users_in_room, args=(entities,))
        thread.start()

    def __process_users_in_room(self, entities):
        self.__lock.acquire()
        try:
            for user in entities:
                self.room_users[user.index] = user
        finally:
            self.__lock.release()

    def __clear_room_users(self, _):
        self.room_users.clear()

    def on_new_users(self, func):
        self.__callback_new_users = func

    def on_remove_user(self, func):
        self.__callback_remove_user = func

    def __on_status(self, message):
        thread = threading.Thread(target=self.__parse_and_apply_updates, args=(message.packet,))
        thread.start()

    def __parse_and_apply_updates(self, packet):
        self.try_updates(HUserUpdate.parse(packet))

    def __apply_updates(self, updates):
        for update in updates:
            self.__lock.acquire()
            try:
                user = self.room_users[update.index]
                if isinstance(user, HEntity):
                    user.try_update(update)
            except KeyError:
                pass
            finally:
                self.__lock.release()

    def __start_update_processing_thread(self, updates):
        thread = threading.Thread(target=self.__apply_updates, args=(updates,))
        thread.start()

    def try_updates(self, updates):
        self.__start_update_processing_thread(updates)

    def request(self):
        self.room_users = {}
        self.__ext.send_to_server(HPacket(self.__request_id))


class RoomFurni:
    def __init__(self, ext: Extension, floor_items='Objects', wall_items='Items',
                 request='GetHeightMap'):
        validate_headers(ext, 'RoomFurni', [
            (floor_items, Direction.TO_CLIENT),
            (wall_items, Direction.TO_CLIENT),
            (request, Direction.TO_SERVER)])

        self.floor_furni = []
        self.wall_furni = []
        self.__callback_floor_furni = None
        self.__callback_wall_furni = None

        self.__ext = ext
        self.__request_id = request

        ext.intercept(Direction.TO_CLIENT, self.__floor_furni_load, floor_items)
        ext.intercept(Direction.TO_CLIENT, self.__wall_furni_load, wall_items)

    def __floor_furni_load(self, message):
        self.floor_furni = HFloorItem.parse(message.packet)
        if self.__callback_floor_furni is not None:
            self.__callback_floor_furni(self.floor_furni)

    def __wall_furni_load(self, message):
        self.wall_furni = HWallItem.parse(message.packet)
        if self.__callback_wall_furni is not None:
            self.__callback_wall_furni(self.wall_furni)

    def on_floor_furni_load(self, callback):
        self.__callback_floor_furni = callback

    def on_wall_furni_load(self, callback):
        self.__callback_wall_furni = callback

    def request(self):
        self.floor_furni = []
        self.wall_furni = []
        self.__ext.send_to_server(HPacket(self.__request_id))


class Inventory:
    def __init__(self, ext: Extension, inventory_items='FurniList', request='RequestFurniInventory'):
        validate_headers(ext, 'Inventory', [
            (inventory_items, Direction.TO_CLIENT),
            (request, Direction.TO_SERVER)])

        self.loaded = False
        self.is_loading = False
        self.inventory_items = []
        self.__inventory_items_buffer = []

        self.__ext = ext
        self.__request_id = request
        self.__inventory_load_callback = None

        ext.intercept(Direction.TO_CLIENT, self.__user_inventory_load, inventory_items)

    def __user_inventory_load(self, message: HMessage):
        packet = message.packet
        total, current = packet.read('ii')
        packet.reset()

        items = HInventoryItem.parse(packet)

        if current == 0:  # fresh inventory load
            self.__inventory_items_buffer.clear()
            self.is_loading = True

        self.__inventory_items_buffer.extend(items)
        # print("Loading inventory.. ({}/{})".format(current + 1, total))

        if current == total - 1:  # latest packet
            self.is_loading = False
            self.loaded = True
            self.inventory_items = list(self.__inventory_items_buffer)
            self.__inventory_items_buffer.clear()

            self.__inventory_load_callback(self.inventory_items)

    def request(self):
        self.__ext.send_to_server(HPacket(self.__request_id))

    def on_inventory_load(self, callback):
        self.__inventory_load_callback = callback
