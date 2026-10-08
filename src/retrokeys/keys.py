"""Key names for the 8BitDo Retro Keyboard.

Two number spaces show up everywhere:

- A *source* is the key you are programming (a position on this keyboard).
- A *usage* is the HID keyboard code the keyboard will emit.

Most letter positions use the same number in both spaces. The modifier keys
and the Super Buttons do not.
"""

from __future__ import annotations

# External Dual Super Buttons, one A/B pair per 3.5 mm jack.
# A pad works in any of A, B, X, and Y. The bool is unused by the window.
JACKS: tuple[tuple[str, int, int, bool], ...] = (
    ("A", 0x74, 0x75, False),
    ("B", 0x72, 0x73, False),
    ("X", 0x70, 0x71, True),
    ("Y", 0x6E, 0x6F, False),
)

ONBOARD: tuple[tuple[str, int], ...] = (
    ("Super A", 0x6D),
    ("Super B", 0x6C),
)

FEATURED: frozenset[int] = frozenset(
    code
    for _name, a, b, _primary in JACKS
    for code in (a, b)
) | frozenset(code for _name, code in ONBOARD)


def _titles() -> dict[int, str]:
    titles: dict[int, str] = {}
    for jack, a, b, _primary in JACKS:
        titles[a] = f"Jack {jack} · A"
        titles[b] = f"Jack {jack} · B"
    for name, code in ONBOARD:
        titles[code] = name
    return titles


SOURCE_TITLES: dict[int, str] = _titles()

# Keyboard positions other than the Super Buttons, in physical order.
# Numbers are the keyboard's own source codes.
KEYBOARD_SOURCES: tuple[tuple[int, str], ...] = (
    (0x29, "Escape"),
    (0x3A, "F1"),
    (0x3B, "F2"),
    (0x3C, "F3"),
    (0x3D, "F4"),
    (0x3E, "F5"),
    (0x3F, "F6"),
    (0x40, "F7"),
    (0x41, "F8"),
    (0x42, "F9"),
    (0x43, "F10"),
    (0x44, "F11"),
    (0x45, "F12"),
    (0x46, "Print Screen"),
    (0x47, "Scroll Lock"),
    (0x48, "Pause"),
    (0x35, "Grave"),
    (0x1E, "1"),
    (0x1F, "2"),
    (0x20, "3"),
    (0x21, "4"),
    (0x22, "5"),
    (0x23, "6"),
    (0x24, "7"),
    (0x25, "8"),
    (0x26, "9"),
    (0x27, "0"),
    (0x2D, "Minus"),
    (0x2E, "Equal"),
    (0x2A, "Backspace"),
    (0x49, "Insert"),
    (0x4A, "Home"),
    (0x4B, "Page Up"),
    (0x2B, "Tab"),
    (0x14, "Q"),
    (0x1A, "W"),
    (0x08, "E"),
    (0x15, "R"),
    (0x17, "T"),
    (0x1C, "Y"),
    (0x18, "U"),
    (0x0C, "I"),
    (0x12, "O"),
    (0x13, "P"),
    (0x2F, "Left Bracket"),
    (0x30, "Right Bracket"),
    (0x31, "Backslash"),
    (0x4C, "Delete"),
    (0x4D, "End"),
    (0x4E, "Page Down"),
    (0x39, "Caps Lock"),
    (0x04, "A"),
    (0x16, "S"),
    (0x07, "D"),
    (0x09, "F"),
    (0x0A, "G"),
    (0x0B, "H"),
    (0x0D, "J"),
    (0x0E, "K"),
    (0x0F, "L"),
    (0x33, "Semicolon"),
    (0x34, "Apostrophe"),
    (0x28, "Enter"),
    (0x65, "Left Shift"),
    (0x1D, "Z"),
    (0x1B, "X"),
    (0x06, "C"),
    (0x19, "V"),
    (0x05, "B"),
    (0x11, "N"),
    (0x10, "M"),
    (0x36, "Comma"),
    (0x37, "Dot"),
    (0x38, "Slash"),
    (0x69, "Right Shift"),
    (0x52, "Up"),
    (0x64, "Left Ctrl"),
    (0x67, "Left Super"),
    (0x66, "Left Alt"),
    (0x2C, "Space"),
    (0x6A, "Right Alt"),
    (0x68, "Right Ctrl"),
    (0x50, "Left"),
    (0x51, "Down"),
    (0x4F, "Right"),
)

