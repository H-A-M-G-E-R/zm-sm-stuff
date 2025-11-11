# Uses code from PJBoy's scripts for Super Metroid, modified for GBATroid: https://patrickjohnston.org/ASM/ROM%20data/Super%20Metroid/
# Also uses modified code from SpriteSomething: https://github.com/Artheau/SpriteSomething
# Also modified from H A M's Super Metroid OAM extractor: https://github.com/H-A-M-G-E-R/nspc-track-disassembler/blob/main/enemy%20spritemap%20extractor.py

from PIL import Image
import numpy as np

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
def image_from_raw_data(raw, width=0x20):
    raveled = np.concatenate([np.concatenate([convert_4bpp_tile_gba(raw[(i+j)*0x20:(i+j+1)*0x20], 0) for i in range(width)], 1) for j in range(0, len(raw)//0x20, width)], 0)
    return Image.fromarray(raveled, 'P')

def convert_4bpp_tile_gba(raw_tile, palette):
    tile = np.zeros(64, dtype=np.uint8)

    for i in range(32):
        tile[i*2] = raw_tile[i] & 0xF | palette
        tile[i*2+1] = raw_tile[i] >> 4 | palette

    return tile.reshape(8, 8)

def extract_tiles(tilesAddr, paletteAddr, size, name, width=32):
    romSeek(paletteAddr)
    palette555 = [romRead(2) for i in range(16)]

    paletteRgb = [0]*(3*16)
    for i in range(16):
        paletteRgb[i*3] = (palette555[i] & 0x1F) << 3
        paletteRgb[i*3+1] = (palette555[i] >> 5 & 0x1F) << 3
        paletteRgb[i*3+2] = (palette555[i] >> 10 & 0x1F) << 3

    romSeek(tilesAddr)
    tiles = [romRead() for j in range(0x20*size)]

    image = image_from_raw_data(tiles, width)
    image.putpalette(paletteRgb, 'RGB')
    image.save(name)

rom = open("mzm.gba", 'rb')

#extract_tiles(0x832BAC8, 0x832BA08, 0x20*0xE, 'common_tiles_2.png')
'''
extract_tiles(0x832BAC8, 0x832BA08+0x20, 0x20*0xE, 'common_tiles_3.png')
extract_tiles(0x832BAC8, 0x832BA08+0x40, 0x20*0xE, 'common_tiles_4.png')
extract_tiles(0x832BAC8, 0x832BA08+0xA0, 0x20*0xE, 'common_tiles_7.png')
'''
'''
extract_tiles(0x83271A8, 0x83270E8, 0x40, 'normal_beam.png', 16)
extract_tiles(0x8327B90, 0x83270E8+0x20, 0x40, 'long_beam.png', 16)
extract_tiles(0x8328500, 0x83270E8+0x40, 0x40, 'ice_beam.png', 16)
extract_tiles(0x8328F34, 0x83270E8+0x60, 0x40, 'wave_beam.png', 16)
extract_tiles(0x8329ED4, 0x83270E8+0x80, 0x40, 'plasma_beam.png', 16)
'''
#extract_tiles(0x832B078, 0x83270E8+0xA0, 0x40, 'pistol.png', 16)
#extract_tiles(0x83362A8, 0x832BA08+0x40, 0x1C0, 'pistol_charge_gauge.png', 8)
'''
extract_tiles(0x8322468, 0x083239a8+5*0x20, 0x80, 'mecha_ridley_missile.png')
extract_tiles(0x8322468, 0x083239a8+1*0x20, 0x80, 'mecha_ridley_fireball.png')
'''
extract_tiles(0x8323468, 0x083239a8, 6*7, 'mecha_ridley_destroyed.png', 6)
