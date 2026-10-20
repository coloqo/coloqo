"""Public names: slugs, Assistants' words, random keys (decisions 0024, 0025)."""

import re
import secrets
import string

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
"""A slug: lowercase Latin letters, digits and inner hyphens, at most 40 characters."""

CYRILLIC = dict(
    zip(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюяєіїґ",
        (
            "a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o",
            "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e",
            "yu", "ya", "ye", "i", "yi", "g",
        ),
        strict=True,
    )
)  # fmt: skip
"""Transliteration of Cyrillic letters for slugs offered from names."""

WORDS = (
    # Bells and ringing.
    "chime", "peal", "carillon", "gong", "clapper", "belfry", "bourdon", "campana", "tenor",
    "treble", "handbell", "ringer",
    # Musical terms.
    "coda", "cadence", "tempo", "rondo", "sonata", "aria", "allegro", "adagio", "andante",
    "largo", "presto", "forte", "piano", "dolce", "legato", "staccato", "vivace", "scherzo",
    "etude", "motif", "chord", "octave", "timbre", "rhythm", "harmony", "melody", "prelude",
    "overture", "cantata", "minuet", "waltz", "bolero", "nocturne", "serenade", "ballad",
    "refrain", "chorus", "duet", "trio", "quartet", "encore", "crescendo", "fermata", "tremolo",
    "vibrato", "arpeggio", "toccata", "sonatina", "pizzicato", "glissando",
    # Stars.
    "vega", "lyra", "altair", "rigel", "deneb", "sirius", "polaris", "capella", "arcturus",
    "spica", "antares", "aldebaran", "procyon", "castor", "pollux", "regulus", "mira", "alcor",
    "mizar", "electra", "maia", "merope", "alcyone", "canopus", "achernar", "fomalhaut",
    "hadar", "mimosa", "shaula", "sadr", "nunki", "menkar", "alnitak", "alnilam", "mintaka",
    "saiph", "izar", "kochab", "thuban", "elnath", "hamal", "diphda", "enif", "markab",
    "alpheratz", "mirach", "almach", "acrux", "gacrux", "alioth", "dubhe", "merak", "phecda",
    "megrez", "bellatrix",
)  # fmt: skip
"""Words for Assistants' names: bells and ringing, musical terms, stars (decision 0024).

Words with a dark or ambiguous meaning are left out: knell, toll, requiem, dirge, lament, grave,
fugue (also a state of mind), canon (the team's canon), algol (the demon star), alkaid (the
chief of mourners)."""

KEY_ALPHABET = string.ascii_lowercase + string.digits


def new_key() -> str:
    """Return a random public key: a letter, then 11 lowercase letters and digits.

    The letter first keeps a key apart from the numeric ids plugin 0.4.0 sends.
    """
    return secrets.choice(string.ascii_lowercase) + "".join(
        secrets.choice(KEY_ALPHABET) for _ in range(11)
    )


def slugify(name: str, fallback: str = "team") -> str:
    """Return the slug offered from a name.

    Args:
        name: A Team's or an Area's name, in any script.
        fallback: The slug when nothing usable is left of the name.
    """
    text = "".join(CYRILLIC.get(char, char) for char in name.lower())
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40].strip("-")
    return text or fallback


def numbered(slug: str, taken: set[str]) -> str:
    """Return the slug, or ``slug-2``, ``slug-3`` ... when it is taken.

    Args:
        slug: The wished slug.
        taken: Slugs already in use.
    """
    if slug not in taken:
        return slug
    number = 2
    while True:
        suffix = f"-{number}"
        candidate = slug[: 40 - len(suffix)].rstrip("-") + suffix
        if candidate not in taken:
            return candidate
        number += 1


def pick_word(busy: set[str]) -> str:
    """Return a word for a new Assistant that no live Assistant of its project has.

    When every word is busy, a word gets a number: ``vega-2``.

    Args:
        busy: Words of the project's live Assistants.
    """
    free = [word for word in WORDS if word not in busy]
    if free:
        return secrets.choice(free)
    return numbered(secrets.choice(WORDS), busy)
