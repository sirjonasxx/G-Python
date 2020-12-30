from enum import Enum

from g_python.hparsers import HPoint, HEntityType


class HUnityEntity:
    def __init__(self, packet):
        self.id, self.name, self.motto, self.figure_id, self.index, x, y, z, _, entity_type_id = \
            packet.read('lsssiiisii')

        try:
            z = float(z)
        except ValueError:
            z = 0.0

        self.tile = HPoint(x, y, z)
        self.entity_type = HEntityType(entity_type_id)

        self.stuff = []
        if self.entity_type == HEntityType.HABBO:
            self.gender = packet.read_string()
            self.stuff.extend(packet.read('iii'))
            self.favorite_group = packet.read_string()
            self.stuff.extend(packet.read('siB'))
        elif self.entity_type == HEntityType.PET:
            self.stuff.append(packet.read_int())
            self.owner_id, self.owner_name = packet.read('ls')
            self.stuff.extend(packet.read("iisis"))
        elif self.entity_type == HEntityType.BOT:
            self.gender, self.owner_id, self.owner_name, arr_length = packet.read('slsu')
            self.stuff.append(arr_length)
            for _ in range(arr_length):
                self.stuff.append(packet.read_ushort())

    def __str__(self):
        return '{}: {} - {}'.format(self.index, self.name, self.entity_type.name)

    @classmethod
    def parse(cls, packet):
        u1 = packet.read_bytes(2)
        length = u1[0] << 8 | u1[1]
        return [HUnityEntity(packet) for _ in range(length)]
