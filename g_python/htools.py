from typing import Callable

from .gextension import Extension, ConsoleColour
from .hmessage import HMessage, Direction
from .hpacket import HPacket
from .hparsers import HEntity, HFloorItem, HWallItem, HInventoryItem, HUserUpdate
import sys


def validate_headers(ext: Extension, parser_name: str, headers: list[tuple[int | str, Direction]]):
    def validate():
        for (header, direction) in headers:
            if header is None:
                error = "Missing headerID/Name in '{}'".format(parser_name)
                print(error, file=sys.stderr)
                ext.write_to_console(error, ConsoleColour.RED)
            if isinstance(header, str) and (ext.packet_infos is None or header not in ext.packet_infos[direction]):
                error = "Invalid headerID/Name in '{}': {}".format(parser_name, header)
                print(error, file=sys.stderr)
                ext.write_to_console(error, ConsoleColour.RED)

    ext.on_event('connection_start', validate)
    if ext.connection_info is not None:
        validate()


class RoomUsers:
    def __init__(self, ext: Extension, room_users: str | int = 'Users', room_model: str | int = 'RoomReady',
                 remove_user: str | int = 'UserRemove',
                 request: str | int = 'GetHeightMap', status: str | int = 'UserUpdate'):
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

        ext.intercept(Direction.TO_CLIENT, self.__load_room_users, room_users)
        ext.intercept(Direction.TO_CLIENT, self.__clear_room_users, room_model)  # (clear users / new room entered)
        ext.intercept(Direction.TO_CLIENT, self.__remove_user, remove_user)
        ext.intercept(Direction.TO_CLIENT, self.__on_status, status)

    def __remove_user(self, message: HMessage) -> None:
        index = int(message.packet.read_string())
        if index in self.room_users:
            user = self.room_users[index]
            del self.room_users[index]
            if self.__callback_remove_user is not None:
                self.__callback_remove_user(user)

    def __load_room_users(self, message: HMessage) -> None:
        users = HEntity.parse(message.packet)
        for user in users:
            self.room_users[user.index] = user

        if self.__callback_new_users is not None:
            self.__callback_new_users(users)

    def __clear_room_users(self, _) -> None:
        self.room_users.clear()

    def on_new_users(self, func: Callable[[list[HEntity]], None]) -> None:
        self.__callback_new_users = func

    def on_remove_user(self, func: Callable[[HEntity], None]) -> None:
        self.__callback_remove_user = func

    def __on_status(self, message: HMessage) -> None:
        self.try_updates(HUserUpdate.parse(message.packet))

    def try_updates(self, updates: list[HUserUpdate]) -> None:
        for update in updates:
            try:
                user = self.room_users[update.index]
                if isinstance(user, HEntity):
                    user.try_update(update)
            except KeyError:
                pass

    def request(self) -> None:
        self.room_users = {}
        self.__ext.send_to_server(HPacket(self.__request_id))


class RoomFurni:
    def __init__(self, ext: Extension, floor_items: str | int = 'Objects', wall_items: str | int = 'Items',
                 request: str | int = 'GetHeightMap'):
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

    def __floor_furni_load(self, message: HMessage) -> None:
        self.floor_furni = HFloorItem.parse(message.packet)
        if self.__callback_floor_furni is not None:
            self.__callback_floor_furni(self.floor_furni)

    def __wall_furni_load(self, message: HMessage) -> None:
        self.wall_furni = HWallItem.parse(message.packet)
        if self.__callback_wall_furni is not None:
            self.__callback_wall_furni(self.wall_furni)

    def on_floor_furni_load(self, callback: Callable[[list[HFloorItem]], None]) -> None:
        self.__callback_floor_furni = callback

    def on_wall_furni_load(self, callback: Callable[[list[HWallItem]], None]) -> None:
        self.__callback_wall_furni = callback

    def request(self) -> None:
        self.floor_furni = []
        self.wall_furni = []
        self.__ext.send_to_server(HPacket(self.__request_id))


class Inventory:
    def __init__(self, ext: Extension, inventory_items: str | int = 'FurniList',
                 request: str | int = 'RequestFurniInventory'):
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

    def __user_inventory_load(self, message: HMessage) -> None:
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

    def request(self) -> None:
        self.__ext.send_to_server(HPacket(self.__request_id))

    def on_inventory_load(self, callback: Callable[[list[HInventoryItem]], None]) -> None:
        self.__inventory_load_callback = callback
