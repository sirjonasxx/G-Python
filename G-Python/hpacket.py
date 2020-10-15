import hmessage

class HPacket:
    default_extension = None

    def __init__(self, id, *objects):
        self.delayed_id = None if (type(id) is int) else id
        self.fill_id()

        self.read_index = 6
        self.bytearray = bytearray(b'\x00\x00\x00\x02\x00\x00')
        if self.delayed_id is None:
            self.replace_ushort(4, id)
        self.is_edited = False

        for object in objects:
            if type(object) is str:
                self.append_string(object)
            if type(object) is int:
                self.append_int(object)
            if type(object) is bool:
                self.append_bool(object)
            if type(object) is bytes:
                self.append_bytes(object)

        self.is_edited = False

    def fill_id(self, extension = None, direction = None):
        if self.delayed_id is not None:
            if extension is None:
                if self.default_extension is None:
                    return False
                extension = self.default_extension
            if direction is None:
                if extension.harble_api is None:
                    return False
                if (self.delayed_id in extension.harble_api[hmessage.Direction.TO_CLIENT]) is not \
                    (self.delayed_id in extension.harble_api[hmessage.Direction.TO_SERVER]):
                    direction = hmessage.Direction.TO_CLIENT if \
                        (self.delayed_id in extension.harble_api[hmessage.Direction.TO_CLIENT]) else hmessage.Direction.TO_SERVER
                else:
                    return False

            if extension.harble_api is not None and self.delayed_id in extension.harble_api[direction]:
                edited_old = self.is_edited
                self.replace_ushort(4, extension.harble_api[direction][self.delayed_id]['Id'])
                self.is_edited = edited_old
                self.delayed_id = None
                return True
            return False
        return True

    # https://stackoverflow.com/questions/682504/what-is-a-clean-pythonic-way-to-have-multiple-constructors-in-python
    @classmethod
    def from_bytes(cls, bytes):
        obj = cls.__new__(cls)  # Does not call __init__
        super(HPacket, obj).__init__()  # Don't forget to call any polymorphic base class initializers
        obj.bytearray = bytearray(bytes)
        obj.read_index = 6
        obj.is_edited = False
        return obj

    @classmethod
    def from_string(cls, string, extension = None):
        if extension is None:
            if HPacket.default_extension is None:
                raise Exception('No extension given for string <-> packet conversion')
            else:
                extension = HPacket.default_extension
        return extension.string_to_packet(string)

    @classmethod
    def reconstruct_from_java(cls, string):
        obj = cls.__new__(cls)
        super(HPacket, obj).__init__()
        obj.read_index = 6

        obj.bytearray = bytearray(string[1:].encode("iso-8859-1"))
        obj.is_edited = string[0] == '1'
        obj.delayed_id = None
        return obj

    def __repr__(self):
        return ('1' if self.is_edited else '0') + self.bytearray.decode("iso-8859-1")

    def __bytes__(self):
        return bytes(self.bytearray)

    def __len__(self):
        return self.read_int(0)

    def __str__(self):
        return "(id:{}, length:{}) -> {}".format(self.header_id() if self.delayed_id is None else self.delayed_id,
                                                 len(self), bytes(self))

    def g_string(self, extension = None):
        self.fill_id(extension)
        if extension is None:
            if HPacket.default_extension is None:
                raise Exception('No extension given for packet <-> string conversion')
            else:
                extension = HPacket.default_extension
        if self.delayed_id is not None:
            raise Exception('Please initialize the packet with packet.fill_id(ext, Direction.XXX), if that doesn\'t '
                            'work, HarbleAPI does not contain your hash')

        return extension.packet_to_string(self)

    def g_expression(self, extension = None):
        self.fill_id(extension)
        if extension is None:
            if HPacket.default_extension is None:
                raise Exception('No extension given for packet <-> string conversion')
            else:
                extension = HPacket.default_extension
        if self.delayed_id is not None:
            raise Exception('Please initialize the packet with packet.fill_id(ext, Direction.XXX)')

        return extension.packet_to_expression(self)

    def is_corrupted(self):
        return self.delayed_id is not None or len(self.bytearray) < 6 or self.read_int(0) != len(self.bytearray) - 4

    def reset(self):
        self.read_index = 6

    def header_id(self):
        return self.read_ushort(4)

    def fix_length(self):
        self.replace_int(0, len(self.bytearray) - 4)

    def read_int(self, index=None):
        if index is None:
            index = self.read_index
            self.read_index += 4

        return int.from_bytes(self.bytearray[index:index + 4], byteorder='big')

    def read_ushort(self, index=None):
        if index is None:
            index = self.read_index
            self.read_index += 2

        return int.from_bytes(self.bytearray[index:index + 2], byteorder='big', signed=False)

    def read_string(self, index=None, head=2, encoding='iso-8859-1'):
        if index is None:
            index = self.read_index
            self.read_index += head + int.from_bytes(self.bytearray[index:index + head], byteorder='big', signed=False)

        len = int.from_bytes(self.bytearray[index:index + head], byteorder='big', signed=False)
        return self.bytearray[index + head:index + head + len].decode(encoding)

    def read_bytes(self, len, index=None):
        if index is None:
            index = self.read_index
            self.read_index += len

        return self.bytearray[index:index + len]

    def read_byte(self, index=None):
        if index is None:
            index = self.read_index
            self.read_index += 1

        return self.bytearray[index]

    def read_bool(self, index=None):
        return self.read_byte(index) != 0

    def read(self, structure):
        read_methods = {
            'i': self.read_int,
            's': self.read_string,
            'b': self.read_byte,
            'B': self.read_bool
        }
        return [read_methods[value_type]() for value_type in structure]

    def replace_int(self, index, value):
        self.bytearray[index:index + 4] = value.to_bytes(4, byteorder='big')
        self.is_edited = True

    def replace_ushort(self, index, value):
        self.bytearray[index:index + 2] = value.to_bytes(2, byteorder='big', signed=False)
        self.is_edited = True

    def replace_bool(self, index, value):
        self.bytearray[index] = value
        self.is_edited = True

    def replace_string(self, index, value, encoding='utf-8'):
        old_len = self.read_ushort(index)
        part1 = self.bytearray[0:index]
        part3 = self.bytearray[index + 2 + old_len:]

        new_string = value.encode(encoding)
        new_len = len(new_string)
        part2 = new_len.to_bytes(2, byteorder='big', signed=False) + new_string

        self.bytearray = part1 + part2 + part3
        self.fix_length()
        self.is_edited = True

    def append_int(self, value):
        self.bytearray.extend(value.to_bytes(4, byteorder='big'))
        self.fix_length()
        self.is_edited = True
        return self

    def append_ushort(self, value):
        self.bytearray.extend(value.to_bytes(2, byteorder='big', signed=False))
        self.fix_length()
        self.is_edited = True
        return self

    def append_bytes(self, value):
        self.bytearray.extend(value)
        self.fix_length()
        self.is_edited = True
        return self

    def append_bool(self, value):
        self.append_bytes(b'\x01' if value else b'\x00')
        self.fix_length()
        self.is_edited = True
        return self

    def append_string(self, value, head=2, encoding='utf-8'):
        b = value.encode(encoding)
        self.bytearray.extend(len(b).to_bytes(head, byteorder='big', signed=False) + b)
        self.fix_length()
        self.is_edited = True
        return self
