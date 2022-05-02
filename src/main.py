from gettext import install
import sys
import os
import logging
import asyncio
import signal
from turtle import width
from rich.logging import RichHandler
from cbus import CbusInterface
from cbus_messages import CbusMessage, CbusMessageEngineReport, CbusMessageRequestEngineSession, CbusMessageSetEngineFunctions, CbusMessageSetEngineSpeedDir, CbusMessageReleaseEngine, CbusSessionMessage, Direction, FunctionState
from throttle_helper import ThrottleHelper
import PySimpleGUI as sg
import textwrap
from PIL import Image
from io import BytesIO
import requests

DEBUG = False
CAN_INTERFACE = "can0"
CAN_BITRATE = 125000

FONT_H1 = "_ 30"
FONT_H2 = "_ 24"
FONT_H3 = "_ 18"
FONT_H4 = "_ 16"
FONT_BODY  = "_ 12"
FONT_LABEL = "_ 10 bold"
FONT_VALUE = "_ 14"

cbus_interface: CbusInterface

pending_address: str = None
session_id: int = None

throttle_helper = ThrottleHelper()

roster_entry_window: sg.Window = None

def is_session_set() -> bool:
    return session_id is not None


def set_session_id(id: int):
    global session_id
    session_id = id


def is_session_message_relevant(session_message: CbusSessionMessage) -> bool:
    return session_message.session_id == session_id


def update_throttle_helper_from_engine_report(engine_report_message: CbusMessageEngineReport):
    throttle_helper.speed = engine_report_message.speed
    throttle_helper.direction = engine_report_message.direction
    throttle_helper.set_function_states(engine_report_message.functions)


def process_session_message(session_message: CbusSessionMessage):
    global session_id, throttle_helper, roster_entry_window
    if isinstance(session_message, CbusMessageReleaseEngine):
        logging.debug("Release engine request for session: %d", session_message.session_id)
        throttle_helper.release()
        session_id = None
        if roster_entry_window:
            roster_entry_window.close()
    elif isinstance(session_message, CbusMessageEngineReport):
        logging.debug("Engine report for session: %d", session_message.session_id)
        update_throttle_helper_from_engine_report(session_message)
    elif isinstance(session_message, CbusMessageSetEngineSpeedDir):
        logging.debug("Speed / direction for session:  %d", session_message.session_id)
        throttle_helper.speed = session_message.speed
        throttle_helper.direction = session_message.direction
        if roster_entry_window:
            logging.debug("Updating speed, will be %d", throttle_helper.speed)
            # roster_entry_window["speed"].update(f"Speed: {throttle_helper.speed}")  # TODO: Not working
    elif isinstance(session_message, CbusMessageSetEngineFunctions):
        logging.debug("Functions for session:  %d", session_message.session_id)
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
                display_roster_entry_window()
                pending_address = None
            else:
                logging.error("Received a CbusMessageEngineReport, but address did not match pending address.")
        else:
            logging.error("Received a CbusMessageEngineReport, but pending address is not set.")


def create_function_grid_item(function_number: int, alternate_bg_colour: bool):
    global throttle_helper
    background_colour = "#151515" if alternate_bg_colour else "#1F1F1F"
    function_label_text = f"F{function_number}"
    try:
        function = throttle_helper.get_function(function_number)
        function_name = sg.Text(f"{function['name']}", expand_x=True, pad=2, background_color=background_colour, font=FONT_VALUE)
        if not function["lockable"]:
            function_label_text+= " (mom)"
    except IndexError:
        function_name = sg.Text("", background_color=background_colour)
    function_label = sg.Text(function_label_text, expand_x=True, size=(18,1), pad=2, background_color=background_colour, font=FONT_LABEL)
    layout = [ [function_label], [function_name]]
    return sg.Frame(title=None, layout=layout, pad=2, expand_y=True, background_color=background_colour, border_width=0)


