"""Physical key positions for the Retro Keyboard.

Every current colourway (Fami, N, M, C64) is this same 87-key tenkeyless
layout. Super B and Super A sit between Right Alt and Right Ctrl. The
external jack pads are not keys on this drawing.

A different body, such as the 108-key Retro or the 68-key N40, needs its
own row list. Colour stays in theme.py. Spans are quarter key-units.
One row is 18.5 key-units, which is 74 quarters.
"""

from __future__ import annotations

from dataclasses import dataclass

from .keys import JACKS, KEYBOARD_SOURCES, ONBOARD, source_title

WIDTH_QU = 74


@dataclass(frozen=True)
class KeyCell:
    kind: str
    span: int
    code: int = 0
    label: str = ""
    role: str = ""
    aliases: tuple[str, ...] = ()
    # HID usage this cap stands for when it is the target of a mapping.
    # Zero means the cap is only a source (the Super Buttons). Modifier
    # positions do not use the same numbers as the usages they send.
    usage: int = 0


def key(
    code: int,
    label: str,
    role: str,
    span: int,
    *aliases: str,
    usage: int | None = None,
) -> KeyCell:
    return KeyCell(
        "key",
        span,
        code,
        label,
        role,
        aliases,
        code if usage is None else usage,
    )


def gap(span: int) -> KeyCell:
    return KeyCell("gap", span)


# Roles are colour slots. theme.py decides what each role looks like.
ROWS: tuple[tuple[KeyCell, ...], ...] = (
    (
        key(0x29, "Esc", "escape", 4, "esc"),
        gap(4),
        key(0x3A, "F1", "function", 4),
        key(0x3B, "F2", "function", 4),
        key(0x3C, "F3", "function", 4),
        key(0x3D, "F4", "function", 4),
        gap(2),
        key(0x3E, "F5", "function", 4),
        key(0x3F, "F6", "function", 4),
        key(0x40, "F7", "function", 4),
        key(0x41, "F8", "function", 4),
        gap(2),
        key(0x42, "F9", "function", 4),
        key(0x43, "F10", "function", 4),
        key(0x44, "F11", "function", 4),
        key(0x45, "F12", "function", 4),
        gap(2),
        key(0x46, "PS", "nav", 4, "prtsc", "print"),
        key(0x47, "SL", "nav", 4, "scroll"),
        key(0x48, "Pa", "nav", 4, "break"),
    ),
    (
        key(0x35, "`", "alpha", 4, "grave", "tilde"),
        key(0x1E, "1", "alpha", 4),
        key(0x1F, "2", "alpha", 4),
        key(0x20, "3", "alpha", 4),
        key(0x21, "4", "alpha", 4),
        key(0x22, "5", "alpha", 4),
        key(0x23, "6", "alpha", 4),
        key(0x24, "7", "alpha", 4),
        key(0x25, "8", "alpha", 4),
        key(0x26, "9", "alpha", 4),
        key(0x27, "0", "alpha", 4),
        key(0x2D, "-", "alpha", 4, "minus"),
        key(0x2E, "=", "alpha", 4, "equal"),
        key(0x2A, "Bksp", "modifier", 8, "bksp", "backspace"),
        gap(2),
        key(0x49, "Ins", "nav", 4, "insert"),
        key(0x4A, "Hom", "nav", 4, "home"),
        key(0x4B, "PgU", "nav", 4, "pgup", "pageup"),
    ),
    (
        key(0x2B, "Tab", "modifier", 6),
        key(0x14, "Q", "alpha", 4),
        key(0x1A, "W", "alpha", 4),
        key(0x08, "E", "alpha", 4),
        key(0x15, "R", "alpha", 4),
        key(0x17, "T", "alpha", 4),
        key(0x1C, "Y", "alpha", 4),
        key(0x18, "U", "alpha", 4),
        key(0x0C, "I", "alpha", 4),
        key(0x12, "O", "alpha", 4),
        key(0x13, "P", "alpha", 4),
        key(0x2F, "[", "alpha", 4, "bracket"),
        key(0x30, "]", "alpha", 4),
        key(0x31, "\\", "alpha", 6, "backslash"),
        gap(2),
        key(0x4C, "Del", "nav", 4, "delete"),
        key(0x4D, "End", "nav", 4),
        key(0x4E, "PgD", "nav", 4, "pgdn", "pagedown"),
    ),
    (
        key(0x39, "Caps", "modifier", 7, "capslock"),
        key(0x04, "A", "alpha", 4),
        key(0x16, "S", "alpha", 4),
        key(0x07, "D", "alpha", 4),
        key(0x09, "F", "alpha", 4),
        key(0x0A, "G", "alpha", 4),
        key(0x0B, "H", "alpha", 4),
        key(0x0D, "J", "alpha", 4),
        key(0x0E, "K", "alpha", 4),
        key(0x0F, "L", "alpha", 4),
        key(0x33, ";", "alpha", 4, "semicolon"),
        key(0x34, "'", "alpha", 4, "apostrophe", "quote"),
        key(0x28, "Enter", "enter", 9, "return"),
        gap(14),
    ),
    (
        key(0x65, "Shift", "modifier", 9, "lshift", usage=0xE1),
        key(0x1D, "Z", "alpha", 4),
        key(0x1B, "X", "alpha", 4),
        key(0x06, "C", "alpha", 4),
        key(0x19, "V", "alpha", 4),
        key(0x05, "B", "alpha", 4),
        key(0x11, "N", "alpha", 4),
        key(0x10, "M", "alpha", 4),
        key(0x36, ",", "alpha", 4, "comma"),
        key(0x37, ".", "alpha", 4, "dot", "period"),
        key(0x38, "/", "alpha", 4, "slash"),
        key(0x69, "Shift", "modifier", 11, "rshift", usage=0xE5),
        # Up shares Down's column (the inverted T). The gap after Right
        # Shift is what lines that column up with the bottom row.
        gap(6),
        key(0x52, "↑", "arrow", 4, "up"),
        gap(4),
    ),
    (
        key(0x64, "Ctrl", "modifier", 5, "lctrl", "control", usage=0xE0),
        key(0x67, "Sup", "modifier", 5, "win", "super", "meta", usage=0xE3),
        key(0x66, "Alt", "modifier", 5, "lalt", usage=0xE2),
        key(0x2C, "", "space", 27, "space"),
        key(0x6A, "Alt", "modifier", 5, "ralt", usage=0xE6),
        key(0x6C, "B", "super-b", 4, "superb", "super b", usage=0),
        key(0x6D, "A", "super-a", 4, "supera", "super a", usage=0),
        key(0x68, "Ctrl", "modifier", 5, "rctrl", usage=0xE4),
        gap(2),
        key(0x50, "←", "arrow", 4, "left"),
        key(0x51, "↓", "arrow", 4, "down"),
        key(0x4F, "→", "arrow", 4, "right"),
    ),
)


