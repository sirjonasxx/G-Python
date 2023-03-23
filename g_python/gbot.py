import random
import threading
import time
from datetime import datetime
from typing import Callable

from g_python.gextension import Extension
from g_python.hdirection import Direction
from g_python.hmessage import HMessage
from g_python.hpacket import HPacket


class HBotProfile:
    settings = {
        "id": random.randrange(1 << 30, 1 << 31),
        "username": "Bot",
        "gender": 1,
        "is_following_allowed": False,
        "figure": "hd-3704-29",
        "motto": "Hey! I'm a bot.",
        "category_id": 0,
        "creation_date": datetime.today().strftime("%m-%d-%Y"),
        "achievement_score": 1000,
        "friend_count": 1,
        "is_friend": True,
        "is_requested_friend": False,
        "is_online": True,
        "is_persisted_message_user": True,
        "is_vip_member": False,
        "is_pocket_habbo_user": False,
    }

    def __init__(self, **kwargs) -> None:
        for key, value in HBotProfile.settings.items():
            setattr(self, key, value if key not in kwargs else kwargs[key])


# Thanks to denio4321 and sirjonasxx I got some ideas from them
class ConsoleBot:
    def __init__(
        self, extension: Extension, prefix: str = ":", bot_settings: HBotProfile = None
    ) -> None:
        self._extension = extension
        self._prefix = prefix
        self._bot_settings = HBotProfile() if bot_settings is None else bot_settings
        self._commands = {}

        self._chat_opened = False
        self._once_per_connection = False

        extension.intercept(Direction.TO_SERVER, self.should_open_chat)
        extension.intercept(
            Direction.TO_CLIENT, self.on_friend_list, "FriendListFragment", mode="async"
        )
        extension.intercept(Direction.TO_SERVER, self.on_send_message, "SendMsg")
        extension.intercept(
            Direction.TO_SERVER, self.on_get_profile, "GetExtendedProfile"
        )

    def should_open_chat(self, hmessage: HMessage) -> None:
        if not self._chat_opened:
            self._chat_opened = True

            if hmessage.packet.header_id != 4000:
                self._once_per_connection = True
                self.create_chat()

    def on_friend_list(self, ignored_hmessage: HMessage) -> None:
        if not self._once_per_connection:
            self._once_per_connection = True

            time.sleep(1)
            self.create_chat()

    def on_send_message(self, hmessage: HMessage) -> None:
        packet = hmessage.packet

        if packet.read_int() == self._bot_settings.id:
            hmessage.is_blocked = True
            message = packet.read_string()

            prefix, raw_message = message[0], message[1:]

            if message.startswith(prefix) and raw_message in self._commands.keys():
                self._commands[raw_message]()

    def on_get_profile(self, hmessage: HMessage) -> None:
        if hmessage.packet.read_int() == self._bot_settings.id:
            bot = self._bot_settings

            packet = HPacket("ExtendedProfile", bot.id, bot.username, bot.figure, bot.motto, bot.creation_date,
                             bot.achievement_score, bot.friend_count, bot.is_friend, bot.is_requested_friend,
                             bot.is_online, 0, -255, True)

            self._extension.send_to_client(packet)

            self._extension.send_to_client(
                HPacket("HabboUserBadges", bot.id, 1, 1, "BOT")
            )

    def create_chat(self) -> None:
        bot = self._bot_settings

        packet = HPacket("FriendListUpdate", 0, 1, False, False, "", bot.id, bot.username, bot.gender, bot.is_online,
                         bot.is_following_allowed, bot.figure, bot.category_id, bot.motto, 0,
                         bot.is_persisted_message_user, bot.is_vip_member, bot.is_pocket_habbo_user, 65537)

        self._extension.send_to_client(packet)

    def send(self, message: str, as_invite: bool = False) -> None:
        if as_invite:
            self._extension.send_to_client(
                HPacket("RoomInvite", self._bot_settings.id, message)
            )

            return None

        self._extension.send_to_client(
            HPacket("NewConsole", self._bot_settings.id, message, 0, "")
        )

    def add_command(self, command: str, callback: Callable) -> None:
        self._commands[command] = callback