for _code, _name in KEYBOARD_SOURCES:
    SOURCE_TITLES.setdefault(_code, _name)


def source_title(code: int) -> str:
    return SOURCE_TITLES.get(code, f"Key {code:#04x}")


# HID keyboard usages the firmware can emit. Modifiers live in the separate
# modifier byte; a modifier alone is stored with usage 0.
MODIFIERS: tuple[tuple[int, str, str], ...] = (
    (0xE0, "Left Ctrl", "Ctrl"),
    (0xE1, "Left Shift", "Shift"),
    (0xE2, "Left Alt", "Alt"),
    (0xE3, "Left Super", "Super"),
    (0xE4, "Right Ctrl", "RCtrl"),
    (0xE5, "Right Shift", "RShift"),
    (0xE6, "Right Alt", "RAlt"),
    (0xE7, "Right Super", "RSuper"),
)

_MOD_LONG = {code: long for code, long, _short in MODIFIERS}
_MOD_SHORT = {code: short for code, _long, short in MODIFIERS}

# (usage, long name, short name, picker group)
_KEYS: list[tuple[int, str, str, str]] = []


def _add(usage: int, long: str, short: str | None = None, group: str = "Keys") -> None:
    _KEYS.append((usage, long, short or long, group))


for _offset, _letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _add(0x04 + _offset, _letter.upper(), _letter.upper(), "Letters")

for _n in range(1, 10):
    _add(0x1E + _n - 1, str(_n), group="Digits")
_add(0x27, "0", group="Digits")

for _usage, _long, _short in (
    (0x28, "Enter", "Enter"),
    (0x29, "Escape", "Esc"),
    (0x2A, "Backspace", "Bksp"),
    (0x2B, "Tab", "Tab"),
    (0x2C, "Space", "Space"),
    (0x39, "Caps Lock", "Caps"),
):
    _add(_usage, _long, _short, "Typing")

for _usage, _long, _short in (
    (0x35, "Grave", "`"),
    (0x2D, "Minus", "-"),
    (0x2E, "Equal", "="),
    (0x2F, "Left Bracket", "["),
    (0x30, "Right Bracket", "]"),
    (0x31, "Backslash", "\\"),
    (0x33, "Semicolon", ";"),
    (0x34, "Apostrophe", "'"),
    (0x36, "Comma", ","),
    (0x37, "Dot", "."),
    (0x38, "Slash", "/"),
    (0x64, "Non-US \\", "\\"),
):
    _add(_usage, _long, _short, "Symbols")

for _usage, _long, _short in (
    (0x49, "Insert", "Ins"),
    (0x4A, "Home", "Home"),
    (0x4B, "Page Up", "PgUp"),
    (0x4C, "Delete", "Del"),
    (0x4D, "End", "End"),
    (0x4E, "Page Down", "PgDn"),
    (0x4F, "Right", "Right"),
    (0x50, "Left", "Left"),
    (0x51, "Down", "Down"),
    (0x52, "Up", "Up"),
    (0x46, "Print Screen", "PrtSc"),
    (0x47, "Scroll Lock", "ScrLk"),
    (0x48, "Pause", "Pause"),
):
    _add(_usage, _long, _short, "Navigation")

for _i in range(12):
    _add(0x3A + _i, f"F{_i + 1}", group="Function")
for _i in range(12):
    _add(0x68 + _i, f"F{_i + 13}", group="Function")

for _code, _long, _short in MODIFIERS:
    _add(_code, _long, _short, "Modifiers")

for _usage, _long, _short in (
    (0x53, "Num Lock", "Num"),
    (0x54, "Keypad /", "Kp/"),
    (0x55, "Keypad *", "Kp*"),
    (0x56, "Keypad -", "Kp-"),
    (0x57, "Keypad +", "Kp+"),
    (0x58, "Keypad Enter", "KpEnter"),
    (0x59, "Keypad 1", "Kp1"),
    (0x5A, "Keypad 2", "Kp2"),
    (0x5B, "Keypad 3", "Kp3"),
    (0x5C, "Keypad 4", "Kp4"),
    (0x5D, "Keypad 5", "Kp5"),
    (0x5E, "Keypad 6", "Kp6"),
    (0x5F, "Keypad 7", "Kp7"),
    (0x60, "Keypad 8", "Kp8"),
    (0x61, "Keypad 9", "Kp9"),
    (0x62, "Keypad 0", "Kp0"),
    (0x63, "Keypad .", "Kp."),
    (0x65, "Menu", "Menu"),
):
    _add(_usage, _long, _short, "Keypad")

