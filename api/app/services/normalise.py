"""Ingredient alias matching and normalization service.

Matches detected ingredient names from vision output to canonical ingredient IDs
per PRD Section 8.4 and FR-025:
- Case-insensitive
- Ignores punctuation and plural 's'
- Exact matches against canonical IDs, display names, and aliases
- Fuzzy match fallback (Levenshtein distance <= 2 on names of 5+ characters)
- Unmapped names return canonical_id: None
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("fridgechef.normalise")


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


class AliasMatcher:
    """Normalizes and matches raw ingredient names to canonical ingredients."""

    def __init__(self, ingredients_data: list[dict[str, Any]] | None = None) -> None:
        self.exact_map: dict[str, tuple[str, str]] = {}
        self.canonical_names: dict[str, str] = {}
        self.fuzzy_candidates: list[tuple[str, str, str]] = []  # (normalized_alias, canonical_id, display_name)

        if ingredients_data is None:
            ingredients_data = self._load_default_ingredients()

        self._build_indexes(ingredients_data)

    def _load_default_ingredients(self) -> list[dict[str, Any]]:
        """Load ingredients from data/ingredients.json."""
        current_dir = Path(__file__).resolve().parent
        # Try api/data/ingredients.json or ../data/ingredients.json
        possible_paths = [
            current_dir.parent.parent / "data" / "ingredients.json",
            current_dir.parent / "data" / "ingredients.json",
            Path("data/ingredients.json").resolve(),
        ]
        for p in possible_paths:
            if p.exists():
                try:
                    with open(p, encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            return data
                except Exception as exc:
                    logger.warning(f"Failed to read {p}: {exc}")

        logger.error("Could not find ingredients.json for AliasMatcher.")
        return []

    def _clean_text(self, text: str) -> str:
        """Lowercase, remove punctuation, and collapse whitespace."""
        if not text:
            return ""
        # Remove punctuation
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    def _stem_plural(self, word: str) -> str:
        """Strip English plural suffix if word length allows."""
        if len(word) > 4 and word.endswith("es"):
            # e.g., tomatoes -> tomato, potatoes -> potato
            if word.endswith(("toes", "soes")):
                return word[:-2]
            return word[:-2]
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
        return word

    def _normalize_string(self, text: str) -> str:
        """Clean and normalize a phrase, applying plural stemming to each word."""
        cleaned = self._clean_text(text)
        words = cleaned.split()
        stemmed_words = [self._stem_plural(w) for w in words]
        return " ".join(stemmed_words)

    def _build_indexes(self, ingredients: list[dict[str, Any]]) -> None:
        """Index canonical IDs, display names, and aliases."""
        for item in ingredients:
            raw_id = item.get("id")
            if not raw_id:
                continue
            canonical_id = str(raw_id)
            display_name = str(item.get("display_name") or canonical_id)

            self.canonical_names[canonical_id] = display_name

            # Collect all representations
            representations: list[str] = [canonical_id, display_name]
            raw_aliases = item.get("aliases") or []
            if isinstance(raw_aliases, list):
                representations.extend([str(a) for a in raw_aliases if a])

            for rep in representations:
                raw_cleaned = self._clean_text(rep)
                stemmed = self._normalize_string(rep)

                if raw_cleaned:
                    self.exact_map[raw_cleaned] = (canonical_id, display_name)
                    self.fuzzy_candidates.append((raw_cleaned, canonical_id, display_name))
                if stemmed and stemmed != raw_cleaned:
                    self.exact_map[stemmed] = (canonical_id, display_name)
                    self.fuzzy_candidates.append((stemmed, canonical_id, display_name))

    def match(self, raw_name: str) -> tuple[str | None, str | None]:
        """Match a detected ingredient name to a canonical ingredient.

        Returns (canonical_id, display_name) or (None, None).
        """
        if not raw_name or not raw_name.strip():
            return None, None

        cleaned = self._clean_text(raw_name)
        if not cleaned:
            return None, None

        # 1. Exact match on cleaned string
        if cleaned in self.exact_map:
            return self.exact_map[cleaned]

        # 2. Exact match on stemmed/normalized string
        stemmed = self._normalize_string(raw_name)
        if stemmed in self.exact_map:
            return self.exact_map[stemmed]

        # 3. Fuzzy matching (Levenshtein distance <= 2 on names of 5+ characters)
        # Check both cleaned and stemmed forms
        target_name = stemmed if len(stemmed) >= 5 else cleaned
        if len(target_name) >= 5:
            best_match: tuple[str, str] | None = None
            best_dist = 3  # We only accept <= 2

            for candidate_str, c_id, c_name in self.fuzzy_candidates:
                # Skip candidate if length difference is greater than max allowed distance
                if abs(len(candidate_str) - len(target_name)) > 2:
                    continue

                dist = levenshtein_distance(target_name, candidate_str)
                if dist < best_dist:
                    best_dist = dist
                    best_match = (c_id, c_name)
                    if dist == 1:
                        # Distance 1 is already very strong
                        pass

            if best_match is not None and best_dist <= 2:
                logger.debug(
                    f"Fuzzy matched '{raw_name}' (as '{target_name}') to '{best_match[0]}' with distance {best_dist}"
                )
                return best_match

        # 4. Unmapped
        return None, None


# Global singleton instance for easy import
alias_matcher = AliasMatcher()
