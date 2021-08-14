# G-Python
 G-Earth extension interface for Python. 
 
 G-Earth + G-Python allows you to create simple scripts for Habbo and run them on the fly!
 
## Installation
_Requires python >= 3.2: https://www.python.org/downloads/_  
_Note: during Windows installation, make sure to select "Add python to PATH" if you want to install G-Python extensions in G-Earth_  
![image](https://user-images.githubusercontent.com/36828922/129458391-b10339e0-5671-4b8e-b644-da417730514f.png)


Then execute the following in a terminal:
`python -m pip install g-python`

## Features
G-Python exports the following modules:

```python
from g_python.gextension import Extension
from g_python.hmessage import Direction, HMessage
from g_python.hpacket import HPacket
from g_python import hparsers
from g_python import htools
```

* At any point where a `(header)id` is required, a `name` or `hash` can be used as well, if G-Earth is connected to Harble API
* "hparsers" contains a load of useful parsers
* "htools" contains fully prepared environments for accessing your Inventory, Room Furniture, and Room Users


## Usage

Examples are available in the `tests/` folder. _(highly recommended to check out, since it contains functionality not shown underneath)_

This is a template extension with the minimal amount of code to connect with G-Earth:

```python
import sys
from g_python.gextension import Extension

extension_info = {
    "title": "Extension stuff",
    "description": "g_python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

ext = Extension(extension_info, sys.argv)   # sys.argv are the commandline arguments, for example ['-p', '9092'] (G-Earth's extensions port)
ext.start()
```
It is possible to register for events:
```python
ext.on_event('double_click', lambda: print('Extension has been clicked'))
ext.on_event('init', lambda: print('Initialized with g-earth'))
ext.on_event('connection_start', lambda: print('Connection started'))
ext.on_event('connection_end', lambda: print('Connection ended'))
```
Packet injection:
```python
# sending packets to the server
ext.send_to_server(HPacket('RoomUserAction', 1))                    # wave using harble api name
ext.send_to_server(HPacket(1843, 1))                                # wave using header Id
ext.send_to_server(HPacket('623058bd68a68267114aa8d1ee15b597', 1))  # wave using harble api hash

# sending packets from raw text:
ext.send_to_client('{l}{u:1411}{i:0}{s:"hi"}{i:0}{i:23}{i:0}{i:2}')
ext.send_to_client('[0][0][0][6][5][131][0][0][0][0]')
ext.send_to_client(HPacket.from_string('[0][0][0][6][5][131][0][0][0][0]', ext))

# string methods: 
packet = HPacket(1231, "hi", 5, "old", False, True, "lol")
expression = packet.g_expression(ext)   # G-Earth's predicted expression
g_string = packet.g_string(ext)         # G-Earth's string representation
```
Intercepting packets:
```python
# intercept & print all packets
def all_packets(message):
    packet = message.packet
    print(packet.g_string(ext))

ext.intercept(Direction.TO_CLIENT, all_packets)
ext.intercept(Direction.TO_SERVER, all_packets)


# intercept & parse specific packets
def on_walk(message):
    (x, y) = message.packet.read('ii')
    print("Walking to x:{}, y={}".format(x, y))

def on_speech(message):
    (text, color, index) = message.packet.read('sii')
    message.is_blocked = (text == 'blocked')  # block packet if speech equals "blocked"
    print("User said: {}".format(text))

ext.intercept(Direction.TO_SERVER, on_walk, 'RoomUserWalk')
ext.intercept(Direction.TO_SERVER, on_speech, 'RoomUserTalk')
```
There is much more, such as:
 * packet manipulation 
 * specific settings to be given to an Extension object
 * `hparsers`: example in `tests/user_profile.py`
 * `htools`: `tests/room_stuff.py` & `tests/inventory_items.py`
