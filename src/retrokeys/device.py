"""Talk to a Retro Keyboard over its hidraw config interface."""

from __future__ import annotations

import os
import select
import time
from pathlib import Path

from .protocol import (
    Binding,
    Profile,
    ProfileError,
    assemble_macro,
    erase_packet,
    more_follows,
    parse_key,
    parse_key_list,
    parse_macro_body,
    parse_macro_name,
    parse_macro_sources,
    parse_name,
    plan_writes,
    quiet_packet,
    take_macro_piece,
)

VENDOR = "2dc8"
PRODUCTS = {"5200", "5209"}
REPORT = 33
OUT = 0x52
IN = 0x54


class KeyboardError(OSError):
    """The keyboard could not be opened or did not answer."""


def find_config_hidraw() -> str | None:
    """Return ``/dev/hidrawN`` for interface 2, or None."""
    root = Path("/sys/class/hidraw")
    if not root.is_dir():
        return None
    for node in sorted(root.iterdir()):
        device = node / "device"
        uevent_path = device / "uevent"
        if not uevent_path.is_file():
            continue
        try:
            uevent = uevent_path.read_text(errors="replace")
            real = os.path.realpath(device)
        except OSError:
            continue
        upper = uevent.upper()
        if VENDOR.upper() not in upper:
            continue
        if not any(product.upper() in upper for product in PRODUCTS):
            continue
        # .../9-2.3:1.2/0003:2DC8:5200.0017
        if ":1.2/" not in real and not real.endswith(":1.2"):
            continue
        return f"/dev/{node.name}"
    return None


class Keyboard:
    def __init__(self, path: str):
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as exc:
            raise KeyboardError(
                "The keyboard is plugged in, but this user cannot configure it. "
                "Enable programs.retro-keys, rebuild, and replug the cable."
            ) from exc
        except FileNotFoundError as exc:
            raise KeyboardError("The keyboard is not connected.") from exc
        self.path = path

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> Keyboard:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def _write(self, payload: bytes) -> None:
        if len(payload) > 32:
            raise ProfileError("A config packet is longer than 32 bytes.")
        packet = bytes((OUT,)) + payload + bytes(32 - len(payload))
        os.write(self.fd, packet)

    def _read(self, timeout: float) -> bytes | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.fd], [], [], min(0.05, deadline - time.monotonic()))
            if not ready:
                continue
            data = os.read(self.fd, 256)
            if len(data) >= 2 and data[0] == IN and data[1] == 0x8A:
                continue
            return data
        return None

    def _expect(self, kind: int, timeout: float = 1.0) -> bytes:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = self._read(deadline - time.monotonic())
            if data is None:
                break
            if len(data) >= 2 and data[0] == IN and data[1] == kind:
                if kind == 0xE4 and data[2] != 0x08:
                    raise KeyboardError(
                        f"The keyboard refused the update ({data[1]:02x} {data[2]:02x})."
                    )
                return data
        raise KeyboardError("The keyboard did not answer. Use the USB cable with the mode switch off.")

    def quiet(self) -> None:
        self._write(quiet_packet())
        self._expect(0xE4, timeout=0.6)

    def _collect(self, kind: int) -> list[bytes]:
        reports = [self._expect(kind)]
        while more_follows(reports[-1]):
            reports.append(self._expect(kind))
        return reports

    def load(self) -> Profile:
        try:
            self.quiet()
        except KeyboardError:
            pass
        name = parse_name(self._read_command(0x80))
        profile = Profile(name)
        sources: list[int] = []
        for report in self._read_pages(0x81):
            sources.extend(parse_key_list(report))
        for source in sources:
            self._write(bytes((0x83, source)))
            got, type_code, mod, usage = parse_key(self._expect(0x83))
            if got != source:
                raise KeyboardError("The keyboard returned a different key than requested.")
            if mod == 0 and usage == 0:
                continue
            kind = "key" if type_code == 0x07 else "opaque"
            profile.bindings[source] = Binding(
                kind=kind, mod=mod, usage=usage, type_code=type_code
            )
        macros: list[int] = []
        for report in self._read_pages(0x82):
            macros.extend(parse_macro_sources(report))
        for source in macros:
            self._write(bytes((0x84, source)))
            _src, macro_name = parse_macro_name(self._expect(0x84))
            pieces = self._read_macro(source)
            repeats, events = parse_macro_body(assemble_macro(pieces))
            profile.bindings[source] = Binding(
                kind="macro",
                macro_name=macro_name,
                repeats=repeats,
                events=events,
            )
        return profile

    def _read_command(self, command: int, arg: int | None = None) -> bytes:
        payload = bytes((command,)) if arg is None else bytes((command, arg))
        self._write(payload)
        return self._expect(command)

    def _read_pages(self, command: int) -> list[bytes]:
        self._write(bytes((command,)))
        return self._collect(command)

    def _read_macro(self, source: int) -> list[bytes]:
        self._write(bytes((0x86, source)))
        pieces: list[bytes] = []
        while True:
            report = self._expect(0x86)
            pieces.append(report)
            _source, _offset, more, _data = take_macro_piece(report)
            if more == 0:
                return pieces

    def save(self, old: Profile, new: Profile) -> Profile:
        ops = plan_writes(old, new)
        try:
            self.quiet()
        except KeyboardError:
            pass
        for payload, ack in ops:
            self._write(payload)
            if ack:
                self._expect(0xE4)
        return self.load()

    def erase(self) -> Profile:
        try:
            self.quiet()
        except KeyboardError:
            pass
        self._write(erase_packet())
        self._expect(0xE4)
        return self.load()


def open_keyboard() -> Keyboard:
    path = find_config_hidraw()
    if path is None:
        raise KeyboardError(
            "No Retro Keyboard is in wired mode. Plug in the USB cable and set the mode switch to off."
        )
    return Keyboard(path)
