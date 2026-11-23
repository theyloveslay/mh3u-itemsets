# Sharing Item Sets between Cemu and 3DS/Azahar

The 3DS storage implementation uses the **existing Cemu v2 file format**. It
does not introduce an incompatible little-endian format. No Cemu update or
conversion is needed for the matching character slot.

This has been checked by executing the compiled ARM codec and the existing
compiled Cemu PPC adapter against each other's output. This is a format test;
the 3DS mod is now an experimental patch, but is not live-game tested.

## Files to carry across

| Character slot | Recovery bank A | Recovery bank B |
|---|---|---|
| 1 | `mh3u_loadouts_user1_a.bin` | `mh3u_loadouts_user1_b.bin` |
| 2 | `mh3u_loadouts_user2_a.bin` | `mh3u_loadouts_user2_b.bin` |
| 3 | `mh3u_loadouts_user3_a.bin` | `mh3u_loadouts_user3_b.bin` |

Cemu keeps these alongside the game's save files. The implemented 3DS transport
uses these same basenames at the root of the SD card, or Azahar's emulated SD.
The destination path still needs a live access-permission test.

For testing the 3DS port, close the game, retain a backup of the destination
pair, and copy **both** files for the desired character slot. Both versions
validate their checksum and choose the newest valid bank. Merely renaming a
slot-1 bank to slot 2 does not remap it: the slot is also stored in its header.

The file contains 24 registrations, their pouch types, item IDs/quantities and
custom names. It does not supply item stock. Loading still uses the target
game's pouches and box, including its normal missing-item behavior. Reading
older Cemu v1 files upgrades the original 20 registrations to the 24-set format.
This is file transfer, not automatic synchronization between running emulators.

## Wire layout

All multibyte fields use **big endian**, including when running on ARM.

| Offset | Size | Contents |
|---|---|---|
| `0x0000` | 4 | Magic `M3LD` |
| `0x0004` | 4 | Version, currently 2 |
| `0x0008` | 4 | Character slot, zero based |
| `0x000C` | 4 | Wrapping generation number |
| `0x0010` | 4 | FNV-1a checksum of the entire bank; these four bytes count as zero |
| `0x0014` | 28 | Reserved, zero on write |
| `0x0030` | 3,168 | 24 records of 132 bytes |
| `0x0C90` | 480 | 24 names of 20 bytes each; last byte is NUL |
| `0x0E70` | 16 | Padding, zero on write |

Each record has `valid:u8`, `gunner:u8`, `reserved:u16`, then 32 pairs of
`item_id:u16, quantity:u16`. A full v2 bank is 3,712 bytes. A v1 bank is 2,688
bytes, ending after 20 records, with names generated during upgrade.

The checksum seed is 2,166,136,261 and the multiplier is 16,777,619; arithmetic
wraps at 32 bits. The generation comparison matches the Cemu adapter, including
rollover from `0xFFFFFFFF` to zero.
