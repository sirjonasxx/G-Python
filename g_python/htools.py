from .gextension import Extension
from .hmessage import HMessage, Direction
from .hpacket import HPacket
from .hparsers import HEntity, HFloorItem, HWallItem, HInventoryItem


class RoomUsers:
    def __init__(self, ext: Extension, room_users='RoomUsers', room_model='RoomModel', remove_user='RoomUserRemove',
                 request='RequestRoomHeightmap'):
        self.room_users = {}
        self.__callback_new_users = None

        self.__ext = ext
        self.__request_id = request

        ext.intercept(Direction.TO_CLIENT, self.__load_room_users, room_users)
        ext.intercept(Direction.TO_CLIENT, self.__clear_room_users, room_model)  # (clear users / new room entered)
        ext.intercept(Direction.TO_CLIENT, self.__remove_user, remove_user)

    def __remove_user(self, message: HMessage):
        user = message.packet.read_string()
        index = int(user)
        if index in self.room_users:
            del self.room_users[index]

    def __load_room_users(self, message: HMessage):
        users = HEntity.parse(message.packet)
        for user in users:
            self.room_users[user.index] = user

        if self.__callback_new_users is not None:
            self.__callback_new_users(users)

    def __clear_room_users(self, _):
        self.room_users.clear()

    def on_new_users(self, func):
        self.__callback_new_users = func

    def request(self):
        self.room_users = {}
        self.__ext.send_to_server(HPacket(self.__request_id))


class RoomFurni:
    def __init__(self, ext: Extension, floor_items='RoomFloorItems', wall_items='RoomWallItems',
                 request='RequestRoomHeightmap'):
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
    def __init__(self, ext: Extension, inventory_items='InventoryItems', request='RequestInventoryItems'):
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
