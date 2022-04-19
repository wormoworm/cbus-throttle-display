from enum import IntEnum
import logging
from tkinter import OFF
from typing import List
from can import Message

class CbusOpcode(IntEnum):
    KLOC = 33
    RLOC = 64
    DSPD = 71
    DFUN = 96
    PLOC = 225


class Direction(IntEnum):
    REVERSE = 0
    FORWARD = 1


class FunctionState(IntEnum):
    OFF = 0
    ON = 1


class Function:

    number: int = 0
    state: FunctionState = OFF

    def __init__(self, number: int, state: FunctionState):
        self.number = number
        self.state = state


def set_bit(value, bit):
    return value | (1<<bit)


def clear_bit(value, bit):
    return value & ~(1<<bit)


def get_decoder_address(upper_byte: int, lower_byte: int) -> int:
    # logging.debug("Upper byte: %d", upper_byte)
    # logging.debug("Lower byte: %d", lower_byte)
    return clear_bit(clear_bit(upper_byte, 7), 6) * 256 + lower_byte


def get_direction(byte: int) -> Direction:
    return (byte & 0x80) >> 7


def map_nmra_speed_to_friendly_speed(nmra_speed: int) -> int:
    if nmra_speed == 0:
        return 0
    elif nmra_speed == 1:
        return -1
    else:
        return nmra_speed - 1


def get_speed(byte: int) -> int:
    return map_nmra_speed_to_friendly_speed(byte & 0x7F)


def get_bit_position_for_function_number(function_number: int) -> int:
    if function_number == 0:            # Special case - F0 is bit 4 for some reason...
        return 4
    elif function_number <= 4:          # F1 to F4.
        return function_number - 1
    elif function_number <= 8:          # F5 to F8.
        return function_number - 5
    elif function_number <= 12:         # F9 to F12
        return function_number - 9
    elif function_number <= 20:         # F13 to F20
        return function_number - 13
    elif function_number <= 28:         # F21 to F28
        return function_number - 21


def get_function_state(byte: int, function_number: int) -> FunctionState:
    bit_position = get_bit_position_for_function_number(function_number)
    return (byte >> bit_position) & 0x01


def parse_functions(byte: int, first_function_number: int, n_functions: int) -> List[Function]:
    functions = []
    for i in range(first_function_number, first_function_number + n_functions):
        functions.append(Function(i, get_function_state(byte, i)))
    return functions


class CbusMessage:

    id: int
    op_code: int

    def __init__(self, can_message: Message):
        self.id = can_message.arbitration_id
        self.op_code = can_message.data[0]
        

class CbusMessageRequestEngineSession(CbusMessage):

    address: int

    def __init__(self, can_message: Message):
        super().__init__(can_message)
        self.address = get_decoder_address(can_message.data[1], can_message.data[2])


class CbusSessionMessage(CbusMessage):

    session_id: int

    def __init__(self, can_message: Message):
        super().__init__(can_message)
        self.session_id = can_message.data[1]


class CbusMessageReleaseEngine(CbusSessionMessage):

    def __init__(self, can_message: Message):
        super().__init__(can_message)


class CbusMessageSetEngineSpeedDir(CbusSessionMessage):

    direction: Direction
    speed: int

    def __init__(self, can_message: Message):
        super().__init__(can_message)
        self.direction = get_direction(can_message.data[2])
        self.speed = get_speed(can_message.data[2])


class CbusMessageEngineReport(CbusSessionMessage):

    address: int
    direction: Direction
    speed: int
    functions: List[Function]

    def __init__(self, can_message: Message):
        super().__init__(can_message)
        self.address = get_decoder_address(can_message.data[2], can_message.data[3])
        self.direction = get_direction(can_message.data[4])
        self.speed = get_speed(can_message.data[4])
        self.functions = []
        self.functions.extend(parse_functions(can_message.data[5], 0, 5))
        self.functions.extend(parse_functions(can_message.data[6], 5, 4))
        self.functions.extend(parse_functions(can_message.data[7], 9, 4))


class CbusMessageSetEngineFunctions(CbusSessionMessage):

    functions: List[Function]

    def __init__(self, can_message: Message):
        super().__init__(can_message)
        function_range = can_message.data[2]
        function_byte = can_message.data[3]
        logging.debug("Function range: %d", function_range)
        if function_range == 1:
            self.functions = parse_functions(function_byte, 0, 5)
        if function_range == 2:
            self.functions = parse_functions(function_byte, 5, 4)
        if function_range == 3:
            self.functions = parse_functions(function_byte, 9, 4)
        if function_range == 4:
            self.functions = parse_functions(function_byte, 13, 8)
        if function_range == 5:
            self.functions = parse_functions(function_byte, 21, 8)