import random

from userbot.humanize import add_typos, clean_formatting, humanize


def test_clean_formatting_strips_markdown_and_em_dashes():
    text = "# Hey\n**bold** and *italic* — plus `code`\n- one\n2. two"

    assert clean_formatting(text) == "Hey\nbold and italic, plus code\none\ntwo"


def test_clean_formatting_keeps_normal_text():
    assert clean_formatting("hey, 30% + 6% of sales. ok?") == "hey, 30% + 6% of sales. ok?"


def test_no_typos_at_rate_zero():
    text = "sounds good, can you send a couple of photos"

    assert add_typos(text, 0.0, random.Random(1)) == text


def test_every_plain_word_gets_one_typo_at_rate_one():
    original = "sounds good, photos please"
    result = add_typos(original, 1.0, random.Random(3))

    for before, after in zip(original.split(), result.split(), strict=True):
        if len(before.strip(",")) >= 4:
            assert after != before
            assert after[0] == before[0]  # first letter kept
            assert abs(len(after) - len(before)) <= 1
        else:
            assert after == before  # short words are left alone


def test_urls_mentions_numbers_and_prices_are_never_changed():
    text = "https://drive.google.com/folder @someusername $300 2x 25 photos/videos"

    assert add_typos(text, 1.0, random.Random(5)) == text


def test_typos_are_reproducible_with_a_seed():
    text = "thanks for reaching out, how many models are you looking to promote"

    assert add_typos(text, 0.3, random.Random(7)) == add_typos(text, 0.3, random.Random(7))


def test_humanize_cleans_then_adds_typos():
    assert humanize("**hey** there", 0.0) == "hey there"
