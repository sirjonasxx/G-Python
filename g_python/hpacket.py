from .hdirection import Direction
from .gextension import Extension


class HPacket:
    default_extension = None

    def __init__(self, p_id, *objects):
        self.incomplete_identifier = None if isinstance(p_id, int) else p_id

        self.read_index = 6
        self.bytearray = bytearray(b'\x00\x00\x00\x02\xff\xff')
        if self.incomplete_identifier is None:
            self.replace_short(4, p_id)
        self.is_edited = False

        for obj in objects:
            if isinstance(obj, str):
                self.append_string(object)
            if isinstance(obj, int):
                self.append_int(object)
            if isinstance(obj, bool):
                self.append_bool(object)
            if isinstance(obj, bytes):
                self.append_bytes(object)

        self.is_edited = False

    def fill_id(self, direction: Direction, extension: Extension = None) -> bool:
        if self.incomplete_identifier is not None:
            if extension is None:
                if self.default_extension is None:
                    return False
                extension = self.default_extension

            if extension.packet_infos is not None and self.incomplete_identifier in extension.packet_infos[direction]:
                edited_old = self.is_edited
                self.replace_short(4, extension.packet_infos[direction][self.incomplete_identifier][0]['Id'])
                self.is_edited = edited_old
                self.incomplete_identifier = None
                return True
            return False
        return True

    # https://stackoverflow.com/questions/682504/what-is-a-clean-pythonic-way-to-have-multiple-constructors-in-python
    @classmethod
    def from_bytes(cls, p_bytes):
        obj = cls.__new__(cls)  # Does not call __init__
        super(HPacket, obj).__init__()  # Don't forget to call any polymorphic base class initializers
        obj.bytearray = bytearray(p_bytes)
        obj.read_index = 6
        obj.is_edited = False
        return obj

    @classmethod
    def from_string(cls, string, extension=None):
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
        obj.incomplete_identifier = None
        return obj

    def __repr__(self):
        return ('1' if self.is_edited else '0') + self.bytearray.decode("iso-8859-1")

    def __bytes__(self):
        return bytes(self.bytearray)

    def __len__(self):
        return self.read_int(0)

    def __str__(self):
        p_id = self.header_id() if not self.is_incomplete_packet() else self.incomplete_identifier
        return f"(id:{p_id}, length:{len(self)}) -> {bytes(self)}"

    def is_incomplete_packet(self) -> bool:
        return self.incomplete_identifier is not None

    def g_string(self, extension=None) -> str:
        if extension is None:
            if HPacket.default_extension is None:
                raise Exception('No extension given for packet <-> string conversion')
            else:
                extension = HPacket.default_extension

        return extension.packet_to_string(self)

    def g_expression(self, extension=None) -> str:
        if extension is None:
            if HPacket.default_extension is None:
                raise Exception('No extension given for packet <-> string conversion')
            else:
                extension = HPacket.default_extension

        return extension.packet_to_expression(self)

    def is_corrupted(self) -> bool:
        return len(self.bytearray) < 6 or self.read_int(0) != len(self.bytearray) - 4

    def reset(self) -> None:
        self.read_index = 6

    def header_id(self) -> int:
        return self.read_short(4)

    def fix_length(self) -> None:
        self.replace_int(0, len(self.bytearray) - 4)

    def read_int(self, index=None) -> int:
        if index is None:
            index = self.read_index
            self.read_index += 4

        return int.from_bytes(self.bytearray[index:index + 4], byteorder='big', signed=True)

    def read_short(self, index=None) -> int:
        if index is None:
            index = self.read_index
            self.read_index += 2

        return int.from_bytes(self.bytearray[index:index + 2], byteorder='big', signed=True)

    def read_long(self, index=None) -> int:
        if index is None:
            index = self.read_index
            self.read_index += 8

        return int.from_bytes(self.bytearray[index:index + 8], byteorder='big', signed=True)

    def read_string(self, index=None, head=2, encoding='iso-8859-1') -> str:
        if index is None:
            index = self.read_index
            self.read_index += head + int.from_bytes(self.bytearray[index:index + head], byteorder='big', signed=False)

        lenght = int.from_bytes(self.bytearray[index:index + head], byteorder='big', signed=False)
        return self.bytearray[index + head:index + head + lenght].decode(encoding)

    def read_bytes(self, lenght, index=None) -> bytearray:
        if index is None:
            index = self.read_index
            self.read_index += lenght

        return self.bytearray[index:index + lenght]

    def read_byte(self, index=None) -> int:
        if index is None:
            index = self.read_index
            self.read_index += 1

        return self.bytearray[index]

    def read_bool(self, index=None) -> bool:
        return self.read_byte(index) != 0

    def read(self, structure) -> list:
        read_methods = {
            'i': self.read_int,
            's': self.read_string,
            'b': self.read_byte,
            'B': self.read_bool,
            'u': self.read_short,
            'l': self.read_long
        }
        return [read_methods[value_type]() for value_type in structure]

    def replace_int(self, index, value) -> None:
        self.bytearray[index:index + 4] = value.to_bytes(4, byteorder='big', signed=True)
        self.is_edited = True

    def replace_short(self, index, value) -> None:
        self.bytearray[index:index + 2] = value.to_bytes(2, byteorder='big', signed=True)
        self.is_edited = True

    def replace_long(self, index, value) -> None:
        self.bytearray[index:index + 8] = value.to_bytes(8, byteorder='big', signed=False)
        self.is_edited = True

    def replace_bool(self, index, value) -> None:
        self.bytearray[index] = value
        self.is_edited = True

    def replace_string(self, index, value, encoding='utf-8') -> None:
        old_len = self.read_short(index)
        part1 = self.bytearray[0:index]
        part3 = self.bytearray[index + 2 + old_len:]

        new_string = value.encode(encoding)
        new_len = len(new_string)
        part2 = new_len.to_bytes(2, byteorder='big', signed=False) + new_string

        self.bytearray = part1 + part2 + part3
        self.fix_length()
        self.is_edited = True

    def append_int(self, value):
        self.bytearray.extend(value.to_bytes(4, byteorder='big', signed=True))
        self.fix_length()
        self.is_edited = True
        return self

    def append_short(self, value):
        self.bytearray.extend(value.to_bytes(2, byteorder='big', signed=True))
        self.fix_length()
        self.is_edited = True
        return self

    def append_long(self, value):
        self.bytearray.extend(value.to_bytes(8, byteorder='big', signed=False))
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
