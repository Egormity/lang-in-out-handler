"""Japanese character palettes, ordered left to right in five-column rows.

Each section is ``(title, rows)``. Empty strings are alignment gaps, never input
characters. Basic rows follow the a/i/u/e/o order; obsolete wi/we are omitted.
"""

type KanaRow = tuple[str, str, str, str, str]
type KanaSection = tuple[str, tuple[KanaRow, ...]]


KANA_SECTIONS: dict[str, tuple[KanaSection, ...]] = {
    "hiragana": (
        ("Basic", (
            ("あ", "い", "う", "え", "お"),
            ("か", "き", "く", "け", "こ"),
            ("さ", "し", "す", "せ", "そ"),
            ("た", "ち", "つ", "て", "と"),
            ("な", "に", "ぬ", "ね", "の"),
            ("は", "ひ", "ふ", "へ", "ほ"),
            ("ま", "み", "む", "め", "も"),
            ("や", "", "ゆ", "", "よ"),
            ("ら", "り", "る", "れ", "ろ"),
            ("わ", "", "", "", "を"),
            ("ん", "", "", "", ""),
        )),
        ("Voiced", (
            ("が", "ぎ", "ぐ", "げ", "ご"),
            ("ざ", "じ", "ず", "ぜ", "ぞ"),
            ("だ", "ぢ", "づ", "で", "ど"),
            ("ば", "び", "ぶ", "べ", "ぼ"),
            ("ぱ", "ぴ", "ぷ", "ぺ", "ぽ"),
            ("", "", "ゔ", "", ""),
        )),
        ("Small kana", (
            ("ぁ", "ぃ", "ぅ", "ぇ", "ぉ"),
            ("ゃ", "", "ゅ", "", "ょ"),
            ("", "", "っ", "", ""),
            ("ゎ", "", "", "", ""),
        )),
    ),
    "katakana": (
        ("Basic", (
            ("ア", "イ", "ウ", "エ", "オ"),
            ("カ", "キ", "ク", "ケ", "コ"),
            ("サ", "シ", "ス", "セ", "ソ"),
            ("タ", "チ", "ツ", "テ", "ト"),
            ("ナ", "ニ", "ヌ", "ネ", "ノ"),
            ("ハ", "ヒ", "フ", "ヘ", "ホ"),
            ("マ", "ミ", "ム", "メ", "モ"),
            ("ヤ", "", "ユ", "", "ヨ"),
            ("ラ", "リ", "ル", "レ", "ロ"),
            ("ワ", "", "", "", "ヲ"),
            ("ン", "", "", "", ""),
        )),
        ("Voiced", (
            ("ガ", "ギ", "グ", "ゲ", "ゴ"),
            ("ザ", "ジ", "ズ", "ゼ", "ゾ"),
            ("ダ", "ヂ", "ヅ", "デ", "ド"),
            ("バ", "ビ", "ブ", "ベ", "ボ"),
            ("パ", "ピ", "プ", "ペ", "ポ"),
            ("", "", "ヴ", "", ""),
        )),
        ("Small kana", (
            ("ァ", "ィ", "ゥ", "ェ", "ォ"),
            ("ャ", "", "ュ", "", "ョ"),
            ("", "", "ッ", "", ""),
            ("ヮ", "", "", "", ""),
            ("ヵ", "", "", "ヶ", ""),
        )),
    ),
}

# Shared by both scripts. The first item is the prolonged sound mark.
JAPANESE_PUNCTUATION: tuple[str, ...] = ("ー", "。", "、", "！", "？", "・", "「", "」")


def kana_characters(script: str) -> tuple[str, ...]:
    """Return nonblank characters in display order; unknown scripts raise KeyError."""
    return tuple(
        character
        for _, rows in KANA_SECTIONS[script]
        for row in rows
        for character in row
        if character
    )
