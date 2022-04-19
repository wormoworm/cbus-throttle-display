from gettext import install
import sys
import logging
import asyncio
import signal
from rich.logging import RichHandler
from cbus import CbusInterface
from cbus_messages import CbusMessage, CbusMessageEngineReport, CbusMessageRequestEngineSession, CbusMessageSetEngineFunctions, CbusMessageSetEngineSpeedDir, CbusMessageReleaseEngine, CbusSessionMessage, Direction, FunctionState
from throttle_helper import ThrottleHelper

DEBUG = True
CAN_INTERFACE = "can0"
CAN_BITRATE = 125000

cbus_interface: CbusInterface

pending_address: str = None
session_id: int = None

throttle_helper = ThrottleHelper()

def is_session_set() -> bool:
    return session_id is not None


def set_session_id(id: int):
    session_id = id


def is_session_message_relevant(session_message: CbusSessionMessage) -> bool:
    return session_message.session_id == session_id


def update_throttle_helper_from_engine_report(engine_report_message: CbusMessageEngineReport):
    throttle_helper.speed = engine_report_message.speed
    throttle_helper.direction = engine_report_message.direction
    throttle_helper.set_function_states(engine_report_message.functions)


def process_session_message(session_message: CbusSessionMessage):
    if isinstance(session_message, CbusMessageReleaseEngine):
        logging.debug("Release engine request for session: %d", session_message.session_id)
        throttle_helper.release()
        session_id = None
    elif isinstance(session_message, CbusMessageEngineReport):
        logging.debug("Engine report for session: %d", session_message.session_id)
        update_throttle_helper_from_engine_report(session_message)
    elif isinstance(session_message, CbusMessageSetEngineSpeedDir):
        logging.info("Speed / direction for session:  %d", session_message.session_id)
        throttle_helper.speed = session_message.speed
        throttle_helper.direction = session_message.direction
    elif isinstance(session_message, CbusMessageSetEngineFunctions):
        logging.info("Functions for session:  %d", session_message.session_id)
        throttle_helper.set_function_states(session_message.functions)


def update_display():
    logging.debug("Update display")


def cbus_message_listener(cbus_message: CbusMessage):
    global pending_address
    # Check if the current session ID is set.
    if is_session_set():
        # Check if this message is a CbusSessionMessage.
        if isinstance(cbus_message, CbusSessionMessage):
            # A session is set, so this CbusSessionMessages should only be handled if they match the current session ID.
            if is_session_message_relevant(cbus_message):
                # The message is relevant, so process it
                process_session_message(cbus_message)
                update_display()
    # Session is not set, so if this is a CbusMessageRequestEngineSession, cache the address for later (it will be used for a lookup when the command station replies with a CbusMessageEngineReport).
    elif isinstance(cbus_message, CbusMessageRequestEngineSession):
        pending_address = cbus_message.address
    # Session is not set, so if this message is a CbusMessageEngineReport, set the session ID, and instruct the ThrottleHelper to fetch the roster entry details (using the address we cached previously).
    elif isinstance(cbus_message, CbusMessageEngineReport):
        set_session_id(cbus_message.session_id)
        if pending_address:
            if cbus_message.address == pending_address:
                throttle_helper.set_address(pending_address)
                update_throttle_helper_from_engine_report(cbus_message)
                pending_address = None
            else:
                logging.error("Received a CbusMessageEngineReport, but address did not match pending address.")
        else:
            logging.error("Received a CbusMessageEngineReport, but pending address is not set.")


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
