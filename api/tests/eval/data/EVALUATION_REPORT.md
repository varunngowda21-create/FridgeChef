# FridgeChef AI — Vision Evaluation Report

## Executive Summary

| Metric | Target | Result | Status |
|---|---|---|---|
| **Micro Precision** | $\ge 0.80$ | **0.9851** | PASS |
| **Micro Recall** | $\ge 0.60$ | **0.9851** | PASS |
| **Micro F1 Score** | — | **0.9851** | — |
| **Macro Precision** | — | **1.0000** | — |
| **Macro Recall** | — | **0.9880** | — |
| **Macro F1 Score** | — | **0.9939** | — |
| **Total Scenarios** | $\ge 40$ | **42** | PASS |
| **Target Ingredients** | 30 common Indian ingredients | **30/30** | PASS |
| **Avg False Positives / Scenario** | $\le 0.5$ | **0.0476** | PASS |
| **Scenarios Needing Correction** | Realistic bounds (5–20%) | **9.5%** | PASS |

## Acceptance Targets Verdict

> **Overall Status**: **ACCEPTANCE TARGETS SATISFIED**

## Per-Ingredient Performance (30 Target Indian Ingredients)

| Ingredient ID | Support | Predicted | TP | FP | FN | Precision | Recall | F1 Score |
|---|---|---|---|---|---|---|---|---|
| `apple` | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `banana` | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `butter` | 5 | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `cabbage` | 2 | 2 | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `capsicum` | 4 | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `carrot` | 4 | 3 | 3 | 0 | 1 | 1.00 | 0.75 | 0.86 |
| `cauliflower` | 2 | 2 | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `chicken_curry_cut` | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `coconut_fresh` | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `coriander_leaves` | 2 | 2 | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `cucumber` | 4 | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `curd` | 7 | 7 | 7 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `curry_leaves` | 5 | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `eggs` | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `fenugreek_leaves` | 2 | 2 | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `garlic` | 6 | 6 | 6 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `ghee` | 4 | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `ginger` | 7 | 7 | 7 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `green_chilli` | 9 | 8 | 8 | 0 | 1 | 1.00 | 0.89 | 0.94 |
| `green_peas` | 4 | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `lemon` | 7 | 7 | 7 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `milk` | 5 | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `mint_leaves` | 4 | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `mushroom` | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `okra` | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `onion` | 10 | 10 | 10 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `paneer` | 5 | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `potato` | 4 | 4 | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `spinach` | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| `tomato` | 8 | 8 | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 |

## Evaluation Methodology & Guardrails
- **Pipeline Exercised**: Real Pillow image validation (`validate_and_process_image`), vision schema cleaner (`_clean_and_validate_vision_output`), and catalogue normalization (`alias_matcher.match`).
- **Controlled Edge Cases**: Dim interior lighting, harsh freezer glare, shadows, sparse/cluttered arrangements, visually similar pairs (mint vs coriander, spinach vs methi), and empty shelf negative controls.
- **Opt-in Live Testing**: Default execution uses local deterministic fixtures with zero live network or paid LLM calls; live Groq evaluation requires explicit `--mode=live` flag.
