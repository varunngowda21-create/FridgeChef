"""Vision evaluation runner.

Exercises the real image processing pipeline, vision schema validation,
and catalogue alias normalization to measure identification performance.
Supports both deterministic fixture-based evaluation (default) and opt-in live provider evaluation.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.llm.vision import _clean_and_validate_vision_output, call_groq_vision
from app.media.image_pipeline import validate_and_process_image
from app.services.normalise import alias_matcher
from tests.eval.dataset import (
    TARGET_30_INDIAN_INGREDIENTS,
    EvaluationScenario,
    load_evaluation_scenarios,
)
from tests.eval.metrics import (
    EvaluationSummary,
    ScenarioMetricResult,
    calculate_evaluation_summary,
    calculate_scenario_metrics,
)

logger = logging.getLogger("fridgechef.eval")


@dataclass
class EvaluationRunConfig:
    mode: Literal["fixture", "live"] = "fixture"
    target_ingredients: list[str] | None = None
    precision_threshold: float = 0.80
    recall_threshold: float = 0.60
    validate_image_bytes: bool = True


async def run_evaluation_scenario(
    scenario: EvaluationScenario,
    config: EvaluationRunConfig,
    db: Session | None = None,
) -> ScenarioMetricResult:
    """Execute a single scenario through the real FridgeChef vision and normalization pipeline."""
    # 1. Exercise real image pipeline (EXIF stripping, resizing, JPEG re-encoding)
    if config.validate_image_bytes:
        image_bytes = scenario.load_image_bytes()
        processed_image = validate_and_process_image(file_bytes=image_bytes)
        assert len(processed_image.data) > 0, f"Image processing failed for scenario {scenario.id}"

    # 2. Vision output generation
    if config.mode == "live":
        if db is None:
            raise ValueError("Database session required for live Groq vision evaluation")
        # Live Groq API inference
        vision_response = await call_groq_vision(
            image_bytes=processed_image.data,
            db=db,
        )
    else:
        # Fixture evaluation: validates stored model output through real schema cleaner & validator
        vision_response = _clean_and_validate_vision_output(scenario.stored_vision_output)

    # 3. Exercise real catalogue alias matching and normalization
    predicted_canonical_ids: list[str] = []
    unmapped_items: list[str] = []

    for item in vision_response.items:
        canonical_id, _ = alias_matcher.match(item.name)
        if canonical_id is not None:
            predicted_canonical_ids.append(canonical_id)
        else:
            unmapped_items.append(item.name)

    # 4. Compute metrics against ground truth
    targets = set(config.target_ingredients or TARGET_30_INDIAN_INGREDIENTS)
    return calculate_scenario_metrics(
        scenario_id=scenario.id,
        ground_truth=scenario.expected_canonical_ids,
        predictions=predicted_canonical_ids,
        unmapped_predictions=unmapped_items,
        target_ingredients=targets,
    )


async def run_full_evaluation(
    scenarios: list[EvaluationScenario] | None = None,
    config: EvaluationRunConfig | None = None,
    db: Session | None = None,
) -> EvaluationSummary:
    """Run evaluation across all scenarios and aggregate results."""
    cfg = config or EvaluationRunConfig()
    scenario_list = scenarios if scenarios is not None else load_evaluation_scenarios()
    targets = set(cfg.target_ingredients or TARGET_30_INDIAN_INGREDIENTS)

    results: list[ScenarioMetricResult] = []
    for sc in scenario_list:
        metric_res = await run_evaluation_scenario(sc, cfg, db=db)
        results.append(metric_res)

    return calculate_evaluation_summary(
        scenario_results=results,
        target_ingredients=targets,
        precision_threshold=cfg.precision_threshold,
        recall_threshold=cfg.recall_threshold,
    )

