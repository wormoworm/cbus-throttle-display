from audioop import add
import logging
from typing import List
from cbus_messages import Function, Direction
from requests import get, Response
import json

MAX_FUNCTIONS = 28

class ThrottleHelper:

    # _address: int
    roster_entry: dict = None
    speed: int = None
    direction: Direction = None
    functions: dict = {}

    def set_address(self, address: int):
        # TODO: Fetch from roster API.
        logging.debug("Fetching details for address %s", address)
        roster_entry_response = get(f"https://roster.tomstrains.co.uk/api/v2/roster_entry/address/{address}")
        if roster_entry_response.status_code == 200:
            self.process_roster_entry_response(roster_entry_response)
        else:
            logging.error("Could not fetch roster entry with address %d (error code %d)", address, roster_entry_response.status_code)
    
    def process_roster_entry_response(self, roster_entry_response: Response):
        self.roster_entry = roster_entry_response.json()["roster_entry"]
        # logging.debug(json.dumps(self.roster_entry, indent=4))


    def release(self):
        self.roster_entry = None
        self.speed = None
        self.direction = None
        self.functions.clear()
        logging.debug("Released")

    
    def get_function(self, function_number: int) -> dict:
        for i in range(MAX_FUNCTIONS):
            try:
                function = self.roster_entry["functions"][i]
                if function["number"] == function_number:
                    return function
            except IndexError:
                pass
        raise IndexError

    
    def set_function_states(self, functions: List[Function]):
        for function in functions:
            self.functions[function.number] = function.state
