"""Reproduce static inspection without changing the executable or save.

Usage: python inspect_rpx.py executable.rpx updated-save output-directory
Requires capstone for disassembly; section extraction uses only the stdlib.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
import zlib

def sections(path):
    blob = Path(path).read_bytes()
    assert blob[:6] == b'\x7fELF\x01\x02', 'Expected big-endian ELF32'
    offset = struct.unpack_from('>I', blob, 32)[0]
    stride, count, names = struct.unpack_from('>HHH', blob, 46)
    result = []
    for index in range(count):
        name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from('>10I', blob, offset + index * stride)
        data = blob[off:off+size] if typ != 8 else b''
        if flags & 0x08000000:
            expected = struct.unpack_from('>I', data)[0]
            data = zlib.decompress(data[4:])
            assert len(data) == expected
        result.append(dict(nameoff=name, type=typ, addr=addr, data=data, info=info))
    for entry in result:
        entry['name'] = result[names]['data'][entry['nameoff']:].split(b'\0')[0].decode()
    symbols = next(s['data'] for s in result if s['name'] == '.symtab')
    for entry in result:
        if entry['type'] != 4:
            continue
        target = result[entry['info']]
        data = bytearray(target['data'])
        for off in range(0, len(entry['data']), 12):
            place, info, addend = struct.unpack_from('>III', entry['data'], off)
            symbol, typ = info >> 8, info & 255
            value = (struct.unpack_from('>I', symbols, symbol * 16 + 4)[0] + addend) & 0xffffffff
            loc = place - target['addr']
            if typ == 1:
                struct.pack_into('>I', data, loc, value)
            elif typ in (4, 5, 6):
                value = value if typ == 4 else value >> 16 if typ == 5 else (value + 0x8000) >> 16
                struct.pack_into('>H', data, loc, value & 65535)
            elif typ == 10:
                word = struct.unpack_from('>I', data, loc)[0]
                struct.pack_into('>I', data, loc, (word & ~0x03fffffc) | ((value-place) & 0x03fffffc))
            else:
                raise ValueError(f'Unsupported relocation {typ}')
        target['data'] = bytes(data)
    return result

def main():
    executable, save, output = map(Path, sys.argv[1:])
    output.mkdir(parents=True, exist_ok=True)
    mapped = sections(executable)
    manifest = {'inputs': {str(p): {'size': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (executable, save)}, 'sections': []}
    for entry in mapped:
        if entry['addr'] and entry['data']:
            (output / (entry['name'].lstrip('.') + '.bin')).write_bytes(entry['data'])
        manifest['sections'].append({'name': entry['name'], 'address': hex(entry['addr']), 'size': len(entry['data'])})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    try:
        from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    except ImportError:
        print('Sections extracted; install capstone for disassembly.')
        return
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    text = next(s for s in mapped if s['name'] == '.text')
    listing = []
    for address, size in [(0x02700580, 0x80), (0x027001b0, 0x34), (0x026fd53c, 0x200), (0x020742f8, 0xb0), (0x02199dd4, 0x74)]:
        listing.append(f'\nBLOCK {address:08x}')
        off = address - text['addr']
        listing.extend(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(text['data'][off:off+size], address))
    (output / 'disassembly.txt').write_text('\n'.join(listing))
    print(json.dumps(manifest['inputs'], indent=2))

if __name__ == '__main__':
    main()
