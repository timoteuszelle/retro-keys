"""Colour editions of the Retro Keyboard.

The key positions do not change between editions. A palette fills the role
slots from layout.py (alpha, function, escape, the Super A and B keys, and
the rest) and the app chrome around them. Add a palette to support another
colourway. A different body shape belongs in layout.py, selected by
Edition.layout.

Fami matches the keyboard this project was built against. N and M follow
the product photos. C64 is a first pass at the beige and brown edition.
Xbox is the translucent green Retro 87. Its arrow keys use the controller
colours, and the window draws the case button separately.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path

# Tokens in the stylesheet are written @name@ and filled from the palette.
_CSS = """
window.retro { background-color: @window@; color: @text@; }
window.retro headerbar {
  background: @header@;
  color: @text@;
  box-shadow: none;
}
window.retro entry { background-color: @entry@; color: @text@; }
window.retro dropdown,
window.retro dropdown > button,
window.retro popover {
  background-color: @entry@;
  color: @text@;
}
.hint { color: @hint@; font-size: 13px; }
.jack {
  background-color: @card@;
  border-radius: 18px;
  padding: 12px 14px 14px;
}
.jack:hover { box-shadow: inset 0 0 0 2px @hint@; }
.jack.is-selected,
.jack.is-selected:hover { box-shadow: inset 0 0 0 2px @selection@; }
.jack-title { font-weight: 700; color: @text@; }
button.pad {
  min-width: 76px;
  min-height: 76px;
  padding: 0;
  border-radius: 999px;
  font-size: 22px;
  font-weight: 800;
  background-image: none;
  border: 3px solid transparent;
  box-shadow: none;
}
button.pad.a { background-color: @pad_a@; color: @pad_a_text@; }
button.pad.b { background-color: @pad_b@; color: @pad_b_text@; }
button.pad:hover { filter: brightness(1.06); }
button.pad.is-on { box-shadow: 0 0 0 1px @mapped@; }
button.pad.is-match { border-color: @find@; }
button.pad.is-selected { border-color: @selection@; }
button.pad.is-on.is-match {
  border-color: @find@;
  box-shadow: 0 0 0 1px @mapped@;
}
button.pad.is-on.is-selected {
  border-color: @selection@;
  box-shadow: 0 0 0 1px @mapped@;
}
button.pad.is-selected.is-match,
button.pad.is-on.is-selected.is-match {
  border-color: @selection@;
  box-shadow: 0 0 0 2px @find@;
}
.cap { color: @hint@; font-size: 12px; }
.summary { font-size: 22px; font-weight: 700; color: @text@; }
.editor {
  background-color: @editor@;
  border-radius: 18px;
  padding: 16px;
}
.editor.is-inactive {
  background-color: @window@;
  box-shadow: inset 0 0 0 2px @header@;
}
.editor.is-inactive .summary { color: @hint@; }
.editor.is-inactive .editor-controls { opacity: 0.45; }
.board {
  background-color: @board@;
  border-radius: 16px;
  padding: 8px;
}
button.kb {
  min-width: 0;
  min-height: 0;
  padding: 0;
  margin: 0;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  background-image: none;
  border: none;
  box-shadow: none;
}
button.kb.alpha { background-color: @alpha_bg@; color: @alpha_fg@; }
button.kb.function { background-color: @function_bg@; color: @function_fg@; }
button.kb.escape { background-color: @escape_bg@; color: @escape_fg@; }
button.kb.enter { background-color: @enter_bg@; color: @enter_fg@; }
button.kb.modifier { background-color: @modifier_bg@; color: @modifier_fg@; }
button.kb.nav { background-color: @nav_bg@; color: @nav_fg@; }
button.kb.arrow { background-color: @arrow_bg@; color: @arrow_fg@; }
button.kb.xbox {
  border-radius: 999px;
  background-color: @accent@;
  color: @accent_text@;
  font-size: 11px;
  font-weight: 800;
}
button.kb.space { background-color: @space_bg@; color: @space_fg@; }
button.kb.super-a { background-color: @super_a_bg@; color: @super_a_fg@; }
button.kb.super-b { background-color: @super_b_bg@; color: @super_b_fg@; }
button.kb:hover { filter: brightness(1.08); }
button.kb.is-on { box-shadow: inset 0 -3px 0 @mapped@; }
button.kb.is-selected { box-shadow: inset 0 0 0 2px @selection@; }
button.kb.is-on.is-selected {
  box-shadow: inset 0 0 0 2px @selection@, inset 0 -3px 0 @mapped@;
}
button.kb.is-target,
button.kb.is-on.is-target,
button.kb.is-selected.is-target,
button.kb.is-on.is-selected.is-target {
  background-color: @selection@;
  color: @find_text@;
}
button.kb.is-match,
button.kb.is-on.is-match,
button.kb.is-selected.is-match,
button.kb.is-on.is-selected.is-match,
button.kb.is-target.is-match,
button.kb.is-on.is-target.is-match,
button.kb.is-selected.is-target.is-match,
button.kb.is-on.is-selected.is-target.is-match {
  background-color: @find@;
  color: @find_text@;
}
button.kb.is-selected.is-match,
button.kb.is-on.is-selected.is-match,
button.kb.is-target.is-match,
button.kb.is-on.is-target.is-match,
button.kb.is-selected.is-target.is-match,
button.kb.is-on.is-selected.is-target.is-match {
  box-shadow: inset 0 0 0 3px @selection@;
}
.mode-switch {
  background-color: @window@;
  border-radius: 12px;
  padding: 3px;
}
.mode-switch button {
  background-image: none;
  background-color: transparent;
  box-shadow: none;
  border-radius: 9px;
  color: @hint@;
  font-weight: 700;
}
.mode-switch button:checked {
  background-color: @accent@;
  color: @accent_text@;
}
.response-area { background-color: @editor@; }
.response-area > button {
  background-image: none;
  background-color: @card@;
  color: @text@;
  box-shadow: none;
}
.response-area > button.destructive-action,
.response-area > button.suggested-action,
window.retro button.suggested-action,
window.retro button.destructive-action {
  background-color: @accent@;
  color: @accent_text@;
}
window.retro scrolledwindow,
window.retro viewport,
window.retro list,
window.retro list > row {
  background-color: @list_bg@;
  color: @text@;
}
window.retro list > row:hover { background-color: @list_hover@; }
window.retro list > row:selected,
window.retro list > row.is-selected {
  background-color: @list_selected@;
  color: @accent_text@;
}
"""


@dataclass(frozen=True)
class Palette:
    window: str
    header: str
    entry: str
    text: str
    hint: str
    card: str
    editor: str
    list_bg: str
    list_hover: str
    list_selected: str
    accent: str
    accent_text: str
    selection: str
    mapped: str
    find: str
    find_text: str
    pad_a: str
    pad_a_text: str
    pad_b: str
    pad_b_text: str
    board: str
    alpha_bg: str
    alpha_fg: str
    function_bg: str
    function_fg: str
    escape_bg: str
    escape_fg: str
    enter_bg: str
    enter_fg: str
    modifier_bg: str
    modifier_fg: str
    nav_bg: str
    nav_fg: str
    arrow_bg: str
    arrow_fg: str
    space_bg: str
    space_fg: str
    super_a_bg: str
    super_a_fg: str
    super_b_bg: str
    super_b_fg: str

    def css(self) -> str:
        text = _CSS
        for field in fields(self):
            text = text.replace(f"@{field.name}@", getattr(self, field.name))
        return text


# Controller colours on the arrow cluster: up Y, left X, down A, right B.
# Repeated after the shared rules so a target or a search match still wins.
_XBOX_ARROWS = """
button.kb.up { background-color: #f5c518; color: #241c04; }
button.kb.left { background-color: #2f6fdb; color: #f4f8ff; }
button.kb.down { background-color: #7ed321; color: #14280c; }
button.kb.right { background-color: #e23b32; color: #fff6f4; }
button.kb.up.is-target,
button.kb.left.is-target,
button.kb.down.is-target,
button.kb.right.is-target {
  background-color: #f2c200;
  color: #241c04;
}
button.kb.up.is-match,
button.kb.left.is-match,
button.kb.down.is-match,
button.kb.right.is-match {
  background-color: #7ee7ff;
  color: #102028;
}
"""


@dataclass(frozen=True)
class Edition:
    id: str
    name: str
    layout: str
    palette: Palette
    extra_css: str = ""


def _palette(**colors: str) -> Palette:
    return Palette(**colors)


# Shared dark-app shape. Keycap colours are the part that tracks the plastic.
_FAMI = _palette(
    window="#161014",
    header="#1c1216",
    entry="#2a1c22",
    text="#f6efe6",
    hint="#cbbbae",
    card="#2a1c22",
    editor="#24181e",
    list_bg="#1c1216",
    list_hover="#322028",
    list_selected="#3a2830",
    accent="#e10600",
    accent_text="#fff8f4",
    selection="#e2b340",
    mapped="#e2b340",
    find="#7ee7ff",
    find_text="#102028",
    pad_a="#e10600",
    pad_a_text="#fff8f4",
    pad_b="#f3ead8",
    pad_b_text="#241418",
    board="#3a2228",
    alpha_bg="#f3ead8",
    alpha_fg="#c41212",
    function_bg="#e10600",
    function_fg="#fff8f4",
    escape_bg="#e10600",
    escape_fg="#fff8f4",
    enter_bg="#e10600",
    enter_fg="#fff8f4",
    modifier_bg="#f3ead8",
    modifier_fg="#c41212",
    nav_bg="#f3ead8",
    nav_fg="#c41212",
    arrow_bg="#1a1214",
    arrow_fg="#f3ead8",
    space_bg="#f3ead8",
    space_fg="#c41212",
    super_a_bg="#e10600",
    super_a_fg="#fff8f4",
    super_b_bg="#f3ead8",
    super_b_fg="#241418",
)

_N = _palette(
    window="#1c1e22",
    header="#26282c",
    entry="#32363c",
    text="#f4f1ea",
    hint="#c8c2b8",
    card="#2c3036",
    editor="#24282e",
    list_bg="#1e2126",
    list_hover="#343a42",
    list_selected="#3e4650",
    accent="#d0121a",
    accent_text="#fff8f4",
    selection="#ffd24a",
    mapped="#ffd24a",
    find="#7ee7ff",
    find_text="#102028",
    pad_a="#e10600",
    pad_a_text="#fff8f4",
    pad_b="#9aa0a6",
    pad_b_text="#1a1c1e",
    board="#cfc8be",
    alpha_bg="#f4f1ea",
    alpha_fg="#d0121a",
    function_bg="#e4e0d8",
    function_fg="#d0121a",
    escape_bg="#e10600",
    escape_fg="#fff8f4",
    enter_bg="#e10600",
    enter_fg="#fff8f4",
    modifier_bg="#6a6e74",
    modifier_fg="#f4f1ea",
    nav_bg="#5a5e64",
    nav_fg="#f4f1ea",
    arrow_bg="#1a1c1e",
    arrow_fg="#f4f1ea",
    space_bg="#f4f1ea",
    space_fg="#d0121a",
    super_a_bg="#e10600",
    super_a_fg="#fff8f4",
    super_b_bg="#8b9096",
    super_b_fg="#f4f1ea",
)

_M = _palette(
    window="#1a1c1e",
    header="#242628",
    entry="#2e3230",
    text="#f3f1ea",
    hint="#c9c6be",
    card="#2a2e2c",
    editor="#222624",
    list_bg="#1e2124",
    list_hover="#34383a",
    list_selected="#3a4044",
    accent="#2f6fdb",
    accent_text="#f7fbff",
    selection="#f0c14a",
    mapped="#2f6fdb",
    find="#7ee7ff",
    find_text="#102028",
    pad_a="#e7e8ec",
    pad_a_text="#1d4e9e",
    pad_b="#e7e8ec",
    pad_b_text="#1d4e9e",
    board="#c8c6c0",
    alpha_bg="#f7f6f2",
    alpha_fg="#2a2c2e",
    function_bg="#e6e4de",
    function_fg="#2a2c2e",
    escape_bg="#e6e4de",
    escape_fg="#2a2c2e",
    enter_bg="#d5d6da",
    enter_fg="#2a2c2e",
    modifier_bg="#b7b8bc",
    modifier_fg="#2a2c2e",
    nav_bg="#b7b8bc",
    nav_fg="#2a2c2e",
    arrow_bg="#a9aaae",
    arrow_fg="#2a2c2e",
    space_bg="#f7f6f2",
    space_fg="#2a2c2e",
    super_a_bg="#f7f6f2",
    super_a_fg="#1d4e9e",
    super_b_bg="#f7f6f2",
    super_b_fg="#1d4e9e",
)

_C64 = _palette(
    window="#1a1410",
    header="#261c16",
    entry="#3a2a22",
    text="#f6efe4",
    hint="#d9c7b0",
    card="#2e221c",
    editor="#241a16",
    list_bg="#1e1612",
    list_hover="#3a2c24",
    list_selected="#4a382c",
    accent="#c4492c",
    accent_text="#fff6f0",
    selection="#f0c14a",
    mapped="#f0c14a",
    find="#7ee7ff",
    find_text="#102028",
    pad_a="#c4492c",
    pad_a_text="#fff6f0",
    pad_b="#e7d3b0",
    pad_b_text="#3a2418",
    board="#d7c4a0",
    alpha_bg="#6b442c",
    alpha_fg="#f6ead8",
    function_bg="#8a5a38",
    function_fg="#f6ead8",
    escape_bg="#c4492c",
    escape_fg="#fff6f0",
    enter_bg="#c4492c",
    enter_fg="#fff6f0",
    modifier_bg="#4a3022",
    modifier_fg="#f6ead8",
    nav_bg="#5c4030",
    nav_fg="#f6ead8",
    arrow_bg="#3a2418",
    arrow_fg="#f6ead8",
    space_bg="#6b442c",
    space_fg="#f6ead8",
    super_a_bg="#c4492c",
    super_a_fg="#fff6f0",
    super_b_bg="#e7d3b0",
    super_b_fg="#3a2418",
)

_XBOX = _palette(
    window="#101c14",
    header="#16281c",
    entry="#1e3426",
    text="#f3fbe6",
    hint="#c5ddb0",
    card="#1a2e22",
    editor="#15261c",
    list_bg="#122018",
    list_hover="#24382a",
    list_selected="#2e4634",
    accent="#3caf3c",
    accent_text="#f4fff4",
    selection="#f2c200",
    mapped="#f2c200",
    find="#7ee7ff",
    find_text="#102028",
    pad_a="#245c32",
    pad_a_text="#e9f8c8",
    pad_b="#163222",
    pad_b_text="#d7efc4",
    board="#3e7c36",
    alpha_bg="#4f9444",
    alpha_fg="#e7f6b4",
    function_bg="#4f9444",
    function_fg="#e7f6b4",
    escape_bg="#4f9444",
    escape_fg="#e7f6b4",
    enter_bg="#4f9444",
    enter_fg="#e7f6b4",
    modifier_bg="#3d8638",
    modifier_fg="#e7f6b4",
    nav_bg="#3d8638",
    nav_fg="#e7f6b4",
    arrow_bg="#4f9444",
    arrow_fg="#e7f6b4",
    space_bg="#4f9444",
    space_fg="#e7f6b4",
    super_a_bg="#b6dc6a",
    super_a_fg="#163010",
    super_b_bg="#2f7a38",
    super_b_fg="#f3ffe8",
)

EDITIONS: tuple[Edition, ...] = (
    Edition("fami", "Fami", "tkl", _FAMI),
    Edition("n", "N", "tkl", _N),
    Edition("m", "M", "tkl", _M),
    Edition("c64", "C64", "tkl", _C64),
    Edition("xbox", "Xbox", "tkl", _XBOX, _XBOX_ARROWS),
)

BY_ID: dict[str, Edition] = {edition.id: edition for edition in EDITIONS}


def edition_by_id(edition_id: str) -> Edition:
    return BY_ID.get(edition_id, BY_ID["fami"])


def _edition_file(config_home: Path | None) -> Path:
    if config_home is None:
        env = os.environ.get("XDG_CONFIG_HOME")
        base = Path(env) if env else Path.home() / ".config"
    else:
        base = config_home
    return base / "retro-keys" / "edition"


def load_edition_id(config_home: Path | None = None) -> str:
    path = _edition_file(config_home)
    try:
        edition_id = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "fami"
    return edition_id if edition_id in BY_ID else "fami"


def save_edition_id(edition_id: str, config_home: Path | None = None) -> None:
    if edition_id not in BY_ID:
        return
    path = _edition_file(config_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(edition_id + "\n", encoding="utf-8")
