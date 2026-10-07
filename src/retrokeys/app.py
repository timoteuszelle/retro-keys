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
    KEYBOARD_SOURCES,
    MODIFIERS,
    ONBOARD,
    USAGES,
    hid_from_keycode,
    is_modifier,
    source_title,
)
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

CSS = """
window.retro { background-color: #161014; }
window.retro headerbar {
  background: #1c1216;
  box-shadow: none;
}
window.retro entry { background-color: #2a1c22; color: #f6efe6; }
.hint { color: #cbbbae; font-size: 13px; }
.jack {
  background-color: #2a1c22;
  border-radius: 18px;
  padding: 12px 14px 14px;
}
.jack.primary { box-shadow: inset 0 0 0 1px #e2b340; }
.jack-title { font-weight: 700; }
.jack-note { color: #e2b340; font-size: 11px; }
button.pad {
  min-width: 92px;
  min-height: 92px;
  padding: 0;
  border-radius: 46px;
  font-size: 26px;
  font-weight: 800;
  background-image: none;
  border: 3px solid transparent;
  box-shadow: none;
}
button.pad.a { background-color: #e10600; color: #fff8f4; }
button.pad.b { background-color: #f3ead8; color: #241418; }
button.pad:hover { filter: brightness(1.06); }
button.pad.is-on { box-shadow: 0 0 0 1px rgba(255,255,255,0.16); }
button.keycap {
  min-width: 92px;
  min-height: 52px;
  border-radius: 10px;
  font-weight: 700;
  background-image: none;
  background-color: #3a2830;
  color: #f6efe6;
  border: 3px solid transparent;
}
button.pad.is-selected, button.keycap.is-selected { border-color: #e2b340; }
.cap { color: #d9cdc2; font-size: 12px; }
.summary { font-size: 22px; font-weight: 700; }
.editor {
  background-color: #24181e;
  border-radius: 18px;
  padding: 16px;
}
.mode-switch {
  background-color: #1a1014;
  border-radius: 12px;
  padding: 3px;
}
.mode-switch button {
  background-image: none;
  background-color: transparent;
  box-shadow: none;
  border-radius: 9px;
  color: #d9cdc2;
  font-weight: 700;
}
.mode-switch button:checked {
  background-color: #e10600;
  color: #fff8f4;
}
.response-area {
  background-color: #24181e;
}
.response-area > button {
  background-image: none;
  background-color: #3a2830;
  color: #f6efe6;
  box-shadow: none;
}
.response-area > button.destructive-action,
.response-area > button.suggested-action {
  background-color: #e10600;
  color: #fff8f4;
}
window.retro scrolledwindow,
window.retro viewport,
window.retro list,
window.retro list > row {
  background-color: #1c1216;
  color: #f6efe6;
}
window.retro list > row:hover {
  background-color: #322028;
}
window.retro list > row:selected {
  background-color: #3a2830;
  color: #fff8f4;
}
"""

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

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

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
        self.selected = JACKS[2][1]  # Jack X, button A
        self.filling = False
        self.listening = False
        self.recording = False
        self.held: set[int] = set()
        self.last_event: float | None = None
        self.pads: dict[int, tuple[Gtk.Button, Gtk.Label]] = {}

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
        for jack, button_a, button_b, primary in JACKS:
            jacks.append(self._jack(jack, button_a, button_b, primary))
        left.append(jacks)

        board_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        label = Gtk.Label(label="On the keyboard", xalign=0)
        label.add_css_class("jack-title")
        board = Gtk.Box(spacing=16, halign=Gtk.Align.START)
        for name, code in ONBOARD:
            board.append(self._keycap(name, code))
        board_col.append(label)
        board_col.append(board)
        left.append(board_col)

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
        more = Gtk.Button(label="Edit another key…")
        more.set_halign(Gtk.Align.START)
        more.connect("clicked", lambda *_: self._pick_source())
        other_wrap.append(more)
        left.append(other_wrap)
        root.append(left)
        root.append(self._editor())
        return root

    def _jack(self, name: str, code_a: int, code_b: int, primary: bool) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("jack")
        if primary:
            card.add_css_class("primary")
        title = Gtk.Label(label=f"Jack {name}", xalign=0)
        title.add_css_class("jack-title")
        card.append(title)
        if primary:
            note = Gtk.Label(label="Single pad goes here", xalign=0)
            note.add_css_class("jack-note")
            card.append(note)
        row = Gtk.Box(spacing=10, homogeneous=True)
        row.append(self._pad("A", code_a, "a"))
        row.append(self._pad("B", code_b, "b"))
        card.append(row)
        return card

    def _pad(self, letter: str, code: int, kind: str) -> Gtk.Widget:
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        button = Gtk.Button(label=letter)
        button.add_css_class("pad")
        button.add_css_class(kind)
        button.connect("clicked", lambda *_b, c=code: self._select(c))
        caption = Gtk.Label(label="—")
        caption.add_css_class("cap")
        caption.set_ellipsize(Pango.EllipsizeMode.END)
        caption.set_max_width_chars(14)
        self.pads[code] = (button, caption)
        col.append(button)
        col.append(caption)
        return col

    def _keycap(self, name: str, code: int) -> Gtk.Widget:
        button = Gtk.Button(label=name)
        button.add_css_class("keycap")
        button.connect("clicked", lambda *_b, c=code: self._select(c))
        caption = Gtk.Label(label="—")
        caption.add_css_class("cap")
        self.pads[code] = (button, caption)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(button)
        box.append(caption)
        return box

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
        card.append(switcher)
        card.append(self.mode)

        clear = Gtk.Button(label="Clear this button")
        clear.connect("clicked", lambda *_: self._assign(None))
        card.append(clear)
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
        self._select(self.selected)

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
        self._select(self.selected)
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

    def _select(self, code: int) -> None:
        self.selected = code
        self.listening = False
        self.recording = False
        self.held.clear()
        self.last_event = None
        self._fill_editor()
        self._paint()

    def _fill_editor(self) -> None:
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
        for code, (button, caption) in self.pads.items():
            binding = self.profile.bindings.get(code)
            caption.set_text("—" if binding is None else binding.summary())
            if code == self.selected:
                button.add_css_class("is-selected")
            else:
                button.remove_css_class("is-selected")
            if binding is None:
                button.remove_css_class("is-on")
            else:
                button.add_css_class("is-on")
        self._paint_others()
        self._paint_summary()
        self._paint_listen()
        if self._dirty():
            self.write_btn.add_css_class("suggested-action")
        else:
            self.write_btn.remove_css_class("suggested-action")

    def _paint_summary(self) -> None:
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

    def _pick_source(self) -> None:
        dialog = Adw.Dialog(title="Edit another key", content_width=360, content_height=480)
        search = Gtk.SearchEntry(placeholder_text="Search the keyboard")
        listing = Gtk.ListBox()
        listing.add_css_class("boxed-list")
        listing.set_selection_mode(Gtk.SelectionMode.NONE)
        listing.set_activate_on_single_click(True)

        def refill(query: str) -> None:
            while (row := listing.get_row_at_index(0)) is not None:
                listing.remove(row)
            needle = query.casefold().strip()
            for code, name in KEYBOARD_SOURCES:
                if needle and needle not in name.casefold():
                    continue
                label = Gtk.Label(label=name, xalign=0)
                label.set_margin_start(8)
                label.set_margin_top(4)
                label.set_margin_bottom(4)
                item = Gtk.ListBoxRow()
                item.set_child(label)
                item.code = code
                listing.append(item)

        def choose(_box, row) -> None:
            dialog.close()
            self._select(row.code)

        search.connect("search-changed", lambda entry: refill(entry.get_text()))
        listing.connect("row-activated", choose)
        refill("")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        scroll = Gtk.ScrolledWindow(vexpand=True, child=listing)
        box.append(search)
        box.append(scroll)
        dialog.set_child(box)
        dialog.present(self)

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
