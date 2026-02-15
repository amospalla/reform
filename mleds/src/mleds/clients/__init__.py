from mleds.clients.battery import Battery
from mleds.clients.kanata import Kanata
from mleds.clients.keypresses import KeyPresses
from mleds.clients.tetris import Tetris

all_clients = {
    "battery": Battery,
    "kanata": Kanata,
    "keypresses": KeyPresses,
    "tetris": Tetris,
}
