"""Offline English end-rhyme checks using the bundled CMU pronunciation data.

Rhyme is the sound from the last stressed vowel (primary or secondary stress)
through the end of the word. Pronunciation variants are accepted; spelling
suffixes are never evidence of rhyme. A pronunciation with only unstressed
vowels uses its final vowel. The dictionary is US English, so accents, invented
words and unfamiliar slang may remain unverified.

Blank lines are ignored. Each bracketed heading starts a fresh section, even
when its name repeats. AABB checks adjacent pairs; AAAA checks blocks of four,
including a final chain of two or three. ABAB checks positions 1/3 and 2/4 in
each four-line block, only when both positions exist. Unpaired trailing lines
are free. Numbering in reports is the original text's one-based line number.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import unicodedata


RHYME_SCHEMES = ("AABB couplets", "ABAB alternating", "AAAA chains")
_SCHEMES = {scheme.split()[0]: scheme for scheme in RHYME_SCHEMES}
_DICT_PATH = Path(__file__).resolve().parent / "data" / "cmudict.dict"
_MAX_DICT_BYTES = 8 * 1024 * 1024
_HEADING = re.compile(r"^\[[^\[\]\r\n]+\]$")
_WORD = re.compile(r"'?[a-z0-9]+(?:['-][a-z0-9]+)*'?", re.ASCII)
_VOWELS = frozenset("AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW".split())
_CONSONANTS = frozenset("B CH D DH F G HH JH K L M N NG P R S SH T TH V W Y Z ZH".split())
_SIBILANTS = frozenset(("S", "Z", "SH", "ZH", "CH", "JH"))
_VOICELESS = frozenset(("P", "T", "K", "F", "TH"))


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.translate(str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u2010": "-", "\u2011": "-"}))
    value = "".join(c for c in value if unicodedata.category(c) != "Cf")
    value = unicodedata.normalize("NFKD", value)
    return "".join(c for c in value if not unicodedata.category(c).startswith("M"))


def _last_word(line: str) -> str:
    matches = _WORD.findall(_fold(line))
    return matches[-1] if matches else ""


def _valid_phone(phone: str) -> bool:
    return phone in _CONSONANTS or (len(phone) >= 2 and phone[-1] in "012" and phone[:-1] in _VOWELS)


@lru_cache(maxsize=1)
def _dictionary() -> dict[str, tuple[tuple[str, ...], ...]]:
    """Read a fixed local file once; bound input size and validate its records."""
    with _DICT_PATH.open("rb") as stream:
        raw = stream.read(_MAX_DICT_BYTES + 1)
    if len(raw) > _MAX_DICT_BYTES:
        raise ValueError("The bundled pronunciation dictionary is too large.")
    entries: dict[str, set[tuple[str, ...]]] = {}
    for line in raw.decode("utf-8").splitlines():
        if not line or len(line) > 1024 or line.startswith((";;;", "#")):
            continue
        fields = line.split("#", 1)[0].split()
        if len(fields) < 2 or len(fields) > 65:
            continue
        word = re.sub(r"\(\d+\)$", "", fields[0]).casefold()
        phones = tuple(fields[1:])
        if all(_valid_phone(phone) for phone in phones):
            entries.setdefault(word, set()).add(phones)
    if len(entries) < 10000:
        raise ValueError("The bundled pronunciation dictionary is incomplete.")
    return {word: tuple(sorted(variants)) for word, variants in entries.items()}


def _rhyme_tail(phones: tuple[str, ...]) -> tuple[str, ...] | None:
    stressed = [i for i, phone in enumerate(phones) if phone[-1:] in ("1", "2")]
    vowels = [i for i, phone in enumerate(phones) if phone[-1:] in ("0", "1", "2")]
    if not vowels:
        return None
    start = stressed[-1] if stressed else vowels[-1]
    return tuple(re.sub(r"[012]$", "", phone) for phone in phones[start:])


def _pronunciations(word: str, dictionary: dict) -> tuple[str, tuple[tuple[str, ...], ...]]:
    """Resolve quotes, final hyphen components, possessives and dropped-g -in'."""
    # A trailing apostrophe can be a closing quote. Preserve dropped-g endings
    # such as fightin' and singular/plural possessives where meaningful.
    candidate = word
    if candidate.endswith("'"):
        if candidate[:-1] in dictionary:
            candidate = candidate[:-1]
        elif not candidate.endswith("in'"):
            candidate = candidate.rstrip("'")
    if candidate in dictionary:
        return candidate, dictionary[candidate]
    if candidate.startswith("'") and candidate[1:] in dictionary:
        candidate = candidate[1:]
        return candidate, dictionary[candidate]
    if "-" in candidate:
        return _pronunciations(candidate.rsplit("-", 1)[-1], dictionary)
    if candidate.endswith("in'"):
        full_word = candidate[:-1] + "g"
        variants = dictionary.get(full_word, ())
        dropped = tuple(phones[:-1] + ("N",) for phones in variants if phones[-1:] == ("NG",))
        if dropped:
            return candidate, dropped
    if candidate.endswith("'s"):
        base = candidate[:-2]
        variants = dictionary.get(base, ())
        possessives = []
        for phones in variants:
            last = phones[-1]
            ending = ("IH0", "Z") if last in _SIBILANTS else (("S",) if last in _VOICELESS else ("Z",))
            possessives.append(phones + ending)
        if possessives:
            return candidate, tuple(possessives)
    return candidate, ()


