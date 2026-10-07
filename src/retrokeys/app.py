"""Window for programming the Retro Keyboard's Super Buttons."""

from __future__ import annotations

import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk, Pango

from .device import KeyboardError, open_keyboard
from .keys import (
    FEATURED,
    JACKS,
    MODIFIERS,
    USAGES,
    hid_from_keycode,
    is_modifier,
    source_title,
)
from .layout import ROWS, board_key_for_usage, search_hits
from .theme import EDITIONS, edition_by_id, load_edition_id, save_edition_id
from .protocol import (
    DELAY,
    DOWN,
    MOD_DOWN,
    MOD_UP,
    UP,
    Binding,
    MacroEvent,
    Profile,
    ProfileError,
)

# Quarter key-unit in pixels. layout.py rows sum to 74 of these.
_CELL = 8
# The pad buttons are circles. The slot around them is the jack hit area.
_PAD = 76
_JACK_OF = {code: name for name, button_a, button_b, _primary in JACKS for code in (button_a, button_b)}

HINT = (
    "One pad belongs in the X jack. Mappings are stored on the keyboard. "
    "Press the heart button so its light is on, or the keyboard ignores them."
)
OFFLINE = (
    "Plug in the USB cable and set the mode switch to off. That is wired mode. "
    "The 2.4 GHz receiver and Bluetooth do not accept configuration."
)


def run(argv: list[str] | None = None) -> int:
    app = RetroApp()
    return app.run(argv)


class RetroApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="online.meijokoen.RetroKeys")
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        self._provider = Gtk.CssProvider()
        self._provider_added = False

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self.apply_edition(edition_by_id("fami"))

    def apply_edition(self, edition) -> None:
        # One stylesheet for the whole window, rebuilt from the colour edition.
        # New widgets should use the role classes (kb.alpha, pad.a, ...) rather
        # than a hard-coded colour, so the Colour menu can restyle them.
        self._provider.load_from_string(edition.palette.css())
        display = Gdk.Display.get_default()
        if display is not None and not self._provider_added:
            Gtk.StyleContext.add_provider_for_display(
                display, self._provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            self._provider_added = True

    def do_activate(self) -> None:
        win = self.props.active_window
        if win is None:
            win = RetroWindow(self)
        win.present()


class RetroWindow(Adw.ApplicationWindow):
    def __init__(self, app: RetroApp) -> None:
        super().__init__(application=app, title="Retro Keys")
        self.set_default_size(1360, 760)
        self.add_css_class("retro")
        display = Gdk.Display.get_default()
        name = display.get_name() if display is not None else ""
        self.x11 = "wayland" not in name.lower()

        self.saved = Profile()
        self.profile = Profile()
        self.selected: int | None = JACKS[2][1]  # Jack X, button A
        self.selected_jack: str | None = JACKS[2][0]
        self.filling = False
        self.listening = False
        self.recording = False
        self.held: set[int] = set()
        self.last_event: float | None = None
        self.find_query = ""
        self.pads: dict[int, tuple[Gtk.Button, Gtk.Label]] = {}
        self.keys: dict[int, Gtk.Button] = {}
        self.jack_cards: dict[int, Gtk.Widget] = {}
        self.edition = edition_by_id(load_edition_id())

        self.toast = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        view.add_top_bar(self._header())
        self.pages = Gtk.Stack()
        self.pages.add_named(self._offline_page(), "offline")
        self.pages.add_named(self._studio_page(), "studio")
        view.set_content(self.pages)
        self.toast.set_child(view)
        self.set_content(self.toast)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key_pressed)
        keys.connect("key-released", self._on_key_released)
        self.add_controller(keys)
        self._reload()

    def _header(self) -> Adw.HeaderBar:
        header = Adw.HeaderBar()
        title = Adw.WindowTitle(title="Retro Keys", subtitle="8BitDo Retro Keyboard")
        header.set_title_widget(title)
        self.name_entry = Gtk.Entry(placeholder_text="Profile name", max_length=14, width_chars=14)
        self.name_entry.connect("changed", self._on_name)
        header.pack_start(self.name_entry)
        colour = Gtk.Box(spacing=6)
        colour_label = Gtk.Label(label="Colour")
        colour_label.add_css_class("hint")
        self.edition_drop = Gtk.DropDown.new_from_strings([edition.name for edition in EDITIONS])
        self.edition_drop.set_selected(EDITIONS.index(self.edition))
        self.edition_drop.set_tooltip_text("Same keys on every edition. This changes the colours.")
        self.edition_drop.connect("notify::selected", self._on_edition)
        colour.append(colour_label)
        colour.append(self.edition_drop)
        header.pack_start(colour)
        application = self.get_application()
        if isinstance(application, RetroApp):
            application.apply_edition(self.edition)
        refresh = Gtk.Button(label="Read")
        refresh.connect("clicked", lambda *_: self._reload(confirm=True))
        header.pack_end(refresh)
        self.write_btn = Gtk.Button(label="Write to keyboard")
        self.write_btn.connect("clicked", lambda *_: self._write())
        header.pack_end(self.write_btn)
        menu = Gtk.MenuButton(icon_name="open-menu-symbolic")
        pop = Gtk.Popover()
        erase = Gtk.Button(label="Erase profile on keyboard")
        erase.add_css_class("destructive-action")
        erase.connect("clicked", self._confirm_erase)
        pop.set_child(erase)
        menu.set_popover(pop)
        header.pack_end(menu)
        return header

    def _offline_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        box.set_margin_start(48)
        box.set_margin_end(48)
        title = Gtk.Label(label="The keyboard is not in wired mode")
        title.add_css_class("title-2")
        body = Gtk.Label(label=OFFLINE, wrap=True, justify=Gtk.Justification.CENTER, width_chars=48)
        body.add_css_class("hint")
        retry = Gtk.Button(label="Try again")
        retry.add_css_class("suggested-action")
        retry.set_halign(Gtk.Align.CENTER)
        retry.connect("clicked", lambda *_: self._reload())
        box.append(title)
        box.append(body)
        box.append(retry)
        return box

    def _studio_page(self) -> Gtk.Widget:
        root = Gtk.Box(spacing=18)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, hexpand=True)
        hint = Gtk.Label(label=HINT, wrap=True, xalign=0, max_width_chars=42, hexpand=True)
        hint.add_css_class("hint")
        left.append(hint)
        jacks = Gtk.Box(spacing=12, homogeneous=True)
        for jack, button_a, button_b, _primary in JACKS:
            jacks.append(self._jack(jack, button_a, button_b))
        left.append(jacks)
        left.append(self._finder())
        left.append(self._board())

        self.others = Gtk.ListBox()
        self.others.add_css_class("boxed-list")
        self.others.set_selection_mode(Gtk.SelectionMode.NONE)
        self.others.set_activate_on_single_click(True)
        self.others.connect("row-activated", self._on_other)
        other_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        other_label = Gtk.Label(label="Other mapped keys", xalign=0)
        other_label.add_css_class("hint")
        other_wrap.append(other_label)
        other_wrap.append(self.others)
        left.append(other_wrap)
        root.append(left)
        root.append(self._editor())
        return root

    def _jack(self, name: str, code_a: int, code_b: int) -> Gtk.Widget:
        # Three hit areas. The card selects the jack. A and B select the jack
        # and that button. The gesture watches the card in the capture phase
        # and steps aside when the click lands on a pad button.
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("jack")
        card.jack_name = name
        card.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        card.set_tooltip_text(f"Jack {name}. Click A or B to edit that button.")
        self.jack_cards[code_a] = card
        self.jack_cards[code_b] = card
        click = Gtk.GestureClick()
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.set_exclusive(False)
        click.connect("pressed", self._on_jack_pressed, card)
        click.connect("released", self._on_jack_released, card)
        card.add_controller(click)
        title = Gtk.Label(label=f"Jack {name}", xalign=0)
        title.add_css_class("jack-title")
        card.append(title)
        row = Gtk.Box(spacing=10, homogeneous=True)
        row.append(self._pad("A", code_a, "a"))
        row.append(self._pad("B", code_b, "b"))
        card.append(row)
        return card

    def _on_jack_pressed(self, gesture, _n_press, x: float, y: float, card) -> None:
        if self._pad_at(card, x, y):
            gesture.set_state(Gtk.EventSequenceState.DENIED)
        else:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _on_jack_released(self, _gesture, _n_press, x: float, y: float, card) -> None:
        if self._pad_at(card, x, y):
            return
        self._select_jack(card.jack_name)

    def _pad_at(self, card, x: float, y: float) -> bool:
        target = card.pick(x, y, Gtk.PickFlags.DEFAULT)
        while target is not None and target is not card:
            if isinstance(target, Gtk.Button) and "pad" in target.get_css_classes():
                return True
            target = target.get_parent()
        return False

    def _finder(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.find_entry = Gtk.SearchEntry(placeholder_text="Find a key")
        self.find_entry.connect("search-changed", self._on_find)
        self.find_entry.connect("activate", self._on_find_activate)
        self.find_entry.connect("notify::has-focus", self._search_focused)
        self.find_list = Gtk.ListBox()
        self.find_list.add_css_class("boxed-list")
        self.find_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.find_list.set_activate_on_single_click(True)
        self.find_list.connect("row-activated", self._on_find_row)
        self.find_scroll = Gtk.ScrolledWindow(child=self.find_list, vexpand=False)
        self.find_scroll.set_propagate_natural_height(True)
        self.find_scroll.set_max_content_height(140)
        self.find_scroll.set_visible(False)
        self.find_empty = Gtk.Label(label="No matching key", xalign=0)
        self.find_empty.add_css_class("hint")
        self.find_empty.set_visible(False)
        box.append(self.find_entry)
        box.append(self.find_scroll)
        box.append(self.find_empty)
        return box

    def _board(self) -> Gtk.Widget:
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        frame.add_css_class("board")
        frame.set_halign(Gtk.Align.CENTER)
        for row in ROWS:
            line = Gtk.Box(spacing=0)
            for cell in row:
                # The slot is the column. The cap is 2px smaller on every
                # side and centered, so a label cannot shove the next key
                # and the arrow columns stay on the same grid.
                slot = Gtk.Box()
                slot.set_size_request(cell.span * _CELL, _CELL * 4)
                if cell.kind == "gap":
                    line.append(slot)
                    continue
                button = Gtk.Button(label=cell.label)
                button.add_css_class("kb")
                button.add_css_class(cell.role)
                button.set_size_request(cell.span * _CELL - 4, _CELL * 4 - 4)
                button.set_halign(Gtk.Align.CENTER)
                button.set_valign(Gtk.Align.CENTER)
                button.set_tooltip_text(source_title(cell.code))
                child = button.get_child()
                if isinstance(child, Gtk.Label):
                    child.set_ellipsize(Pango.EllipsizeMode.END)
                button.connect("clicked", lambda *_b, code=cell.code: self._select(code))
                self.keys[cell.code] = button
                slot.append(button)
                line.append(slot)
            frame.append(line)
        # The drawing is wider than a narrow tile. Scroll sideways instead of
        # clipping the arrow keys. A wide window shows it in full, with no bar.
        scroll = Gtk.ScrolledWindow(child=frame, hexpand=True, vexpand=False)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroll.set_propagate_natural_width(True)
        scroll.set_propagate_natural_height(True)
        return scroll

    def _on_edition(self, dropdown, _param) -> None:
        index = dropdown.get_selected()
        if index < 0 or index >= len(EDITIONS) or EDITIONS[index].id == self.edition.id:
            return
        self.edition = EDITIONS[index]
        save_edition_id(self.edition.id)
        app = self.get_application()
        if isinstance(app, RetroApp):
            app.apply_edition(self.edition)

    def _on_find(self, entry: Gtk.SearchEntry) -> None:
        self.find_query = entry.get_text()
        self._rebuild_find()
        self._paint_sources()
        self._mark_find()

    def _on_find_activate(self, _entry: Gtk.SearchEntry) -> None:
        hits = search_hits(self.find_query)
        if hits:
            self._select(hits[0])

    def _on_find_row(self, _box, row) -> None:
        self._select(row.code)

    def _rebuild_find(self) -> None:
        while (row := self.find_list.get_row_at_index(0)) is not None:
            self.find_list.remove(row)
        hits = search_hits(self.find_query)
        query = self.find_query.strip()
        # A scrolled window collapses to nothing unless it is given a height.
        # Four rows is enough to scan; the rest scroll.
        self.find_scroll.set_min_content_height(min(len(hits), 4) * 36 if hits else 0)
        self.find_scroll.set_visible(bool(query and hits))
        self.find_empty.set_visible(bool(query) and not hits)
        for code in hits:
            label = Gtk.Label(label=source_title(code), xalign=0)
            label.set_margin_start(8)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            item = Gtk.ListBoxRow()
            item.set_child(label)
            item.code = code
            self.find_list.append(item)

    def _pad(self, letter: str, code: int, kind: str) -> Gtk.Widget:
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        button = Gtk.Button(label=letter)
        button.add_css_class("pad")
        button.add_css_class(kind)
        button.set_size_request(_PAD, _PAD)
        button.set_halign(Gtk.Align.CENTER)
        button.set_valign(Gtk.Align.CENTER)
        button.set_hexpand(False)
        button.connect("clicked", lambda *_b, c=code: self._select(c))
        caption = Gtk.Label(label="—")
        caption.add_css_class("cap")
        caption.set_ellipsize(Pango.EllipsizeMode.END)
        caption.set_max_width_chars(14)
        self.pads[code] = (button, caption)
        col.append(button)
        col.append(caption)
        return col

    def _editor(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("editor")
        card.set_size_request(380, -1)
        card.set_vexpand(True)
        self.editor_title = Gtk.Label(xalign=0)
        self.editor_title.add_css_class("hint")
        self.editor_summary = Gtk.Label(xalign=0)
        self.editor_summary.add_css_class("summary")
        card.append(self.editor_title)
        card.append(self.editor_summary)

        self.editor_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, vexpand=True)
        card.append(self.editor_controls)
        self.mode = Gtk.Stack()
        self.mode.add_named(self._key_page(), "key")
        self.mode.add_named(self._chord_page(), "chord")
        self.mode.add_named(self._macro_page(), "macro")
        self._mode_buttons = {}
        switcher = Gtk.Box(homogeneous=True)
        switcher.add_css_class("mode-switch")
        group = None
        for name, label in (("key", "Key"), ("chord", "Chord"), ("macro", "Macro")):
            button = Gtk.ToggleButton(label=label)
            if group is None:
                group = button
            else:
                button.set_group(group)
            button.connect("toggled", self._on_mode, name)
            self._mode_buttons[name] = button
            switcher.append(button)
        self.editor_controls.append(switcher)
        self.editor_controls.append(self.mode)

        clear = Gtk.Button(label="Clear this button")
        clear.connect("clicked", lambda *_: self._assign(None))
        self.editor_controls.append(clear)
        return card

    def _key_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True)
        self.listen_btn = Gtk.Button(label="Press a key…")
        self.listen_btn.connect("clicked", lambda *_: self._toggle_listen())
        note = Gtk.Label(
            label="Esc cancels. The name is the key position the keyboard will send.",
            wrap=True,
            xalign=0,
            max_width_chars=36,
        )
        note.add_css_class("hint")
        box.append(self.listen_btn)
        box.append(note)
        box.append(self._picker("key"))
        return box

    def _chord_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True)
        self.mods = Gtk.DropDown.new_from_strings([long for _code, long, _short in MODIFIERS])
        self.mods.connect("notify::selected", self._on_mod)
        self.chord_btn = Gtk.Button(label="Press the other key…")
        self.chord_btn.connect("clicked", lambda *_: self._toggle_listen(chord=True))
        note = Gtk.Label(
            label="One modifier plus one key. For several keys, record a macro.",
            wrap=True,
            xalign=0,
            max_width_chars=36,
        )
        note.add_css_class("hint")
        box.append(self.mods)
        box.append(self.chord_btn)
        box.append(note)
        box.append(self._picker("chord"))
        return box

    def _macro_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True)
        self.macro_name = Gtk.Entry(placeholder_text="Macro name", max_length=14)
        self.macro_name.connect("changed", self._on_macro_meta)
        row = Gtk.Box(spacing=8)
        row.append(Gtk.Label(label="Repeats"))
        self.repeats = Gtk.SpinButton.new_with_range(1, 99, 1)
        self.repeats.set_value(1)
        self.repeats.connect("value-changed", self._on_macro_meta)
        row.append(self.repeats)
        self.record_btn = Gtk.Button(label="Record")
        self.record_btn.connect("clicked", lambda *_: self._toggle_record())
        row.append(self.record_btn)
        wait = Gtk.Button(label="Add 100 ms")
        wait.connect("clicked", lambda *_: self._add_wait())
        row.append(wait)
        box.append(self.macro_name)
        box.append(row)
        self.steps = Gtk.ListBox()
        self.steps.add_css_class("boxed-list")
        self.steps.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=180, child=self.steps)
        box.append(scroll)
        return box

    def _picker(self, mode: str) -> Gtk.Widget:
        search = Gtk.SearchEntry(placeholder_text="Search keys")
        listing = Gtk.ListBox()
        listing.add_css_class("boxed-list")
        listing.set_selection_mode(Gtk.SelectionMode.NONE)
        listing.set_activate_on_single_click(True)
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=180, child=listing)
        search.connect("search-changed", lambda entry: self._fill_picker(listing, entry.get_text(), mode))
        search.connect("notify::has-focus", self._search_focused)
        listing.connect("row-activated", lambda _box, row, m=mode: self._picked(m, row.usage))
        self._fill_picker(listing, "", mode)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, vexpand=True)
        box.append(search)
        box.append(scroll)
        return box

    def _fill_picker(self, listing: Gtk.ListBox, query: str, mode: str) -> None:
        while (row := listing.get_row_at_index(0)) is not None:
            listing.remove(row)
        needle = query.casefold().strip()
        for usage, long, _short, group in USAGES:
            if mode == "chord" and is_modifier(usage):
                continue
            if needle and needle not in long.casefold() and needle not in group.casefold():
                continue
            label = Gtk.Label(label=long, xalign=0)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            label.set_margin_start(8)
            item = Gtk.ListBoxRow()
            item.set_child(label)
            item.usage = usage
            listing.append(item)

    def _search_focused(self, entry: Gtk.SearchEntry, _param) -> None:
        if entry.has_focus():
            self.listening = False
            self._paint_listen()

    def _reload(self, confirm: bool = False) -> None:
        if confirm and self._dirty():
            self._ask(
                "Discard unsaved changes?",
                "Reading the keyboard again replaces what you have edited.",
                "Read again",
                self._reload,
            )
            return
        try:
            with open_keyboard() as keyboard:
                self.saved = keyboard.load()
        except (KeyboardError, OSError) as exc:
            self.pages.set_visible_child_name("offline")
            self._toast(str(exc))
            return
        self.profile = self.saved.clone()
        self.pages.set_visible_child_name("studio")
        self.filling = True
        self.name_entry.set_text(self.profile.name)
        self.filling = False
        self.listening = False
        self.recording = False
        self._restore_selection()

    def _write(self) -> None:
        if not self._dirty():
            self._toast("Nothing new to write.")
            return
        try:
            with open_keyboard() as keyboard:
                self.saved = keyboard.save(self.saved, self.profile)
        except ProfileError as exc:
            self._toast(str(exc))
            return
        except (KeyboardError, OSError) as exc:
            self._toast(str(exc))
            self._reload()
            return
        self.profile = self.saved.clone()
        self.filling = True
        self.name_entry.set_text(self.profile.name)
        self.filling = False
        self._paint()
        self._toast("Saved on the keyboard. Turn the heart light on to use it.")

    def _confirm_erase(self, *_args) -> None:
        self._ask(
            "Erase the profile on the keyboard?",
            "This clears the name and every mapping. The heart button turns off.",
            "Erase",
            self._erase,
            destructive=True,
        )

    def _erase(self) -> None:
        try:
            with open_keyboard() as keyboard:
                self.saved = keyboard.erase()
        except (KeyboardError, OSError) as exc:
            self._toast(str(exc))
            return
        self.profile = self.saved.clone()
        self.filling = True
        self.name_entry.set_text("")
        self.filling = False
        self._restore_selection()
        self._toast("Profile erased.")

    def _ask(self, heading: str, body: str, accept: str, callback, destructive: bool = False) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("go", accept)
        dialog.set_response_appearance(
            "go",
            Adw.ResponseAppearance.DESTRUCTIVE if destructive else Adw.ResponseAppearance.SUGGESTED,
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def done(source, result) -> None:
            if source.choose_finish(result) == "go":
                callback()

        dialog.choose(self, None, done)

    def _restore_selection(self) -> None:
        if self.selected is not None:
            self._select(self.selected)
        elif self.selected_jack:
            self._select_jack(self.selected_jack)
        else:
            self._select(JACKS[2][1])

    def _select(self, code: int) -> None:
        self.selected = code
        self.selected_jack = _JACK_OF.get(code)
        self._arm_editor()

    def _select_jack(self, name: str) -> None:
        self.selected = None
        self.selected_jack = name
        self._arm_editor()

    def _arm_editor(self) -> None:
        self.listening = False
        self.recording = False
        self.held.clear()
        self.last_event = None
        self._fill_editor()
        self._paint()

    def _fill_editor(self) -> None:
        jack_only = self.selected is None
        self.editor_controls.set_visible(not jack_only)
        if jack_only:
            self.editor_title.set_text(f"Jack {self.selected_jack}" if self.selected_jack else "")
            self.editor_summary.set_text("Choose A or B")
            return
        binding = self.profile.bindings.get(self.selected)
        self.filling = True
        self.editor_title.set_text(source_title(self.selected))
        if binding is None:
            self.mode.set_visible_child_name("key")
            self.macro_name.set_text("")
            self.repeats.set_value(1)
            self._set_steps(())
        elif binding.kind == "macro":
            self.mode.set_visible_child_name("macro")
            self.macro_name.set_text(binding.macro_name)
            self.repeats.set_value(binding.repeats)
            self._set_steps(binding.events)
        elif binding.kind == "key" and binding.mod and binding.usage:
            self.mode.set_visible_child_name("chord")
            self._select_mod(binding.mod)
        elif binding.kind == "key" and binding.mod:
            self.mode.set_visible_child_name("key")
        else:
            self.mode.set_visible_child_name("key")
        self.filling = False
        self._paint_summary()

    def _paint(self) -> None:
        self._paint_sources()
        self._mark_find()
        self._paint_others()
        self._paint_summary()
        self._paint_listen()
        if self._dirty():
            self.write_btn.add_css_class("suggested-action")
        else:
            self.write_btn.remove_css_class("suggested-action")

    def _target_key(self) -> int | None:
        """Cap that shows the key this source will send, when one is drawn."""

        if self.selected is None:
            return None
        binding = self.profile.bindings.get(self.selected)
        if binding is None or binding.kind != "key":
            return None
        if binding.usage:
            return board_key_for_usage(binding.usage)
        return board_key_for_usage(binding.mod)

    def _paint_sources(self) -> None:
        hits = set(search_hits(self.find_query))
        target = self._target_key()
        seen_cards: set[int] = set()
        for code, card in self.jack_cards.items():
            card_id = id(card)
            if card_id in seen_cards:
                continue
            seen_cards.add(card_id)
            if self.selected_jack == card.jack_name:
                card.add_css_class("is-selected")
            else:
                card.remove_css_class("is-selected")
        for code, (button, caption) in self.pads.items():
            self._paint_button(code, button, hits)
            binding = self.profile.bindings.get(code)
            caption.set_text("—" if binding is None else binding.summary())
        for code, button in self.keys.items():
            self._paint_button(code, button, hits, target=code == target)

    def _paint_button(self, code: int, button: Gtk.Button, hits: set[int], target: bool = False) -> None:
        binding = self.profile.bindings.get(code)
        title = source_title(code)
        button.set_tooltip_text(title if binding is None else f"{title}: {binding.summary()}")
        if code == self.selected:
            button.add_css_class("is-selected")
        else:
            button.remove_css_class("is-selected")
        if target:
            button.add_css_class("is-target")
        else:
            button.remove_css_class("is-target")
        if code in hits:
            button.add_css_class("is-match")
        else:
            button.remove_css_class("is-match")
        if binding is None:
            button.remove_css_class("is-on")
        else:
            button.add_css_class("is-on")

    def _mark_find(self) -> None:
        index = 0
        while (row := self.find_list.get_row_at_index(index)) is not None:
            if getattr(row, "code", None) == self.selected:
                row.add_css_class("is-selected")
            else:
                row.remove_css_class("is-selected")
            index += 1

    def _paint_summary(self) -> None:
        if self.selected is None:
            self.editor_summary.set_text("Choose A or B")
            return
        binding = self.profile.bindings.get(self.selected)
        self.editor_summary.set_text("Not set" if binding is None else binding.summary())

    def _on_mode(self, button: Gtk.ToggleButton, name: str) -> None:
        if button.get_active():
            self.mode.set_visible_child_name(name)
            self._paint_listen()

    def _sync_mode(self) -> None:
        name = self.mode.get_visible_child_name()
        button = self._mode_buttons.get(name)
        if button is not None and not button.get_active():
            button.set_active(True)

    def _paint_listen(self) -> None:
        self._sync_mode()
        self.listen_btn.set_label("Listening…  Esc cancels" if self.listening and self.mode.get_visible_child_name() == "key" else "Press a key…")
        chord = self.listening and self.mode.get_visible_child_name() == "chord"
        self.chord_btn.set_label("Listening…  Esc cancels" if chord else "Press the other key…")
        self.record_btn.set_label("Stop" if self.recording else "Record")
        self.macro_name.set_sensitive(not self.recording)

    def _paint_others(self) -> None:
        while (row := self.others.get_row_at_index(0)) is not None:
            self.others.remove(row)
        extras = [(code, binding) for code, binding in sorted(self.profile.bindings.items()) if code not in FEATURED]
        self.others.set_visible(bool(extras))
        for code, binding in extras:
            label = Gtk.Label(label=f"{source_title(code)}    {binding.summary()}", xalign=0)
            label.set_margin_start(8)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            item = Gtk.ListBoxRow()
            item.set_child(label)
            item.code = code
            self.others.append(item)

    def _on_other(self, _box, row) -> None:
        self._select(row.code)

    def _on_name(self, entry: Gtk.Entry) -> None:
        if self.filling:
            return
        self.profile.name = entry.get_text()
        self._paint()

    def _toggle_listen(self, chord: bool = False) -> None:
        want = "chord" if chord else "key"
        if self.listening and self.mode.get_visible_child_name() == want:
            self.listening = False
        else:
            self.recording = False
            self.listening = True
            self.mode.set_visible_child_name(want)
        self._paint_listen()

    def _toggle_record(self) -> None:
        self.recording = not self.recording
        self.listening = False
        if self.recording:
            self.held.clear()
            self.last_event = None
            if self.selected not in self.profile.bindings or self.profile.bindings[self.selected].kind != "macro":
                self._set_steps(())
                self.filling = True
                if not self.macro_name.get_text():
                    self.macro_name.set_text("")
                self.filling = False
        self._paint_listen()

    def _on_key_pressed(self, _controller, keyval: int, keycode: int, _state) -> bool:
        if keyval == Gdk.KEY_Escape and self.listening:
            self.listening = False
            self._paint_listen()
            return True
        if not self.listening and not self.recording:
            return False
        usage = hid_from_keycode(keycode, x11=self.x11)
        if usage is None:
            return True
        if self.recording:
            self._record(usage, down=True)
            return True
        if self.mode.get_visible_child_name() == "chord":
            if is_modifier(usage):
                self._toast("Choose the modifier in the list. Then press the other key.")
                return True
            self._assign(Binding("key", mod=self._current_mod(), usage=usage))
        elif is_modifier(usage):
            self._assign(Binding("key", mod=usage))
        else:
            self._assign(Binding("key", usage=usage))
        self.listening = False
        self._paint_listen()
        return True

    def _on_key_released(self, _controller, _keyval: int, keycode: int, _state) -> bool:
        if not self.recording:
            return False
        usage = hid_from_keycode(keycode, x11=self.x11)
        if usage is None:
            return True
        self._record(usage, down=False)
        return True

    def _record(self, usage: int, down: bool) -> None:
        if down:
            if usage in self.held:
                return
            self.held.add(usage)
        else:
            if usage not in self.held:
                return
            self.held.discard(usage)
        self._gap()
        if is_modifier(usage):
            action = MOD_DOWN if down else MOD_UP
        else:
            action = DOWN if down else UP
        events = list(self._current_events())
        events.append(MacroEvent(action, usage))
        if len(events) > 80:
            self.recording = False
            self._toast("Stopped at 80 steps.")
        self._commit_events(tuple(events))

    def _gap(self) -> None:
        now = time.monotonic()
        if self.last_event is not None:
            waited = int((now - self.last_event) * 1000)
            if waited >= 15:
                events = list(self._current_events())
                events.append(MacroEvent(DELAY, min(waited, 60000)))
                self._commit_events(tuple(events), paint_steps=False)
        self.last_event = now

    def _add_wait(self) -> None:
        events = list(self._current_events())
        events.append(MacroEvent(DELAY, 100))
        self._commit_events(tuple(events))

    def _current_events(self) -> tuple[MacroEvent, ...]:
        binding = self.profile.bindings.get(self.selected)
        if binding is not None and binding.kind == "macro":
            return binding.events
        return ()

    def _commit_events(self, events: tuple[MacroEvent, ...], paint_steps: bool = True) -> None:
        if not events:
            return
        self._assign(
            Binding(
                "macro",
                macro_name=self.macro_name.get_text(),
                repeats=int(self.repeats.get_value()),
                events=events,
            ),
            refill=False,
        )
        if paint_steps:
            self._set_steps(events)

    def _set_steps(self, events: tuple[MacroEvent, ...]) -> None:
        while (row := self.steps.get_row_at_index(0)) is not None:
            self.steps.remove(row)
        for index, event in enumerate(events):
            line = Gtk.Box(spacing=8)
            label = Gtk.Label(label=event.label(), xalign=0, hexpand=True)
            label.set_margin_start(8)
            remove = Gtk.Button(icon_name="list-remove-symbolic")
            remove.set_tooltip_text("Remove step")
            remove.add_css_class("flat")
            remove.connect("clicked", lambda *_a, i=index: self._drop_step(i))
            line.append(label)
            line.append(remove)
            item = Gtk.ListBoxRow()
            item.set_child(line)
            self.steps.append(item)

    def _drop_step(self, index: int) -> None:
        events = list(self._current_events())
        if index >= len(events):
            return
        del events[index]
        if events:
            self._commit_events(tuple(events))
        else:
            self._assign(None)

    def _on_macro_meta(self, *_args) -> None:
        if self.filling:
            return
        events = self._current_events()
        if not events:
            return
        self._assign(
            Binding(
                "macro",
                macro_name=self.macro_name.get_text(),
                repeats=int(self.repeats.get_value()),
                events=events,
            ),
            refill=False,
        )

    def _on_mod(self, *_args) -> None:
        if self.filling:
            return
        binding = self.profile.bindings.get(self.selected)
        if binding is None or binding.kind != "key" or not binding.usage:
            return
        self._assign(Binding("key", mod=self._current_mod(), usage=binding.usage), refill=False)

    def _current_mod(self) -> int:
        index = self.mods.get_selected()
        if index < 0 or index >= len(MODIFIERS):
            return MODIFIERS[0][0]
        return MODIFIERS[index][0]

    def _select_mod(self, code: int) -> None:
        for index, (mod, _long, _short) in enumerate(MODIFIERS):
            if mod == code:
                self.mods.set_selected(index)
                return

    def _picked(self, mode: str, usage: int) -> None:
        if mode == "chord":
            self._assign(Binding("key", mod=self._current_mod(), usage=usage))
            return
        if is_modifier(usage):
            self._assign(Binding("key", mod=usage))
        else:
            self._assign(Binding("key", usage=usage))

    def _assign(self, binding: Binding | None, refill: bool = True) -> None:
        if self.selected is None:
            return
        if binding is None:
            self.profile.bindings.pop(self.selected, None)
        else:
            self.profile.bindings[self.selected] = binding
        if refill:
            self._fill_editor()
        self._paint()

    def _dirty(self) -> bool:
        return self.profile.name != self.saved.name or self.profile.bindings != self.saved.bindings

    def _toast(self, text: str) -> None:
        self.toast.add_toast(Adw.Toast(title=text, timeout=4))
