import threading
from g_python.hmessage import Direction, HMessage
from g_python.hpacket import HPacket
from g_python.gextension import Extension


class Bot:
    def __init__(self, extension: Extension, bot_id=99999999, botname="ConsoleBot", figurestring="hd-3704-29"):
        self.__ext = extension
        self.bot_id = bot_id
        self.botname = botname
        self.figure_string = figurestring
        self.commands = dict()

    def show_profile(self, message: HMessage):
        if message.packet.read_int() == self.bot_id:
            self.__ext.send_to_client(HPacket('ExtendedProfile', self.bot_id, self.botname, self.figure_string, str(),
                                              "17/07/2021", 0, 1, True, False, True, 0, -255, True))
            self.__ext.send_to_client(HPacket('HabboUserBadges', self.bot_id, 1, 1, 'BOT'))

    def on_command(self, command, callback):
        self.commands.update({command: callback})

    def command_handler(self, message: HMessage):
        if message.packet.read_int() == self.bot_id:
            received_message = message.packet.read_string()
            for command, callback in self.commands.items():
                if received_message.startswith(command):
                    command_callback = threading.Thread(target=callback, args=received_message[len(command):])
                    command_callback.start()


    def send_message(self, args):
        self.__ext.send_to_client(HPacket('NewConsole', self.bot_id, args, 0, str()))

    @staticmethod
    def block_msg(message: HMessage):
        message.is_blocked = True

    def start(self):
        self.__ext.send_to_client(HPacket('FriendListUpdate', 0, 1, False, False, "",
                                          self.bot_id, "[BOT] " + self.botname, 1, True, False, self.figure_string,
                                          0, "", 0, True, True, True, 65537))

        self.__ext.intercept(Direction.TO_SERVER, self.show_profile, 'GetExtendedProfile')
        self.__ext.intercept(Direction.TO_SERVER, self.command_handler, 'SendMsg')
        self.__ext.intercept(Direction.TO_CLIENT, self.block_msg, 'ErrorReport', mode="async_modify")

    def hide_bot(self):
        self.__ext.send_to_client(HPacket('FriendListUpdate', 0, 1, -1, self.bot_id))
