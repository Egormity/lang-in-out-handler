"""The Japanese palettes preserve Unicode characters and gojuon alignment."""

import unicodedata

import pytest

from lang_handler.kana import JAPANESE_PUNCTUATION, KANA_SECTIONS, kana_characters


@pytest.mark.parametrize("script, count", [("hiragana", 82), ("katakana", 84)])
def test_characters_are_unique_normalized_single_codepoints(script, count):
    characters = kana_characters(script)
    assert len(characters) == len(set(characters)) == count
    assert characters == kana_characters(script)
    assert all(len(character) == 1 for character in characters)
    assert all(unicodedata.normalize("NFC", character) == character for character in characters)
    assert all(unicodedata.name(character).startswith(script.upper()) for character in characters)


@pytest.mark.parametrize("script", KANA_SECTIONS)
def test_sections_keep_five_column_alignment_and_cover_common_compounds(script):
    sections = dict(KANA_SECTIONS[script])
    assert tuple(sections) == ("Basic", "Voiced", "Small kana")
    assert all(len(row) == 5 for rows in sections.values() for row in rows)
    basic = sections["Basic"]
    assert [bool(character) for character in basic[7]] == [True, False, True, False, True]
    assert [bool(character) for character in basic[9]] == [True, False, False, False, True]
    assert len([character for row in basic for character in row if character]) == 46
    examples = "きゃっぷぢづゔぃんゎ" if script == "hiragana" else "キャップヂヅヴィンヮヵヶ"
    assert set(examples) <= set(kana_characters(script))


def test_shared_punctuation_is_distinct_and_unknown_script_does_not_fall_back():
    assert set("ー。、！？・「」") == set(JAPANESE_PUNCTUATION)
    assert len(JAPANESE_PUNCTUATION) == len(set(JAPANESE_PUNCTUATION))
    assert not set(JAPANESE_PUNCTUATION) & set(kana_characters("hiragana"))
    assert not set(JAPANESE_PUNCTUATION) & set(kana_characters("katakana"))
    with pytest.raises(KeyError):
        kana_characters("unsupported")
