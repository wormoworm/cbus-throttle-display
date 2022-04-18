import sys
import logging
import asyncio
import signal
from rich.logging import RichHandler
from cbus import CbusMessage, CbusInterface

DEBUG = True
CAN_INTERFACE = "can0"
CAN_BITRATE = 125000

cbus_interface: CbusInterface

def cbus_message_listener(cbus_message: CbusMessage):
    logging.debug(f"Opcode: {cbus_message.op_code}")

    # pylint: disable=unused-argument
def os_signal_handler(signum, frame):
    """Handle OS signal"""
    logging.debug(f"Received signal from OS ({0}), shutting down gracefully...".format(signum))
    cbus_interface.close()
    sys.exit()

if __name__ == "__main__":
    # Set up rich logging.
    logging.basicConfig(
        level="DEBUG" if DEBUG else "WARNING",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(omit_repeated_times=False)],
    )

    # Register a function to be invoked when we receive SIGTERM or SIGHUP.
    # This allows us to act on these events, which are sent when the program execution is halted, or when systemd wants to stop the service.
    signal.signal(signal.SIGINT, os_signal_handler)
    signal.signal(signal.SIGTERM, os_signal_handler)
    signal.signal(signal.SIGHUP, os_signal_handler)

    cbus_interface = CbusInterface(CAN_INTERFACE, CAN_BITRATE)
    loop = asyncio.get_event_loop()
    loop.create_task(cbus_interface.listen(cbus_message_listener))
    loop.run_forever()
