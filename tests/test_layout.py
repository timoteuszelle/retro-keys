"""The on-screen keyboard and the colour editions. These tests do not open the device."""

import tempfile
import unittest
from pathlib import Path

from retrokeys.keys import JACKS
from retrokeys.layout import (
    ROWS,
    WIDTH_QU,
    board_key_for_usage,
    board_keys,
    column_of,
    expected_board_codes,
    layout_codes,
    search_hits,
)
from retrokeys.theme import EDITIONS, edition_by_id, load_edition_id, save_edition_id


class LayoutTests(unittest.TestCase):
    def test_every_row_is_one_tkl_width(self):
        for row in ROWS:
            self.assertEqual(sum(cell.span for cell in row), WIDTH_QU)

    def test_board_is_the_keyboard_keys_once(self):
        codes = [cell.code for cell in board_keys()]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(set(codes), expected_board_codes())

    def test_jacks_are_not_drawn_as_keys(self):
        drawn = layout_codes()
        for _jack, button_a, button_b, _primary in JACKS:
            self.assertNotIn(button_a, drawn)
            self.assertNotIn(button_b, drawn)

    def test_up_shares_the_down_column(self):
        self.assertEqual(column_of(0x52), column_of(0x51))
        self.assertEqual(column_of(0x50) + 4, column_of(0x51))
        self.assertEqual(column_of(0x51) + 4, column_of(0x4F))
        self.assertEqual(column_of(0x49), column_of(0x50))
        self.assertEqual(column_of(0x4A), column_of(0x52))
        self.assertEqual(column_of(0x4B), column_of(0x4F))

    def test_a_chosen_usage_maps_to_the_cap_that_sends_it(self):
        self.assertEqual(board_key_for_usage(0x04), 0x04)
        self.assertEqual(board_key_for_usage(0x52), 0x52)
        self.assertEqual(board_key_for_usage(0xE1), 0x65)
        self.assertEqual(board_key_for_usage(0xE4), 0x68)
        self.assertIsNone(board_key_for_usage(0xE7))
        self.assertIsNone(board_key_for_usage(0x68))
        self.assertIsNone(board_key_for_usage(0x65))
        self.assertIsNone(board_key_for_usage(0))

    def test_search_finds_a_key_and_a_jack(self):
        self.assertEqual(search_hits(""), [])
        self.assertEqual(search_hits("   "), [])
        self.assertEqual(search_hits("esc"), [0x29])
        self.assertEqual(search_hits("super a"), [0x6D])
        self.assertEqual(search_hits("jack x"), [0x70, 0x71])
        self.assertIn(0x04, search_hits("a"))
        self.assertIn(0x6D, search_hits("a"))


class ThemeTests(unittest.TestCase):
    def test_editions_share_the_tkl_layout_and_fill_every_colour(self):
        ids = [edition.id for edition in EDITIONS]
        self.assertEqual(len(ids), len(set(ids)))
        accents = set()
        for edition in EDITIONS:
            self.assertEqual(edition.layout, "tkl")
            css = edition.palette.css()
            self.assertNotIn("@", css)
            self.assertIn(edition.palette.accent, css)
            self.assertIn(edition.palette.selection, css)
            self.assertIn("button.kb.super-a", css)
            self.assertIn("button.kb.is-target", css)
            self.assertIn(".editor.is-inactive", css)
            self.assertIn(".editor-controls", css)
            accents.add(edition.palette.accent)
        self.assertGreater(len(accents), 1)
        self.assertEqual(edition_by_id("missing").id, "fami")
        xbox = edition_by_id("xbox")
        self.assertEqual(xbox.layout, "tkl")
        self.assertIn("button.kb.up", xbox.extra_css)
        self.assertIn("button.kb.right", xbox.extra_css)
        self.assertEqual(edition_by_id("fami").extra_css, "")

    def test_edition_choice_is_remembered(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(load_edition_id(home), "fami")
            save_edition_id("n", home)
            self.assertEqual(load_edition_id(home), "n")
            save_edition_id("not-a-keyboard", home)
            self.assertEqual(load_edition_id(home), "n")
            (home / "retro-keys" / "edition").write_text("nope\n", encoding="utf-8")
            self.assertEqual(load_edition_id(home), "fami")
