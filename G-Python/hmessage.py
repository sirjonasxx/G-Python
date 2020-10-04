import sys
from enum import Enum

from hpacket import HPacket

class Direction(Enum):
    TO_SERVER = 0
    TO_CLIENT = 1

class HMessage:
    def __init__(self, packet, direction, index, is_blocked=False):
        self.packet = packet
        self.direction = direction
        self.index = index
        self.is_blocked = is_blocked

    @classmethod
    def reconstruct_from_java(cls, extension, string):
        obj = cls.__new__(cls)
        super(HMessage, obj).__init__()

        split = string.split(' ', 3)
        obj.is_blocked = split[0] == '1'
        obj.index = int(split[1])
        obj.direction = Direction.TO_CLIENT if split[2] == 'TOCLIENT' else Direction.TO_SERVER
        obj.packet = HPacket.reconstruct_from_java(extension, split[3])
        return obj

    def __repr__(self):
        return "{}\t{}\t{}\t{}".format(
            '1' if self.is_blocked else '0',
            self.index,
            'TOCLIENT' if self.direction == Direction.TO_CLIENT else 'TOSERVER',
            repr(self.packet)
        )
