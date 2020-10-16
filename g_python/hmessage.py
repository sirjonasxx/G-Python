from .hpacket import HPacket
from .hdirection import Direction


class HMessage:
    def __init__(self, packet: HPacket, direction: Direction, index: int, is_blocked=False):
        self.packet = packet
        self.direction = direction
        self._index = index
        self.is_blocked = is_blocked

    @classmethod
    def reconstruct_from_java(cls, string):
        obj = cls.__new__(cls)
        super(HMessage, obj).__init__()

        split = string.split('\t', 3)
        obj.is_blocked = split[0] == '1'
        obj._index = int(split[1])
        obj.direction = Direction.TO_CLIENT if split[2] == 'TOCLIENT' else Direction.TO_SERVER
        obj.packet = HPacket.reconstruct_from_java(split[3])
        return obj

    def __repr__(self):
        return "{}\t{}\t{}\t{}".format(
            '1' if self.is_blocked else '0',
            self._index,
            'TOCLIENT' if self.direction == Direction.TO_CLIENT else 'TOSERVER',
            repr(self.packet)
        )

    def index(self):
        return self._index
