"""Retro Keys command line. ``dump`` skips the window and prints the profile."""

from __future__ import annotations

import sys

from .keys import source_title


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "dump":
        from .device import KeyboardError, open_keyboard

        try:
            with open_keyboard() as keyboard:
                profile = keyboard.load()
        except KeyboardError as exc:
            print(exc, file=sys.stderr)
            return 1
        print(f"Profile: {profile.name or '(none)'}")
        if not profile.bindings:
            print("No keys are mapped.")
            return 0
        for code, binding in sorted(profile.bindings.items()):
            print(f"  {source_title(code)}: {binding.summary()}")
        return 0

    from .app import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
