from audioop import add
import logging
from typing import List
from cbus_messages import Function, Direction

class ThrottleHelper:

    # _address: int
    roster_entry: dict = None
    speed: int = None
    direction: Direction = None
    functions: dict = {}

    def set_address(self, address: int):
        # TODO: Fetch from roster API.
        logging.debug("Fetching details for address %d", address)
    

    def release(self):
        self.roster_entry = None
        self.speed = None
        self.direction = None
        self.functions.clear()
        logging.debug("Released")

    
    def set_function_states(self, functions: List[Function]):
        for function in functions:
            self.functions[function.number] = function.state