def _sections(text: str) -> list[list[tuple[int, str]]]:
    sections: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if _HEADING.fullmatch(line):
            if current:
                sections.append(current)
            current = []
        else:
            current.append((number, _last_word(line)))
    if current:
        sections.append(current)
    return sections


def rhyme_report(text: str, scheme: str = "AABB couplets") -> dict:
    """Return JSON-safe rhyme groups, a score, unknown words and repair issues.

    ``match`` is boolean. ``status`` distinguishes matched, unmatched,
    unverified, repeated and missing groups. Unknown words are not declared
    nonrhyming. ``pairs`` and ``groups`` contain the same group records (AAAA
    records can have up to four lines). Only formed groups contribute to the
    score. Every formed group must match for ``rhyme_issues`` to return empty.
    """
    groups: list[dict] = []
    issues: list[str] = []
    report = {"matched_groups": 0, "total_groups": 0, "unknown_words": [],
              "issues": issues, "pairs": groups, "groups": groups,
              "ungrouped_lines": [], "score": None}
    key = str(scheme).strip().upper().split(" ", 1)[0]
    if key not in _SCHEMES:
        issues.append("Choose AABB couplets, ABAB alternating or AAAA chains for end-rhyme checks.")
        return report
    report["scheme"] = _SCHEMES[key]
    sections = _sections(text)
    if not sections:
        issues.append("Add lyric lines to check their ending words.")
        return report
    try:
        dictionary = _dictionary()
    except (OSError, UnicodeError, ValueError):
        issues.append("End rhymes could not be verified. Restore data/cmudict.dict beside Hardstyle Writer and try again.")
        return report

    endings: dict[int, dict] = {}
    unknown: set[str] = set()
    for section in sections:
        for number, word in section:
            identity, variants = _pronunciations(word, dictionary)
            tails = {tail for phones in variants if (tail := _rhyme_tail(phones)) is not None}
            endings[number] = {"word": word, "identity": identity, "tails": tails}
            if not word:
                issues.append(f"Line {number} has no ending word. Write a lyric line with a pronounceable final word.")
            elif not tails:
                unknown.add(word)
    report["unknown_words"] = sorted(unknown)

    blocks: list[list[tuple[int, str]]] = []
    for section in sections:
        step = 2 if key == "AABB" else 4
        for offset in range(0, len(section), step):
            block = section[offset:offset + step]
            proposed = (block[::2], block[1::2]) if key == "ABAB" else (block,)
            for group in proposed:
                if len(group) >= 2:
                    blocks.append(group)
                else:
                    report["ungrouped_lines"].extend(number for number, _ in group)

    for block in blocks:
        numbers = [number for number, _ in block]
        items = [endings[number] for number in numbers]
        words = [item["word"] for item in items]
        identities = [item["identity"] for item in items]
        missing = any(not word for word in words)
        unverified = [item["word"] for item in items if item["word"] and not item["tails"]]
        repeated = len(set(identities)) != len(identities)
        shared = set.intersection(*(item["tails"] for item in items))
        match = bool(shared) and not repeated and not missing
        status = "matched" if match else ("missing" if missing else "unverified" if unverified else "repeated" if repeated else "unmatched")
        record = {"line_numbers": numbers, "end_words": words, "match": match, "status": status}
        groups.append(record)
        label = " / ".join(str(number) for number in numbers)
        displayed = " / ".join(word or "(no word)" for word in words)
        if status == "unverified":
            unknown_display = ", ".join(dict.fromkeys(unverified))
            issues.append(f"Lines {label}: end rhyme is unverified for {unknown_display}. Replace the ending with a familiar English word that rhymes with the other line endings ({displayed}).")
        elif status == "repeated":
            issues.append(f"Lines {label}: repeated ending words ({displayed}) do not count as rhyme. Use different words with the same ending sound.")
        elif status == "unmatched":
            issues.append(f"Lines {label}: ending words ({displayed}) do not share a stressed-vowel rhyme. Change the endings to different words with the same ending sound.")
    report["matched_groups"] = sum(group["match"] for group in groups)
    report["total_groups"] = len(groups)
    if groups:
        report["score"] = round(100 * report["matched_groups"] / len(groups))
    return report


def rhyme_issues(text: str, scheme: str = "AABB couplets") -> list[str]:
    """Return strict, actionable failures for every complete rhyme group."""
    return rhyme_report(text, scheme)["issues"]
