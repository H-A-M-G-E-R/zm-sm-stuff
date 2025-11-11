# Requires a ZM rom (mzm.gba) and symbols (mzm_us.map) from the decomp (https://github.com/metroidret/mzm).

import base64, copy, json, sys
from labels import extract_labels
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

def remap_gba_2_snes_tile(tile, gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset, big=False):
    try:
        if big:
            for idx in range(len(snes_gfx) - 0x11):
                if idx & 0xF != 0xF:
                    if gba_gfx[tile - gba_gfx_offset] == snes_gfx[idx]:
                        if gba_gfx[tile + 1 - gba_gfx_offset] == snes_gfx[idx + 1]:
                            if gba_gfx[tile + 0x20 - gba_gfx_offset] == snes_gfx[idx + 0x10]:
                                if gba_gfx[tile + 0x21 - gba_gfx_offset] == snes_gfx[idx + 0x11]:
                                    return idx + snes_gfx_offset
            # failed to match 16x16 region, split into four 8x8 tiles
            return -1
        else:
            if gba_gfx[tile - gba_gfx_offset] == [0]*64:
                # blank tile
                return -2
            if gba_gfx[tile - gba_gfx_offset] in snes_gfx:
                return snes_gfx.index(gba_gfx[tile - gba_gfx_offset]) + snes_gfx_offset
    except:
        pass
    return snes_gfx_offset

def build_gfx(fp):
    image = Image.open(fp)
    out = []
    for y in range(0, image.height, 8):
        for x in range(0, image.width, 8):
            out.append(list(image.crop((x, y, x + 8, y + 8)).getdata()))
    return out

# Documented at https://www.coranac.com/tonc/text/regobj.htm
def decode_spritemap_entry(entry):
    return {
        'x': (entry[1] & 0x1FF) - (0x200 if (entry[1] & 0x1FF) >= 0x100 else 0),
        'y': (entry[0] & 0xFF) - (0x100 if (entry[0] & 0xFF) >= 0x80 else 0),
        'shape': entry[0] >> 0xE,
        'size': entry[1] >> 0xE,
        'tile': entry[2] & 0x3FF,
        'palette': (entry[2] >> 0xC & 0xF) - 8,
        'bg_priority': entry[2] >> 0xA & 0x3,
        'h_flip': entry[1] & 0x1000 == 0x1000,
        'v_flip': entry[1] & 0x2000 == 0x2000
    }

