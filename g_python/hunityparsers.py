from enum import Enum
from struct import unpack

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
                self.stuff.append(packet.read_short())

    def __str__(self):
        return '<HUnityEntity> [{}] {} - {}'.format(self.index, self.name, self.entity_type.name)

    @classmethod
    def parse(cls, packet):
        return [HUnityEntity(packet) for _ in range(packet.read_short())]


class HUnityStatus:
    def __init__(self, packet):
        self.index, x, y, z, dir1, dir2, self.action = packet.read('iiisiis')
        self.tile = get_tile_from_coords(x, y, z)
        self.headFacing = HDirection(dir1)
        self.bodyFacing = HDirection(dir2)
        self.nextTile = self.predict_next_tile()

    def __str__(self):
        return '<HUnityStatus> [{}] - X: {} - Y: {} - Z: {} - head {} - body {} - next tile {}'\
            .format(self.index, self.tile.x, self.tile.y, self.tile.z, self.headFacing.name, self.bodyFacing.name, self.nextTile)

    def predict_next_tile(self):
        actions = self.action.split('/mv ')
        if len(actions) > 1:
            (x, y, z) = actions[1].replace('/', '').split(',')
            return get_tile_from_coords(int(x), int(y), z)
        else:
            return HPoint(-1, -1, 0.0)

    @classmethod
    def parse(cls, packet):
        return [HUnityStatus(packet) for _ in range(packet.read_short())]


def get_tile_from_coords(x, y, z) -> HPoint:
    try:
        z = float(z)
    except ValueError:
        z = 0.0

    return HPoint(x, y, z)


def read_stuff(packet, category):
    stuff = []
    cat2 = category & 0xFF

    if cat2 == 0:  # legacy
        stuff.append(packet.read_string())
    if cat2 == 1:  # map
        stuff.append([packet.read('ss') for _ in range(packet.read_short())])
    if cat2 == 2:  # string array
        stuff.append([packet.read_string() for _ in range(packet.read_short())])
    if cat2 == 3:  # vote results
        stuff.extend(packet.read('si'))
    if cat2 == 5:  # int array
        stuff.append([packet.read_int() for _ in range(packet.read_short())])
    if cat2 == 6:  # highscores
        stuff.extend(packet.read('sii'))
        stuff.append([(packet.read_int(), [packet.read_string() for _ in range(packet.read_short())]) for _ in
                      range(packet.read_int())])
    if cat2 == 7:  # crackables
        stuff.extend(packet.read('sii'))

    if (category & 0xFF00 & 0x100) > 0:
        stuff.extend(packet.read('ii'))

    return stuff


class HFUnityFloorItem:
    def __init__(self, packet):
        self.id, self.type_id, x, y, facing_id = packet.read('liiii')

        # https://en.wikipedia.org/wiki/IEEE_754
        z = unpack('>f', bytearray(packet.read('bbbb')))[0]

        self.tile = HPoint(x, y, z)
        self.facing = HDirection(facing_id)

        # another weird float
        self.height = unpack('>f', bytearray(packet.read('bbbb')))[0]

        a, b, self.category = packet.read('iii')
        self.stuff = read_stuff(packet, self.category)

        self.seconds_to_expiration, self.usage_policy, self.owner_id = packet.read('iil')
        self.owner = None  # expected to be filled in by parse class method

        if self.type_id < 0:
            packet.read_string()

    @classmethod
    def parse(cls, packet):
        owners = {}
        for _ in range(packet.read_short()):
            id = packet.read_long()
            owners[id] = packet.read_string()

        furnis = [HFUnityFloorItem(packet) for _ in range(packet.read_short())]
        for furni in furnis:
            furni.owner = owners[furni.owner_id]

        return furnis