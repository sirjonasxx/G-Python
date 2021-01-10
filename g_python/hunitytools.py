import threading
import time

from .gextension import Extension
from .hmessage import HMessage, Direction
from .hpacket import HPacket
from .hunityparsers import HUnityEntity, HFUnityFloorItem


class UnityRoomUsers:
    def __init__(self, ext: Extension, users_in_room=28, get_guest_room=385, user_logged_out=29):
        self.room_users = {}
        self.__callback_new_users = None

        self.__ext = ext

        self.__lock = threading.Lock()

        ext.intercept(Direction.TO_CLIENT, self.__load_room_users, users_in_room)
        ext.intercept(Direction.TO_SERVER, self.__clear_room_users, get_guest_room)
        ext.intercept(Direction.TO_CLIENT, self.__remove_user, user_logged_out)

    def __remove_user(self, message: HMessage):
        self.__start_remove_user_processing_thread(message.packet.read_int())

    def __start_remove_user_processing_thread(self, index: int):
        thread = threading.Thread(target=self.__process_remove_user, args=(index,))
        thread.start()

    def __process_remove_user(self, index: int):
        self.__lock.acquire()
        try:
            if index in self.room_users:
                del self.room_users[index]
        finally:
            self.__lock.release()

    def __load_room_users(self, message: HMessage):
        users = HUnityEntity.parse(message.packet)
        self.__start_user_processing_thread(users)

        if self.__callback_new_users is not None:
            self.__callback_new_users(users)

    def __process_users_in_room(self, entities):
        self.__lock.acquire()
        try:
            for user in entities:
                self.room_users[user.index] = user
        finally:
            self.__lock.release()

    def __start_user_processing_thread(self, entities):
        thread = threading.Thread(target=self.__process_users_in_room, args=(entities,))
        thread.start()

    def __clear_room_users(self, _):
        self.__lock.acquire()
        self.room_users.clear()
        self.__lock.release()

    def on_new_users(self, func):
        self.__callback_new_users = func


class UnityRoomFurni:
    def __init__(self, ext: Extension, floor_items=32, wall_items='RoomWallItems',
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
        self.floor_furni = HFUnityFloorItem.parse(message.packet)
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