from .hpacket import HPacket
from .hdirection import Direction


class HMessage:
    def __init__(self, packet: HPacket, direction: Direction, index: int, is_blocked=False):
        self.packet = packet
        self.direction = direction
        self.hindex = index
        self.is_blocked = is_blocked

    @classmethod
    def reconstruct_from_java(cls, string):
        obj = cls.__new__(cls)
        super(HMessage, obj).__init__()

        split = string.split('\t', 3)
        obj.is_blocked = split[0] == '1'
        obj.hindex = int(split[1])
        obj.direction = Direction.TO_CLIENT if split[2] == 'TOCLIENT' else Direction.TO_SERVER
        obj.packet = HPacket.reconstruct_from_java(split[3])
        return obj

    def __repr__(self):
        blocked = '1' if self.is_blocked else '0'
        direction = 'TOCLIENT' if self.direction == Direction.TO_CLIENT else 'TOSERVER'
        return f"{blocked}\t{self.hindex}\t{direction}\t{repr(self.packet)}"

    def index(self):
        return self.hindex