USAGES: tuple[tuple[int, str, str, str], ...] = tuple(_KEYS)
USAGE_LONG = {usage: long for usage, long, _short, _group in USAGES}
USAGE_SHORT = {usage: short for usage, _long, short, _group in USAGES}
MODIFIER_CODES = frozenset(_MOD_LONG)


def usage_long(code: int) -> str:
    if code == 0:
        return ""
    return USAGE_LONG.get(code, f"{code:#04x}")


def usage_short(code: int) -> str:
    if code == 0:
        return ""
    return USAGE_SHORT.get(code, usage_long(code))


def is_modifier(code: int) -> bool:
    return code in MODIFIER_CODES


# Linux evdev code → HID usage. On Wayland, GTK reports these codes directly.
# On X11 the same hardware code is reported 8 higher. The caller passes x11=True.
_EVDEV_TO_HID: dict[int, int] = {
    30: 0x04,  # A
    48: 0x05,  # B
    46: 0x06,  # C
    32: 0x07,  # D
    18: 0x08,  # E
    33: 0x09,  # F
    34: 0x0A,  # G
    35: 0x0B,  # H
    23: 0x0C,  # I
    36: 0x0D,  # J
    37: 0x0E,  # K
    38: 0x0F,  # L
    50: 0x10,  # M
    49: 0x11,  # N
    24: 0x12,  # O
    25: 0x13,  # P
    16: 0x14,  # Q
    19: 0x15,  # R
    31: 0x16,  # S
    20: 0x17,  # T
    22: 0x18,  # U
    47: 0x19,  # V
    17: 0x1A,  # W
    45: 0x1B,  # X
    21: 0x1C,  # Y
    44: 0x1D,  # Z
    2: 0x1E,
    3: 0x1F,
    4: 0x20,
    5: 0x21,
    6: 0x22,
    7: 0x23,
    8: 0x24,
    9: 0x25,
    10: 0x26,
    11: 0x27,
    28: 0x28,  # Enter
    1: 0x29,  # Escape
    14: 0x2A,
    15: 0x2B,
    57: 0x2C,
    12: 0x2D,
    13: 0x2E,
    26: 0x2F,
    27: 0x30,
    43: 0x31,
    39: 0x33,
    40: 0x34,
    41: 0x35,
    51: 0x36,
    52: 0x37,
    53: 0x38,
    58: 0x39,
    99: 0x46,  # SysRq / Print Screen
    70: 0x47,
    119: 0x48,
    110: 0x49,
    102: 0x4A,
    104: 0x4B,
    111: 0x4C,
    107: 0x4D,
    109: 0x4E,
    106: 0x4F,
    105: 0x50,
    108: 0x51,
    103: 0x52,
    69: 0x53,
    98: 0x54,
    55: 0x55,
    74: 0x56,
    78: 0x57,
    96: 0x58,
    79: 0x59,
    80: 0x5A,
    81: 0x5B,
    75: 0x5C,
    76: 0x5D,
    77: 0x5E,
    71: 0x5F,
    72: 0x60,
    73: 0x61,
    82: 0x62,
    83: 0x63,
    86: 0x64,  # 102nd
    127: 0x65,  # Compose
    29: 0xE0,
    42: 0xE1,
    56: 0xE2,
    125: 0xE3,
    97: 0xE4,
    54: 0xE5,
    100: 0xE6,
    126: 0xE7,
}

for _i in range(10):
    _EVDEV_TO_HID[59 + _i] = 0x3A + _i  # F1–F10. F11 and F12 are not next in line.
_EVDEV_TO_HID[87] = 0x44  # F11
_EVDEV_TO_HID[88] = 0x45  # F12
for _i in range(12):
    _EVDEV_TO_HID[183 + _i] = 0x68 + _i  # F13–F24

EVDEV_TO_HID = _EVDEV_TO_HID


def hid_from_keycode(keycode: int, *, x11: bool = False) -> int | None:
    """Map a GTK hardware keycode to a HID usage.

    Wayland reports the evdev code. X11 reports that same code plus 8, and the
    two number spaces overlap, so the caller has to say which display it is.
    """
    evdev = keycode - 8 if x11 else keycode
    return EVDEV_TO_HID.get(evdev)
