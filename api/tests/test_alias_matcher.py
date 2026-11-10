"""Unit tests for the ingredient alias matching and normalization service

per PRD Section 8.4 and FR-025.
"""

from app.services.normalise import AliasMatcher, alias_matcher, levenshtein_distance


def test_levenshtein_distance():
    """Verify Levenshtein distance calculations."""
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("potato", "potatos") == 1
    assert levenshtein_distance("same", "same") == 0
    assert levenshtein_distance("", "test") == 4
    assert levenshtein_distance("test", "") == 4


def test_exact_canonical_match():
    """Verify exact matching on canonical IDs and display names."""
    c_id, name = alias_matcher.match("tomato")
    assert c_id == "tomato"
    assert name == "Tomato"

    c_id, name = alias_matcher.match("Potato")
    assert c_id == "potato"
    assert name == "Potato"

    c_id, name = alias_matcher.match("onion")
    assert c_id == "onion"


def test_case_insensitivity():
    """Verify case-insensitivity across uppercase, mixed case, and lowercase."""
    c_id, _ = alias_matcher.match("TOMATO")
    assert c_id == "tomato"

    c_id, _ = alias_matcher.match("pOtAtO")
    assert c_id == "potato"

    c_id, _ = alias_matcher.match("CaPsIcUm")
    assert c_id == "capsicum"


def test_punctuation_ignoring():
    """Verify punctuation (hyphens, commas, exclamation marks) is ignored."""
    c_id, _ = alias_matcher.match("bell-pepper")
    assert c_id == "capsicum"

    c_id, _ = alias_matcher.match("lady-finger")
    assert c_id == "okra"

    c_id, _ = alias_matcher.match("(capsicum)!")
    assert c_id == "capsicum"


def test_plural_handling():
    """Verify plurals ending in 's' or 'es' are normalized to their singular form."""
    c_id, _ = alias_matcher.match("tomatoes")
    assert c_id == "tomato"

    c_id, _ = alias_matcher.match("potatoes")
    assert c_id == "potato"

    c_id, _ = alias_matcher.match("onions")
    assert c_id == "onion"

    c_id, _ = alias_matcher.match("capsicums")
    assert c_id == "capsicum"


def test_regional_and_hindi_aliases():
    """Verify common Indian English and Hindi aliases map to canonical IDs."""
    # Aloo -> Potato
    c_id, _ = alias_matcher.match("aloo")
    assert c_id == "potato"

    # Tamatar -> Tomato
    c_id, _ = alias_matcher.match("tamatar")
    assert c_id == "tomato"

    # Pyaaz -> Onion
    c_id, _ = alias_matcher.match("pyaaz")
    assert c_id == "onion"

    # Bhindi -> Lady finger / Okra
    c_id, _ = alias_matcher.match("bhindi")
    assert c_id == "okra"

    # Shimla Mirch -> Capsicum
    c_id, _ = alias_matcher.match("shimla mirch")
    assert c_id == "capsicum"

    # Dahi -> Curd / Yogurt
    c_id, _ = alias_matcher.match("dahi")
    assert c_id == "curd"


def test_fuzzy_matching_fallback():
    """Verify fuzzy matching fallback (Levenshtein distance <= 2 on names 5+ chars)."""
    # "potatos" (distance 1 to potato)
    c_id, _ = alias_matcher.match("potatos")
    assert c_id == "potato"

    # "spinch" (distance 1 to spinach)
    c_id, _ = alias_matcher.match("spinch")
    assert c_id == "spinach"

    # "tomto" (distance 1 to tomato)
    c_id, _ = alias_matcher.match("tomto")
    assert c_id == "tomato"


def test_unmapped_names_rejection():
    """Verify unknown or unrecognized names return canonical_id: None per FR-025."""
    c_id, name = alias_matcher.match("Unrecognized Alien Fruit")
    assert c_id is None
    assert name is None

    c_id, name = alias_matcher.match("random_unknown_item_99")
    assert c_id is None
    assert name is None

    # Empty and whitespace
    c_id, name = alias_matcher.match("")
    assert c_id is None
    assert name is None

    c_id, name = alias_matcher.match("   ")
    assert c_id is None
    assert name is None


def test_custom_matcher_isolated():
    """Verify AliasMatcher behavior with custom isolated dataset."""
    custom_data = [
        {
            "id": "paneer",
            "display_name": "Paneer",
            "aliases": ["cottage cheese", "chenna"],
        }
    ]
    matcher = AliasMatcher(ingredients_data=custom_data)

    assert matcher.match("paneer")[0] == "paneer"
    assert matcher.match("cottage cheese")[0] == "paneer"
    assert matcher.match("chenna")[0] == "paneer"
    assert matcher.match("tofu")[0] is None