def display_roster_entry_window():
    global roster_entry_window, throttle_helper

    if os.environ.get('DISPLAY','') == '':
        logging.warning('no display found. Using :0.0')
        os.environ.__setitem__('DISPLAY', ':0.0')
    
    # Set the theme
    sg.theme('Black')
    # All the stuff inside your window.

    info_items = []

    info_number = sg.Frame(title=None, layout=[[sg.Text("Number", font=FONT_LABEL)], [sg.Text(throttle_helper.roster_entry["number"], size=(8,1), font=FONT_H2)]], pad=0, border_width=0)
    info_address = sg.Frame(title=None, layout=[[sg.Text("Address", font=FONT_LABEL)], [sg.Text(throttle_helper.roster_entry["dcc_address"], size=(5,1), font=FONT_H2)]], pad=0, border_width=0)

    info_items.append([info_number, info_address])
    lhs_items = []

    if throttle_helper.roster_entry["name"]:
        # Use textwrap to ensure the name fits, breaking into multiple lines if necessary
        for name_piece in textwrap.wrap(throttle_helper.roster_entry["name"], 25):
            info_items.append([sg.Text(name_piece, font=FONT_H2)])
    
    info_height = 600
    if throttle_helper.roster_entry["image_file_path"]:
        with Image.open(requests.get(f"https://roster.tomstrains.co.uk/api/v2/roster_entry/{throttle_helper.roster_entry['roster_id']}/image?size=502", stream=True).raw) as image:
            image_bytes = BytesIO()
            image.save(image_bytes, format="png")
            # Calculate the image's aspect ratio, so that was can resize it correctly
            width, height = image.size
            aspect_ratio = width / height
            desired_width = 502
            desired_height = desired_width / aspect_ratio
            lhs_items.append([sg.Image(source=image_bytes.getvalue(), size=(desired_width, desired_height), pad=0)])
            info_height-= desired_height
    

    info_section = sg.Frame(title=None, layout=info_items, size=(502, info_height), pad=0, border_width=0)
    lhs_items.insert(0, [info_section])

    lhs = sg.Column(lhs_items, pad=0, size=(502, 600))

    functions = [[create_function_grid_item(row + (column * 10), (row + column) % 2 == 0) for column in range(3)] for row in range(10)]
    functions_section = sg.Column(functions, expand_y=True, pad=0)

    layout = [  [lhs, functions_section] ]
    roster_entry_window = sg.Window(title="Hello World", layout=layout, no_titlebar=True, location=(0,0), size=(1024,600), margins=(0,0), keep_on_top=True, background_color="#657381").Finalize()
    # Hide the mouse cursor. # TODO: Not working
    roster_entry_window.set_cursor("none")

# async def test_gui():
#     global throttle_helper
#     if os.environ.get('DISPLAY','') == '':
#         logging.warning('no display found. Using :0.0')
#         os.environ.__setitem__('DISPLAY', ':0.0')
#     gui.theme('DarkAmber')   # Add a touch of color
# # All the stuff inside your window.

#     window: gui.Window = None
    
#     # Create the Window
#     while True:
#         # window = gui.Window(title="Hello World", layout=layout, no_titlebar=True, location=(0,0), size=(1024,600), keep_on_top=True).Finalize()
#         # event, values = window.read(timeout=20)

#         # if event is None:
#         #     break

#         # elif event == "_TEST_":
#         #     print("Test")

#         if window:
#             window.close()
        
#         if throttle_helper.roster_entry:
#             layout = [  [gui.Text(throttle_helper.roster_entry["name"])],
#             [gui.Text(throttle_helper.roster_entry["address"])] ]
#             window = gui.Window(title="Hello World", layout=layout, no_titlebar=True, location=(0,0), size=(1024,600), keep_on_top=True).Finalize()
        
#             # window.find_element("Name").Update(throttle_helper.roster_entry["name"])
#         else:
#             layout = [  [gui.Text("No locomotive", key = "Name")]]
#             window = gui.Window(title="Hello World", layout=layout, no_titlebar=True, location=(0,0), size=(1024,600), keep_on_top=True).Finalize()


#         await asyncio.sleep(0.1)
#     window.Close()

    # pylint: disable=unused-argument
def os_signal_handler(signum, frame):
    """Handle OS signal"""
    logging.debug(f"Received signal from OS ({signum}), shutting down gracefully...")
    cbus_interface.close()
    sys.exit()

def DUMMY_manual_load(address: str):
    global throttle_helper
    throttle_helper.set_address(address)
    # update_throttle_helper_from_engine_report(cbus_message)
    display_roster_entry_window()

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

    # test_gui()

    cbus_interface = CbusInterface(CAN_INTERFACE, CAN_BITRATE)
    loop = asyncio.get_event_loop()
    loop.create_task(cbus_interface.listen(cbus_message_listener))
    # loop.create_task(test_gui())
    # TODO:TEMP
    DUMMY_manual_load("6957")
    loop.run_forever()
