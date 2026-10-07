"""Packet tests against captures from a Famicom-edition Retro Keyboard."""

import unittest

from retrokeys.keys import hid_from_keycode
from retrokeys.protocol import (
    Binding,
    MacroEvent,
    Profile,
    ProfileError,
    assemble_macro,
    encode_text,
    key_packet,
    macro_body,
    macro_body_packets,
    name_packet,
    parse_key,
    parse_key_list,
    parse_macro_body,
    parse_macro_name,
    parse_macro_sources,
    parse_name,
    plan_writes,
)


# 12 delays, 10 ms through 21 ms, repeat twice. Split across two reports.
MACRO_PAGES = [
    bytes.fromhex(
        "5486700100001a0102000c0f0a000f0b000f0c000f0d000f0e000f0f000f10000f"
    ),
    bytes.fromhex(
        "548670001a000e11000f12000f13000f14000f1500000000000000000000000000"
    ),
]


class ProtocolTests(unittest.TestCase):
    def test_name_round_trip_matches_the_keyboard(self):
        packet = name_packet("AΩ")
        self.assertEqual(packet.hex(), "700400004103a9")
        report = bytes.fromhex("54800400004103a900")
        self.assertEqual(parse_name(report), "AΩ")

        spaced = name_packet("a b")
        self.assertEqual(spaced[:3].hex(), "700600")
        self.assertEqual(spaced[3:], "a b".encode("utf-16-be"))
        self.assertEqual(encode_text("a b"), bytes.fromhex("006100200062"))

    def test_empty_name_is_not_a_normal_write(self):
        with self.assertRaises(ProfileError):
            name_packet("")

    def test_key_map_packet(self):
        # Jack X button B (source 0x71) → Enter (usage 0x28), no modifier.
        self.assertEqual(
            key_packet(0x71, 0, 0x28).hex(),
            "fa030c00aa097171070028",
        )
        source, type_code, mod, usage = parse_key(bytes.fromhex("54837107002800"))
        self.assertEqual((source, type_code, mod, usage), (0x71, 0x07, 0x00, 0x28))

    def test_key_list_stops_at_zero(self):
        report = bytes.fromhex("5481710700" + "00" * 28)
        self.assertEqual(len(report), 33)
        self.assertEqual(parse_key_list(report), [0x71])

    def test_macro_capture_reassembles(self):
        self.assertEqual(parse_macro_sources(bytes.fromhex("548270280008" + "00" * 26)), [0x70])
        source, macro_name = parse_macro_name(bytes.fromhex("54847504000067006f"))
        self.assertEqual((source, macro_name), (0x75, "go"))

        events = tuple(MacroEvent(0x0F, 10 + i) for i in range(12))
        body = macro_body(2, events)
        self.assertEqual(assemble_macro(MACRO_PAGES), body)
        repeats, parsed = parse_macro_body(body)
        self.assertEqual(repeats, 2)
        self.assertEqual(parsed, events)

        packets = macro_body_packets(0x70, body)
        self.assertEqual([len(payload) - 6 for payload, _ack in packets], [26, 14])
        self.assertEqual([ack for _payload, ack in packets], [False, True])
        self.assertEqual(packets[0][0][:6].hex(), "76700100001a")
        self.assertEqual(packets[1][0][:6].hex(), "7670001a000e")

    def test_plan_refuses_to_erase_and_skips_unchanged(self):
        old = Profile("retro", {0x70: Binding("key", usage=0x28)})
        with self.assertRaises(ProfileError):
            plan_writes(old, Profile("", dict(old.bindings)))
        self.assertEqual(plan_writes(old, old.clone()), [])

    def test_plan_maps_a_pad_button_and_a_macro(self):
        old = Profile("retro")
        new = old.clone()
        new.bindings[0x70] = Binding("key", usage=0x68)  # F13
        new.bindings[0x71] = Binding(
            "macro",
            macro_name="go",
            repeats=1,
            events=(
                MacroEvent(0x83, 0xE0),
                MacroEvent(0x81, 0x0B),
                MacroEvent(0x01, 0x0B),
                MacroEvent(0x03, 0xE0),
            ),
        )
        ops = plan_writes(old, new)
        payloads = [payload for payload, _ack in ops]
        self.assertEqual(payloads[0][:4].hex(), "fa030c00")
        self.assertEqual(payloads[0][7:11].hex(), "70070068")
        self.assertEqual(payloads[1][0], 0x74)
        self.assertEqual(payloads[-1][7:11].hex(), "71070000")
        self.assertTrue(any(payload[0] == 0x76 for payload in payloads))

    def test_clearing_a_key_disables_it(self):
        old = Profile("retro", {0x70: Binding("key", usage=0x68)})
        ops = plan_writes(old, Profile("retro"))
        self.assertEqual(ops, [(bytes.fromhex("fa030c00aa097170070000"), True)])

    def test_clearing_a_macro_deletes_it(self):
        old = Profile(
            "retro",
            {0x75: Binding("macro", macro_name="go", events=(MacroEvent(0x81, 4),))},
        )
        ops = plan_writes(old, Profile("retro"))
        self.assertEqual(ops, [(bytes((0x77, 0x75, 0x8C)), True)])

    def test_keycode_map_knows_letters_and_x11_offset(self):
        self.assertEqual(hid_from_keycode(30), 0x04)  # evdev A
        self.assertEqual(hid_from_keycode(38), 0x0F)  # evdev L
        self.assertEqual(hid_from_keycode(29), 0xE0)  # left ctrl
        self.assertEqual(hid_from_keycode(38 + 8, x11=True), 0x0F)


if __name__ == "__main__":
    unittest.main()
