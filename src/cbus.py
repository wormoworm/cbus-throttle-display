import os
import time
import can
import logging
import asyncio
from rich.logging import RichHandler
from can import Message
from typing import Callable

class CbusMessage:

    id: int
    op_code: int
    data: bytearray

    def __init__(self, id: int, op_code: int, data: bytearray):
        self.id = id
        self.op_code = op_code
        self.data = data

class CbusInterface:

    interface: str
    bus: can.interface.Bus = None
    notifier: can.Notifier = None
    listener: Callable[[CbusMessage], None]

    def __init__(self, interface: str, bitrate: int):
        self.interface = interface
        logging.debug(f"Configuring {interface} at {bitrate}bps")
        os.system(f"sudo ip link set {interface} type can bitrate {bitrate}")
        logging.debug(f"Enabling {interface}")
        os.system(f"sudo ifconfig {interface} up")
        time.sleep(0.1)
        os.system(f"sudo ifconfig {interface} txqueuelen 1000")
        time.sleep(0.1)
    
    def close(self):
        self.notifier.stop()
        self.bus.shutdown()
        logging.debug(f"Disabling {self.interface}")
        os.system(f"sudo ifconfig {self.interface} down")
    
    async def listen(self, listener: Callable[[CbusMessage], None]):
        self.listener = listener
        self.bus = can.interface.Bus(channel = self.interface, bustype = "socketcan")
        logging.debug(f"Listening to {self.interface}")
        # Create Notifier with an explicit loop to use for scheduling of callbacks
        self.notifier = can.Notifier(self.bus, listeners = [self.on_message_received], loop = asyncio.get_event_loop())

    def on_message_received(self, message: Message):
        # TODO: Decode message and pass to handler
        id = message.arbitration_id
        op_code = message.data[0]
        data = message.data[1:]
        cbus_message = CbusMessage(id, op_code, data)
        self.listener(cbus_message)
