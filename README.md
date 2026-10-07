# Retro Keys

A Linux configurator for the 8BitDo Retro Keyboard, including the Dual Super Buttons that plug into the jacks on the back.

It writes the same kind of profile as Ultimate Software V2: one key, a modifier plus a key, or a macro with timing. The profile is stored on the keyboard. Mappings apply while the heart light is on.

## What you need

Use the USB cable with the mode switch set to off. That is wired mode. The 2.4 GHz receiver and Bluetooth do not accept configuration.

A single Dual Super Buttons pad is recognized in the X jack. The keyboard can take a pad on each of A, B, X, and Y.

Retro Keys does not flash firmware, and it does not unbind the keyboard driver, so the keys keep working while it is open.

## Run it

```sh
nix run /home/tim/personal-git/retro-keys
```

`retro-keys dump` prints the profile currently stored on the keyboard.

Give the profile a name, map the buttons, then press **Write to keyboard**. Press the heart button so its light is on. An empty name is refused: on this keyboard that packet erases every mapping. Use **Erase profile on keyboard** in the menu when you actually want that.

Fast mapping with the star button is separate. It copies one key until the keyboard loses power, and Retro Keys does not change those temporary copies.

## NixOS

Add the flake and enable the module. Enabling it installs `retro-keys` and a udev rule so your user can open the config interface. The rule matches USB `2dc8:5200` and `2dc8:5209`, interface 2 only.

```nix
inputs.retro-keys.url = "path:/home/tim/personal-git/retro-keys";
```

```nix
imports = [ inputs.retro-keys.nixosModules.default ];
programs.retro-keys.enable = true;
```

Rebuild, then unplug the keyboard and plug it back in. Until that rule is installed, the config device may only be openable as root.

## Tests

```sh
cd /home/tim/personal-git/retro-keys
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The tests check the packet format. They do not open the keyboard.

## Before a public release

The window still needs a small interface pass. A public release also needs packages for NixOS and for general Linux: Debian, Ubuntu, Fedora, and RHEL.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
