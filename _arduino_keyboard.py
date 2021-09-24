import inspect
import logging
import struct
import threading
import traceback

import arduino.environment
from multiprocessing.connection import Client

import dragonfly
from dragonfly.actions.action_base_keyboard import BaseKeyboardAction
from dragonfly.actions.keyboard._base import BaseKeyboard
from dragonfly.actions.keyboard._win32 import Win32KeySymbols

from arduino.environment import PRESS, RELEASE, USE_ARDUINO, INTERPROCESS_ADDRESS


# check if we are disconnected every five seconds, and if so, reconnect
def interprocess_connect():
    threading.Timer(5.0, interprocess_connect).start()
    if not arduino.environment.connection:
        print("Attempting to reconnect interprocess communication")
        arduino.environment.connection = Client(INTERPROCESS_ADDRESS, authkey=b'secret password')
        print("Interprocess communication reconnected!")


interprocess_connect()


class ArduinoSymbols(Win32KeySymbols):
    """
    These are modifiers recognized by the Arduino keyboard module, documented here:
    https://www.arduino.cc/en/Reference/KeyboardModifiers
    """
    CONTROL = 128
    SHIFT = 129
    ALT = 130
    UP = 218
    DOWN = 217
    LEFT = 216
    RIGHT = 215

    # Not needed as backspace ASCII works
    BACKSPACE = 178

    TAB = 179
    RETURN = 176
    ESCAPE = 177
    INSERT = 209
    DELETE = 212
    PAGE_UP = 211
    PAGE_DOWN = 214
    HOME = 210
    END = 213
    CAPS_LOCK = 193

    F1 = 194
    F2 = 195
    F3 = 196
    F4 = 197
    F5 = 198
    F6 = 199
    F7 = 200
    F8 = 201
    F9 = 202
    F10 = 203
    F11 = 204
    F12 = 205


class ArduinoKeyboard(BaseKeyboard):
    _log = logging.getLogger("arduino")

    def __init__(self):
        pass

    @classmethod
    def send_keyboard_events(cls, events):
        try:
            for event in events:
                print(f"event = {event}")
                character, down, timeout = event[:3]
                # Some events have a keyboard class as the character as a sort of dummy placeholder to insert delay,
                # we ignore these
                print(f"Processing character: {character}")
                if character in (BaseKeyboard, ArduinoKeyboard):
                    continue

                # When the character is an integer, this typically indicate some key combination such as control+C
                if type(character) == int:
                    if character >= 144:
                        character -= 144
                        print(f"Converting character exceeding 127: {character}")
                    # Ideally we would set dragonfly.actions.keyboard.KeySymbols = ArduinoSymbols
                    # However this is not possible without modifying the dragonfly.actions.keyboard file
                    # Hence we use reflection to convert the KeySymbols code into an ArduinoSymbols code
                    key_members = inspect.getmembers(dragonfly.actions.keyboard.KeySymbols)
                    arduino_members = inspect.getmembers(ArduinoSymbols)
                    matching_member = next(iter(filter(lambda field: field[1] == character, key_members)), None)
                    if matching_member:
                        character = dict(arduino_members)[matching_member[0]]
                        print(f"Using matching member {character}")

                    # For some reason, key combinations will always use capital letters.
                    # We convert them to lowercase because capital letters will be interpreted by the Arduino keyboard
                    # module as shift + letter
                    if 65 <= character <= 90:
                        character += 32
                        print(f"Making character lowercase: {character}")
                    character = struct.pack("B", character)
                    print(f"Packing character: {character}")
                else:
                    character = character.encode("ascii")
                    print(f"Encoding character: {character}")

                # Arduino is expecting a three byte array of [character, press/release byte, null byte]
                arduino_commands = character + (PRESS if down else RELEASE) + b"\x00"
                # ARDUINO.write(arduino_commands)
                print(f"Sending command: {arduino_commands}")
                arduino.environment.connection.send(arduino_commands)
        except Exception as e:
            print("Error with interprocess communication!")
            print(traceback.format_exc())
            arduino.environment.connection = None

    @classmethod
    def get_current_layout(cls):
        return "arduino_control"

    @classmethod
    def get_typeable(cls, char, is_text=False):
        return BaseKeyboard.get_typeable(char, is_text)


# Override the keyboard with ArduinoKeyboard, redirecting events to the Arduino
# instead of the dragonfly virtual keyboard
if USE_ARDUINO:
    BaseKeyboardAction._keyboard = ArduinoKeyboard()
