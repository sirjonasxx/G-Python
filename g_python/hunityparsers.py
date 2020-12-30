from enum import Enum

from .hparsers import HPoint, HEntityType, HDirection


class HUnityEntity:
    def __init__(self, packet):
        self.id, self.name, self.motto, self.figure_id, self.index, x, y, z, _, entity_type_id = \
            packet.read('lsssiiisii')
        self.tile = get_tile_from_coords(x, y, z)
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
        return '<HUnityEntity> [{}] {} - {}'.format(self.index, self.name, self.entity_type.name)

    @classmethod
    def parse(cls, packet):
        return [HUnityEntity(packet) for _ in range(packet.read_ushort())]


class HUnityStatus:
    def __init__(self, packet):
        self.index, x, y, z, dir1, dir2, action = packet.read('iiisiis')
        self.tile = get_tile_from_coords(x, y, z)
        self.headFacing = HDirection(dir1)
        self.bodyFacing = HDirection(dir2)

    def __str__(self):
        return '<HUnityStatus> [{}] - X: {} - Y: {} - Z: {} - head {} - body {}'\
            .format(self.index, self.tile.x, self.tile.y, self.tile.y, self.headFacing.name, self.bodyFacing.name)

    @classmethod
    def parse(cls, packet):
        return [HUnityStatus(packet) for _ in range(packet.read_ushort())]


def get_tile_from_coords(x, y, z) -> HPoint:
    try:
        z = float(z)
    except ValueError:
        z = 0.0

    return HPoint(x, y, z)
