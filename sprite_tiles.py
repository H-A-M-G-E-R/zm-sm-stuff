# Uses code from PJBoy's scripts for Super Metroid, modified for GBATroid: https://patrickjohnston.org/ASM/ROM%20data/Super%20Metroid/
# Also uses modified code from SpriteSomething: https://github.com/Artheau/SpriteSomething
# Also modified from H A M's Super Metroid OAM extractor: https://github.com/H-A-M-G-E-R/nspc-track-disassembler/blob/main/enemy%20spritemap%20extractor.py

from PIL import Image
import numpy as np
from decompressor import decomp_lz77

gba2hex = lambda address: address & 0x1FFFFFF
hex2gba = lambda address: address & 0x1FFFFFF | 0x8000000

def romRead(n = 1, address = None):
    if address is not None:
        prevAddress = rom.tell()
        rom.seek(gba2hex(address))

    ret = int.from_bytes(rom.read(n), 'little')
    if address is not None:
        rom.seek(prevAddress)
        
    return ret

def romSeek(address):
    return rom.seek(gba2hex(address))

def romTell():
    return hex2gba(rom.tell())

tile_dimensions = [[(8,8),(16,16),(32,32),(64,64)],[(16,8),(32,8),(32,16),(64,32)],[(8,16),(8,32),(16,32),(32,64)]]

''' Modified From SpriteSomething (https://github.com/Artheau/SpriteSomething) '''
def image_from_raw_data(DMA_writes):
    tiles = [convert_4bpp_tile_gba(tile, 0) for tile in DMA_writes]

    rows = []
    for i in range(0, len(tiles), 0x20):
        rows.append(np.concatenate(tiles[i:i+0x20], 1))

    return Image.fromarray(np.concatenate(rows, 0), 'P')


def convert_4bpp_tile_gba(raw_tile, palette):
    tile = np.zeros(64, dtype=np.uint8)

    for i in range(32):
        tile[i*2] = raw_tile[i] & 0xF | palette
        tile[i*2+1] = raw_tile[i] >> 4 | palette

    return tile.reshape(8, 8)

rom = open("mzm.gba", 'rb')

for spriteIndex in range(0x12, 0xC6):
    tilesAddr = romRead(4, 0x875EBF8+(spriteIndex-0x10)*4)
    paletteAddr = romRead(4, 0x875EEF0+(spriteIndex-0x10)*4)

    decompressed = decomp_lz77(rom, tilesAddr & 0x1FFFFFF)[0]
    rows = len(decompressed)//0x800

    romSeek(paletteAddr)
    palette555 = [romRead(2) for i in range(rows*16)]

    paletteRgb = [0]*(3*16*rows)
    for i in range(rows*16):
        paletteRgb[i*3] = (palette555[i] & 0x1F) << 3
        paletteRgb[i*3+1] = (palette555[i] >> 5 & 0x1F) << 3
        paletteRgb[i*3+2] = (palette555[i] >> 10 & 0x1F) << 3

    tiles = []
    for i in range(0, len(decompressed), 0x20):
        tiles.append(decompressed[i:i+0x20])

    image = image_from_raw_data(tiles)
    image.putpalette(paletteRgb, 'RGB')
    image.save(f'sprite_tiles_original/0x{spriteIndex:x}.png')
