"""Profile packets for the 8BitDo Retro Keyboard.

The config interface is HID output report 0x52 and input report 0x54, each
with a 32-byte body. This was checked against a Famicom-edition keyboard
(USB id 2dc8:5200, interface 2): names, key maps, and macros round-trip,
and a zero-length name erases the whole profile.

Sending 0x76 0xA5 turns on a raw-key stream and is not required to store a
map, so nothing here sends it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

REPORT_BODY = 32
NAME_BYTES = 28  # room left after the 4-byte macro-name header

DELAY = 0x0F
DOWN = 0x81
UP = 0x01
MOD_DOWN = 0x83
MOD_UP = 0x03

KEY_TYPE = 0x07
SET_KEY_PREFIX = bytes((0xFA, 0x03, 0x0C, 0x00, 0xAA, 0x09, 0x71))


class ProfileError(ValueError):
    """The profile cannot be encoded the way the keyboard expects."""


@dataclass(frozen=True)
class MacroEvent:
    action: int
    arg: int

    def label(self) -> str:
        from .keys import usage_short

        if self.action == DELAY:
            return f"Wait {self.arg} ms"
        verb = "Press" if self.action in (DOWN, MOD_DOWN) else "Release"
        return f"{verb} {usage_short(self.arg) or '?'}"


@dataclass(frozen=True)
class Binding:
    kind: str  # "key", "macro", or "opaque"
    mod: int = 0
    usage: int = 0
    macro_name: str = ""
    repeats: int = 1
    events: tuple[MacroEvent, ...] = ()
    type_code: int = KEY_TYPE

    def summary(self) -> str:
        from .keys import usage_short

        if self.kind == "opaque":
            return "Other mapping"
        if self.kind == "macro":
            name = self.macro_name or "Macro"
            if self.repeats > 1:
                return f"{name} ×{self.repeats}"
            return name
        mod = usage_short(self.mod)
        key = usage_short(self.usage)
        if mod and key:
            return f"{mod}+{key}"
        return mod or key or "—"


@dataclass
class Profile:
    name: str = ""
    bindings: dict[int, Binding] = field(default_factory=dict)

    def clone(self) -> Profile:
        return Profile(self.name, dict(self.bindings))


def encode_text(text: str) -> bytes:
    if "\x00" in text:
        raise ProfileError("The name cannot contain a null character.")
    raw = text.encode("utf-16-be")
    if len(raw) > NAME_BYTES:
        raise ProfileError("Use 14 characters or fewer.")
    return raw


def decode_text(raw: bytes) -> str:
    if len(raw) % 2:
        raw = raw[: len(raw) - 1]
    return raw.decode("utf-16-be", errors="replace").rstrip("\x00")


def name_packet(name: str) -> bytes:
    raw = encode_text(name)
    if not raw:
        raise ProfileError("An empty name erases the whole profile.")
    return bytes((0x70,)) + struct.pack("<H", len(raw)) + raw


def erase_packet() -> bytes:
    return bytes((0x70, 0x00, 0x00))


def parse_name(report: bytes) -> str:
    if len(report) < 4 or report[1] != 0x80:
        raise ProfileError("The keyboard did not return a profile name.")
    length = struct.unpack_from("<H", report, 2)[0]
    return decode_text(report[4 : 4 + length])


def key_packet(source: int, mod: int, usage: int) -> bytes:
    return SET_KEY_PREFIX + bytes((source & 0xFF, KEY_TYPE, mod & 0xFF, usage & 0xFF))


def parse_key_list(report: bytes) -> list[int]:
    """Return source codes from one 0x81 report, ignoring the trailing marker."""
    if len(report) < 3 or report[1] != 0x81:
        raise ProfileError("The keyboard did not return a key list.")
    body = report[2:-1]
    found: list[int] = []
    for index in range(0, len(body) - 1, 2):
        source = body[index]
        if source == 0:
            break
        found.append(source)
    return found


def more_follows(report: bytes) -> bool:
    return len(report) >= 33 and report[-1] == 0x01


def parse_key(report: bytes) -> tuple[int, int, int, int]:
    """Return source, type, modifier, usage from an 0x83 report."""
    if len(report) < 6 or report[1] != 0x83:
        raise ProfileError("The keyboard did not return a key mapping.")
    source, type_code, mod, usage = report[2], report[3], report[4], report[5]
    return source, type_code, mod, usage


def parse_macro_sources(report: bytes) -> list[int]:
    if len(report) < 2 or report[1] != 0x82:
        raise ProfileError("The keyboard did not return a macro list.")
    body = report[2:-1]
    found: list[int] = []
    for index in range(0, len(body), 4):
        source = body[index]
        if source == 0:
            break
        found.append(source)
    return found


def parse_macro_name(report: bytes) -> tuple[int, str]:
    if len(report) < 5 or report[1] != 0x84:
        raise ProfileError("The keyboard did not return a macro name.")
    source = report[2]
    length = struct.unpack_from("<H", report, 3)[0]
    return source, decode_text(report[5 : 5 + length])


def macro_body(repeats: int, events: tuple[MacroEvent, ...] | list[MacroEvent]) -> bytes:
    if not 1 <= repeats <= 0xFFFF:
        raise ProfileError("Repeat count must be from 1 to 65535.")
    if not events:
        raise ProfileError("A macro needs at least one step.")
    if len(events) > 0xFF:
        raise ProfileError("A macro can have at most 255 steps.")
    buf = struct.pack("<BHB", 0x01, repeats, len(events))
    for event in events:
        if event.action not in (DELAY, DOWN, UP, MOD_DOWN, MOD_UP):
            raise ProfileError(f"Unknown macro step {event.action:#04x}.")
        if not 0 <= event.arg <= 0xFFFF:
            raise ProfileError("A macro step is out of range.")
        buf += struct.pack("<BH", event.action, event.arg)
    return buf


def parse_macro_body(blob: bytes) -> tuple[int, tuple[MacroEvent, ...]]:
    if len(blob) < 4:
        raise ProfileError("The macro came back empty.")
    _const, repeats, count = struct.unpack_from("<BHB", blob, 0)
    events: list[MacroEvent] = []
    pos = 4
    for _ in range(count):
        if pos + 3 > len(blob):
            raise ProfileError("The macro came back truncated.")
        action, arg = struct.unpack_from("<BH", blob, pos)
        events.append(MacroEvent(action, arg))
        pos += 3
    return repeats, tuple(events)


def macro_name_packet(source: int, name: str) -> bytes:
    raw = encode_text(name) if name else b""
    return bytes((0x74, source & 0xFF)) + struct.pack("<H", len(raw)) + raw


def macro_body_packets(source: int, body: bytes) -> list[tuple[bytes, bool]]:
    """Split a macro body. Only the last piece is acknowledged by the keyboard."""
    room = REPORT_BODY - 6
    packets: list[tuple[bytes, bool]] = []
    pos = 0
    while pos < len(body):
        chunk = body[pos : pos + room]
        more = 0 if pos + len(chunk) >= len(body) else 1
        header = struct.pack("<BBBHB", 0x76, source & 0xFF, more, pos, len(chunk))
        packets.append((header + chunk, more == 0))
        pos += len(chunk)
    return packets


def take_macro_piece(report: bytes) -> tuple[int, int, int, bytes]:
    """Return source, offset, more, data from one 0x86 report."""
    if len(report) < 7 or report[1] != 0x86:
        raise ProfileError("The keyboard did not return a macro.")
    source = report[2]
    more = report[3]
    offset = struct.unpack_from("<H", report, 4)[0]
    length = report[6]
    return source, offset, more, report[7 : 7 + length]


def assemble_macro(pieces: list[bytes]) -> bytes:
    parts: dict[int, bytes] = {}
    for piece in pieces:
        _source, offset, _more, data = take_macro_piece(piece)
        parts[offset] = data
    blob = bytearray()
    for offset in sorted(parts):
        if offset != len(blob):
            raise ProfileError("The macro pieces arrived out of order.")
        blob += parts[offset]
    return bytes(blob)


def delete_macro_packet(source: int) -> bytes:
    return bytes((0x77, source & 0xFF, 0x8C))


def quiet_packet() -> bytes:
    return bytes((0x76, 0xFF))


def plan_writes(old: Profile, new: Profile) -> list[tuple[bytes, bool]]:
    """Packets to turn ``old`` into ``new``.

    Each item is ``(payload, wait_for_ack)``. An empty new name is refused:
    on this keyboard that packet erases every mapping, and erase is a
    separate command.
    """
    if new.name == "":
        if old.name or old.bindings or new.bindings:
            raise ProfileError(
                "An empty profile name erases everything on the keyboard. "
                "Type a name, or use Erase profile."
            )
        return []

    ops: list[tuple[bytes, bool]] = []
    if new.name != old.name:
        ops.append((name_packet(new.name), True))

    sources = sorted(set(old.bindings) | set(new.bindings))
    for source in sources:
        before = old.bindings.get(source)
        after = new.bindings.get(source)
        if before == after:
            continue
        if before is not None and before.kind == "macro" and (
            after is None or after.kind != "macro"
        ):
            ops.append((delete_macro_packet(source), True))
        if after is None:
            # A macro was already deleted above. Any other mapping is cleared
            # by writing an empty key, which drops it from the key list.
            if before is not None and before.kind != "macro":
                ops.append((key_packet(source, 0, 0), True))
            continue
        if after.kind == "opaque":
            raise ProfileError("This mapping cannot be rewritten.")
        if after.kind == "key":
            ops.append((key_packet(source, after.mod, after.usage), True))
            continue
        if after.kind != "macro":
            raise ProfileError(f"Unknown binding {after.kind}.")
        body = macro_body(after.repeats, after.events)
        ops.append((macro_name_packet(source, after.macro_name), True))
        ops.extend(macro_body_packets(source, body))
        if before is None or before.kind != "macro":
            # A macro and a key map on the same button both fire.
            ops.append((key_packet(source, 0, 0), True))
    return ops
