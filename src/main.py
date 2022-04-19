import sys
import logging
import asyncio
import signal
from rich.logging import RichHandler
from cbus import CbusInterface
from cbus_messages import CbusMessage, CbusMessageEngineReport, CbusMessageRequestEngineSession, CbusMessageSetEngineFunctions, CbusMessageSetEngineSpeedDir, CbusMessageReleaseEngine, Direction, FunctionState

DEBUG = True
CAN_INTERFACE = "can0"
CAN_BITRATE = 125000

cbus_interface: CbusInterface

def cbus_message_listener(cbus_message: CbusMessage):
    if isinstance(cbus_message, CbusMessageRequestEngineSession):
        logging.debug("Engine request for address: %d", cbus_message.address)
    elif isinstance(cbus_message, CbusMessageReleaseEngine):
        logging.debug("Release engine request for session: %d", cbus_message.session_id)
    elif isinstance(cbus_message, CbusMessageEngineReport):
        logging.debug("Engine report for session: %d", cbus_message.session_id)
        logging.debug("Engine report address: %d", cbus_message.address)
        logging.info("Speed is %d", cbus_message.speed)
        if cbus_message.direction == Direction.FORWARD:
            logging.info("Direction is forward")
    elif isinstance(cbus_message, CbusMessageSetEngineSpeedDir):
        logging.info("Speed is %d", cbus_message.speed)
        if cbus_message.direction == Direction.FORWARD:
            logging.info("Direction is forward")
    elif isinstance(cbus_message, CbusMessageSetEngineFunctions):
        for function in cbus_message.functions:
            logging.debug("F%d is %s", function.number, FunctionState(function.state))

    # pylint: disable=unused-argument
def os_signal_handler(signum, frame):
    """Handle OS signal"""
    logging.debug(f"Received signal from OS ({signum}), shutting down gracefully...")
    cbus_interface.close()
    sys.exit()

if __name__ == "__main__":
    # Set up rich logging.
    logging.basicConfig(
        level="DEBUG" if DEBUG else "INFO",
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