def board_keys() -> tuple[KeyCell, ...]:
    return tuple(cell for row in ROWS for cell in row if cell.kind == "key")


def _blob(cell: KeyCell) -> str:
    return " ".join((cell.label, source_title(cell.code), *cell.aliases)).casefold()


def search_hits(query: str) -> list[int]:
    """Source codes whose name matches. Empty query matches nothing.

    Board order first, then the jack pads, so a click in the list and a
    click on the drawing select the same key.
    """

    needle = query.casefold().strip()
    if not needle:
        return []
    hits = [cell.code for cell in board_keys() if needle in _blob(cell)]
    for jack, button_a, button_b, _primary in JACKS:
        for code, letter in ((button_a, "a"), (button_b, "b")):
            blob = f"{source_title(code)} jack {jack} {letter} {jack}{letter}".casefold()
            if needle in blob:
                hits.append(code)
    return hits


def column_of(code: int) -> int:
    """Quarter-column where this cap starts. Rows share one grid."""

    for row in ROWS:
        column = 0
        for cell in row:
            if cell.kind == "key" and cell.code == code:
                return column
            column += cell.span
    raise KeyError(code)


def board_key_for_usage(usage: int) -> int | None:
    """Board cap that sends this HID usage, or None when it is not drawn.

    F13 collides with the Right Ctrl position number, and Menu collides
    with Left Shift. Match the usage the cap sends, not the position code.
    """

    if usage <= 0:
        return None
    for cell in board_keys():
        if cell.usage == usage:
            return cell.code
    return None


def layout_codes() -> set[int]:
    return {cell.code for cell in board_keys()}


def expected_board_codes() -> set[int]:
    codes = {code for code, _name in KEYBOARD_SOURCES}
    codes.update(code for _name, code in ONBOARD)
    return codes