def split_spritemap_entry(entry: dict):
    split_entries = []
    (width, height) = tile_dimensions[entry['shape']][entry['size']]
    split_tile_size = 16 if width % 16 == 0 and height % 16 == 0 else 8

    for x in range(width//split_tile_size):
        for y in range(height//split_tile_size):
            split_entry = copy.copy(entry)
            split_entry['x'] += abs(x*split_tile_size-(width-split_tile_size if split_entry['h_flip'] else 0))
            split_entry['y'] += abs(y*split_tile_size-(height-split_tile_size if split_entry['v_flip'] else 0))
            split_entry['tile'] += x*(split_tile_size//8) + y*(split_tile_size*4)
            split_entry['big'] = split_tile_size == 16
            split_entry.pop('shape')
            split_entry.pop('size')
            split_entries.append(split_entry)

    return split_entries

def extract_generic(rom, pal_ptr, pal_count, spritemap_start, name, gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset):
    romSeek(pal_ptr)
    palette555 = [romRead(2) for i in range(16*pal_count)]
    palette888 = [int.from_bytes([
        255,                         # A
        (color555 & 0x1F) << 3,      # R
        (color555 >> 5 & 0x1F) << 3, # G
        (color555 >> 10 & 0x1F) << 3 # B
    ], 'big') for color555 in palette555]

    romSeek(spritemap_start)
    spritemaps = extract_spritemaps(gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset)

    return {
        'game': 'sm',
        'name': name,
        'gfx': "",
        'palette': palette888,
        'gfx_offset': snes_gfx_offset,
        'palette_offset': 0,
        'spritemaps': spritemaps,
        'ext_hitboxes': [],
        'ext_spritemaps': []
    }

def ParseOam(gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset):
    count = romRead(2)
    spritemap = []
    if count != 0:
        for i in range(count):
            spritemap.extend(split_spritemap_entry(decode_spritemap_entry([romRead(2) for j in range(3)])))

    spritemap2 = []
    for entry in spritemap:
        remapped_tile_idx = remap_gba_2_snes_tile(entry['tile'], gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset, entry['big'])
        if remapped_tile_idx >= 0:
            entry['tile'] = remapped_tile_idx
            spritemap2.append(entry)
        elif remapped_tile_idx == -1:
            # Split into four 8x8 tiles
            tile0 = copy.copy(entry)
            tile0['big'] = False
            if entry['h_flip']:
                tile0['x'] += 8
            if entry['v_flip']:
                tile0['y'] += 8
            tile0['tile'] = remap_gba_2_snes_tile(tile0['tile'], gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset, False)

            tile1 = copy.copy(entry)
            tile1['big'] = False
            tile1['tile'] += 1
            if not entry['h_flip']:
                tile1['x'] += 8
            if entry['v_flip']:
                tile1['y'] += 8
            tile1['tile'] = remap_gba_2_snes_tile(tile1['tile'], gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset, False)

            tile2 = copy.copy(entry)
            tile2['big'] = False
            tile2['tile'] += 0x20
            if entry['h_flip']:
                tile2['x'] += 8
            if not entry['v_flip']:
                tile2['y'] += 8
            tile2['tile'] = remap_gba_2_snes_tile(tile2['tile'], gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset, False)

            tile3 = copy.copy(entry)
            tile3['big'] = False
            tile3['tile'] += 0x21
            if not entry['h_flip']:
                tile3['x'] += 8
            if not entry['v_flip']:
                tile3['y'] += 8
            tile3['tile'] = remap_gba_2_snes_tile(tile3['tile'], gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset, False)

            # Delete blank tiles
            if tile0['tile'] != -2:
                spritemap2.append(tile0)
            if tile1['tile'] != -2:
                spritemap2.append(tile1)
            if tile2['tile'] != -2:
                spritemap2.append(tile2)
            if tile3['tile'] != -2:
                spritemap2.append(tile3)

    return spritemap2

def ParseFrameData():
    frameData = []
    while True:
        pFrame = romRead(4)
        timer = romRead(4)
        if pFrame == 0:
            break
        frameData.append((pFrame, timer))

    return frameData

def extract_spritemaps(gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset):
    frames = []
    spritemaps_dict = {}
    namedFrames = {}

    anim_asm = ""

    while True:
        currentAddr = romTell()
        if currentAddr % 4 != 0:
            rom.read(4 - (currentAddr % 4)) # align
        pointer = romRead(4)
        if pointer in spritemaps_dict:
            romSeek(romTell()-4)
            break
        romSeek(currentAddr)
        frames.append(currentAddr)
        spritemaps_dict[currentAddr] = ParseOam(gba_gfx, snes_gfx, gba_gfx_offset, snes_gfx_offset)

    while True:
        anim_addr = romTell()
        pointer = romRead(4)
        romSeek(anim_addr)
        if pointer not in spritemaps_dict:
            break

        anim = ParseFrameData()
        for i in range(len(anim)):
            if anim[i][0] not in namedFrames:
                namedFrames[anim[i][0]] = f"{all_labels[anim_addr]}_Frame{i}"

        anim_asm += f"{all_labels[anim_addr]}:\n"
        for (p_oam, timer) in anim:
            anim_asm += f"  dw {timer},{namedFrames[p_oam]}\n"
        anim_asm += f"  dw $80ED,{all_labels[anim_addr]}\n\n"

    output = []
    for addr in frames:
        output.append({
            "name": namedFrames[addr] if addr in namedFrames else f'sOam_{addr:x}',
            "spritemap": spritemaps_dict[addr]
        })

    print(anim_asm)

    return output

def extract_enemy(rom, sprite_id, name, gba_gfx, snes_gfx, spritemap_start=None):
    pal_ptr = romRead(4, 0x875EEF0+(sprite_id-0x10)*4)
    gfx_ptr = romRead(4, 0x875EBF8+(sprite_id-0x10)*4)

    # get row count based on decompressed gfx height
    row_count = len(decomp_lz77(rom, gfx_ptr & 0x1FFFFFF)[0]) // 0x800

    if spritemap_start == None:
        spritemap_start = pal_ptr+0x20*row_count # doesn't work for a few enemies

    return extract_generic(rom, pal_ptr, row_count, spritemap_start, name, gba_gfx, snes_gfx, 0x200, 0x100)

def convert_to_4bpp(image: Image):
    '''Converts an image to SNES 4bpp tiles as bytearray'''
    if image.mode not in ('P', 'PA'):
        raise AssertionError('Mode must be "P"')

    output = bytearray()

    for y in range(0, image.height, 8):
        for x in range(0, image.width, 8):
            tile = image.crop([x, y, x+8, y+8])
            output.extend(convert_indexed_tile_to_bitplanes(tile.getdata()))

    return output

def convert_indexed_tile_to_bitplanes(indexed_tile):
    # this should literally just be the inverse of
    #  convert_tile_from_bitplanes(), and so it was written in this way
    fixed_bits = np.array(indexed_tile, dtype=np.uint8).reshape(8, 8, 1)
    tile_bits = np.unpackbits(fixed_bits, axis=2, bitorder='little')
    tile = np.packbits(tile_bits, axis=1, bitorder='big')

    low_bitplanes = np.ravel(tile[:, 0, 0:2])
    high_bitplanes = np.ravel(tile[:, 0, 2:4])
    return np.append(low_bitplanes, high_bitplanes)

def export_sprite_oam(sprite_id, name, spritemap_start=None):
    gba_gfx = build_gfx(f'sprite_tiles_original/0x{sprite_id:02x}.png')
    snes_gfx = build_gfx(f'sprites/{name}/0x{sprite_id:02x}_sm.png')

    data = extract_enemy(rom, sprite_id, f'{name}', gba_gfx, snes_gfx, spritemap_start)
    image = Image.open(f'sprites/{name}/0x{sprite_id:02x}_sm.png')
    data['gfx'] =  str(base64.b64encode(convert_to_4bpp(image)), 'utf8')

    json.dump(data, open(f'sprites/{name}/{name}.json', 'w'), indent=1)

if __name__ == "__main__":
    rom = open('mzm.gba', 'rb')
    all_labels = extract_labels()

    #export_sprite_oam(0x12, 'zoomer')
    #export_sprite_oam(0x14, 'zeela') done
    #export_sprite_oam(0x16, 'ripper', 0x82CC014) done
    #export_sprite_oam(0x18, 'zeb', 0x82CCA00) done
    #export_sprite_oam(0x1f, 'skree', 0x82CD30C) done
    #export_sprite_oam(0x21, 'morph_ball') done
    #export_sprite_oam(0x32, 'sova')
    #export_sprite_oam(0x34, 'multiviola') done
    #export_sprite_oam(0x37, 'geruta') done
    #export_sprite_oam(0x38, 'squeept') done
    #export_sprite_oam(0x3b, 'dragon') done
    #export_sprite_oam(0x3f, 'reo', 0x82CE010) done
    #export_sprite_oam(0x45, 'skultera') done
    #export_sprite_oam(0x46, 'dessgeega') done
    #export_sprite_oam(0x48, 'waver') done
    #export_sprite_oam(0x50, 'elevator') done
    #export_sprite_oam(0x51, 'space_pirate')
    #export_sprite_oam(0x57, 'gamet') done
    #export_sprite_oam(0x5b, 'zebbo', 0x82E7068) done
    #export_sprite_oam(0x60, 'piston') done
    #export_sprite_oam(0x66, 'rinka', 0x82EE508) done
    #export_sprite_oam(0x67, 'polyp') done
    #export_sprite_oam(0x68, 'viola', 0x82EF758) done
    #export_sprite_oam(0x6b, 'holtz') done
    #export_sprite_oam(0x72, 'mella') done
    #export_sprite_oam(0x77, 'acid_worm')
    #export_sprite_oam(0x79, 'sidehopper') done
    #export_sprite_oam(0x7a, 'geega', 0x82FDA20) done
    #export_sprite_oam(0x86, 'imago')
    #export_sprite_oam(0x93, 'baristute') done
    #export_sprite_oam(0x98, 'security_laser')
