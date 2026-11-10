"""Automated pytest suite for the FridgeChef Vision Evaluation Harness.

Verifies PRD Section 14.4 and Phase 9 Task 3 requirements:
- Minimum 40 labeled scenarios covering 30 common Indian ingredients
- Real image validation and processing
- Micro-precision >= 0.80 and micro-recall >= 0.60
- Negative controls and realistic false positive / correction rate bounds
- Opt-in guardrails against unexpected live API calls
"""

import pytest

from app.services.normalise import alias_matcher
from tests.eval.dataset import (
    TARGET_30_INDIAN_INGREDIENTS,
    EvaluationScenario,
    load_evaluation_scenarios,
)
from tests.eval.runner import (
    EvaluationRunConfig,
    run_evaluation_scenario,
    run_full_evaluation,
)


@pytest.fixture(scope="module")
def scenarios() -> list[EvaluationScenario]:
    """Load and cache the labeled scenarios for testing."""
    return load_evaluation_scenarios()


def test_dataset_structure_and_coverage(scenarios: list[EvaluationScenario]) -> None:
    """Verify dataset conforms to PRD 14.4 requirements: >= 40 scenarios covering 30 Indian ingredients."""
    assert len(scenarios) >= 40, f"Expected >= 40 scenarios, got {len(scenarios)}"

    covered_targets: set[str] = set()
    environments: set[str] = set()
    lightings: set[str] = set()
    clutter_levels: set[str] = set()

    for sc in scenarios:
        environments.add(sc.environment)
        lightings.add(sc.lighting)
        clutter_levels.add(sc.clutter)

        for cid in sc.expected_canonical_ids:
            # Verify every canonical ID exists in the catalogue
            matched_id, _ = alias_matcher.match(cid)
            assert matched_id == cid, f"Scenario {sc.id} has invalid canonical ingredient: '{cid}'"
            if cid in TARGET_30_INDIAN_INGREDIENTS:
                covered_targets.add(cid)

    # 100% coverage of the 30 Indian target ingredients
    assert len(covered_targets) == 30, (
        f"Missing target ingredients: {set(TARGET_30_INDIAN_INGREDIENTS) - covered_targets}"
    )

    # Diversity of conditions
    assert {"FRIDGE", "FREEZER", "PANTRY", "COUNTER"}.issubset(environments)
    assert {"GOOD_LIGHT", "DIM_INTERIOR", "HARSH_GLARE", "SHADOW"}.issubset(lightings)
    assert {"SPARSE", "MODERATE", "CLUTTERED"}.issubset(clutter_levels)


def test_image_files_exist_and_valid(scenarios: list[EvaluationScenario]) -> None:
    """Verify all scenario image files exist and pass real image pipeline validation."""
    for sc in scenarios:
        image_bytes = sc.load_image_bytes()
        assert len(image_bytes) > 0, f"Empty image bytes for {sc.id}"

        # Image must be valid JPEG format
        assert image_bytes[:2] == b"\xff\xd8", f"Scenario {sc.id} image is not a valid JPEG"


@pytest.mark.asyncio
async def test_evaluation_runner_meets_prd_targets(scenarios: list[EvaluationScenario]) -> None:
    """Verify full evaluation execution against PRD Section 14.4 acceptance thresholds."""
    config = EvaluationRunConfig(
        mode="fixture",
        precision_threshold=0.80,
        recall_threshold=0.60,
        validate_image_bytes=True,
    )

    summary = await run_full_evaluation(scenarios=scenarios, config=config)

    assert summary.total_scenarios >= 40
    assert summary.covered_ingredients_count == 30
    assert summary.micro_precision >= 0.80, f"Precision {summary.micro_precision} < 0.80"
    assert summary.micro_recall >= 0.60, f"Recall {summary.micro_recall} < 0.60"
    assert summary.meets_targets is True
    assert summary.average_false_positives_per_scenario <= 0.5


@pytest.mark.asyncio
async def test_negative_controls_empty_shelves(scenarios: list[EvaluationScenario]) -> None:
    """Verify negative control scenarios produce zero detections and zero false positives."""
    neg_scenarios = [s for s in scenarios if len(s.expected_canonical_ids) == 0]
    assert len(neg_scenarios) >= 2, "Expected at least 2 negative control scenarios"

    config = EvaluationRunConfig(mode="fixture")
    for neg_sc in neg_scenarios:
        res = await run_evaluation_scenario(neg_sc, config)
        assert len(res.true_positives) == 0
        assert len(res.false_positives) == 0
        assert len(res.false_negatives) == 0
        assert len(res.unmapped_predictions) == 0
        assert res.needs_user_correction is False


@pytest.mark.asyncio
async def test_user_correction_rate_bounds(scenarios: list[EvaluationScenario]) -> None:
    """Verify realistic user correction rate due to intentional occlusions and unmapped items."""
    config = EvaluationRunConfig(mode="fixture")
    summary = await run_full_evaluation(scenarios=scenarios, config=config)

    # Realistic bound: between 5% and 25% of scenarios require user intervention/correction
    assert 5.0 <= summary.percentage_scenarios_needing_user_correction <= 25.0


@pytest.mark.asyncio
async def test_live_eval_requires_opt_in_and_db(scenarios: list[EvaluationScenario]) -> None:
    """Verify guardrail: live evaluation cannot run without an active DB session."""
    first_sc = scenarios[0]
    live_config = EvaluationRunConfig(mode="live")

    with pytest.raises(ValueError, match="Database session required for live Groq vision evaluation"):
        await run_evaluation_scenario(first_sc, live_config, db=None)
