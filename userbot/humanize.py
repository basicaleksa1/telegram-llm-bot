"""Makes AI replies read like someone typing on a phone.

Small models are bad at making believable typos on purpose and like to slip
into markdown, so both are handled here in code instead of in the prompt.
"""

import random
import re

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.MULTILINE)
_EMPHASIS = re.compile(r"(\*\*|__|\*|`)(.+?)\1", re.DOTALL)
_EM_DASH = re.compile(r"\s*[—–]\s*")
_TOKEN = re.compile(r"\S+")
# A plain word of 4+ letters, optionally followed by punctuation like "," or "?".
_PLAIN_WORD = re.compile(r"([^\W\d_]{4,})(\W*)")


def clean_formatting(text: str) -> str:
    """Strip markdown headings, bullets, bold/italic/code markers and em dashes."""
    text = _HEADING.sub("", text)
    text = _BULLET.sub("", text)
    text = _EMPHASIS.sub(r"\2", text)
    text = text.replace("`", "")
    text = _EM_DASH.sub(", ", text)
    return text.strip()


def add_typos(text: str, rate: float, rng: random.Random | None = None) -> str:
    """Give roughly `rate` of the words one small typo: two letters swapped, one dropped or one doubled."""
    if rate <= 0:
        return text
    rng = rng or random.Random()

    def typo(match: re.Match[str]) -> str:
        token = match.group()
        # Only plain words: never URLs, @mentions, numbers or prices.
        word = _PLAIN_WORD.fullmatch(token)
        if word is None or rng.random() >= rate:
            return token
        letters, tail = word.groups()
        # Keep the first and last letter so the word stays readable.
        kind = rng.choice(("swap", "drop", "double"))
        i = rng.randrange(1, len(letters) - (2 if kind == "swap" else 1))
        if kind == "swap":
            letters = letters[:i] + letters[i + 1] + letters[i] + letters[i + 2 :]
        elif kind == "drop":
            letters = letters[:i] + letters[i + 1 :]
        else:
            letters = letters[:i] + letters[i] + letters[i:]
        return letters + tail

    return _TOKEN.sub(typo, text)


def humanize(text: str, typo_rate: float, rng: random.Random | None = None) -> str:
    return add_typos(clean_formatting(text), typo_rate, rng)
