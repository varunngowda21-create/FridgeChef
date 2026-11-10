"""Unit tests for vision evaluation metric calculations and edge cases."""

from tests.eval.metrics import (
    calculate_evaluation_summary,
    calculate_scenario_metrics,
)


class TestScenarioMetricCalculations:
    """Verifies precision, recall, F1, and user correction calculations per scenario."""

    def test_perfect_scenario_prediction(self) -> None:
        result = calculate_scenario_metrics(
            scenario_id="s1",
            ground_truth=["tomato", "onion", "green_chilli"],
            predictions=["tomato", "onion", "green_chilli"],
        )
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
        assert result.true_positives == ["green_chilli", "onion", "tomato"]
        assert result.false_positives == []
        assert result.false_negatives == []
        assert not result.needs_user_correction

    def test_partial_match_with_fp_and_fn(self) -> None:
        # Expected: tomato, onion, garlic (3)
        # Predicted: tomato, onion, capsicum (3)
        # TP: tomato, onion (2)
        # FP: capsicum (1)
        # FN: garlic (1)
        # Precision: 2 / (2 + 1) = 0.6667
        # Recall: 2 / (2 + 1) = 0.6667
        result = calculate_scenario_metrics(
            scenario_id="s2",
            ground_truth=["tomato", "onion", "garlic"],
            predictions=["tomato", "onion", "capsicum"],
        )
        assert result.true_positives == ["onion", "tomato"]
        assert result.false_positives == ["capsicum"]
        assert result.false_negatives == ["garlic"]
        assert result.precision == 0.6667
        assert result.recall == 0.6667
        assert result.f1 == 0.6667
        assert result.needs_user_correction

    def test_unmapped_predictions_penalize_precision(self) -> None:
        # Expected: tomato, potato
        # Predicted: tomato
        # Unmapped: "mystery_leaf"
        # TP: 1 (tomato)
        # FP: 1 (mystery_leaf)
        # FN: 1 (potato)
        # Precision: 1 / (1 + 1) = 0.50
        # Recall: 1 / (1 + 1) = 0.50
        result = calculate_scenario_metrics(
            scenario_id="s3",
            ground_truth=["tomato", "potato"],
            predictions=["tomato"],
            unmapped_predictions=["mystery_leaf"],
        )
        assert result.precision == 0.5
        assert result.recall == 0.5
        assert "UNMAPPED:mystery_leaf" in result.false_positives
        assert result.needs_user_correction

    def test_empty_ground_truth_and_empty_prediction(self) -> None:
        # Empty fridge shelf with no ingredients
        result = calculate_scenario_metrics(
            scenario_id="s_empty",
            ground_truth=[],
            predictions=[],
            unmapped_predictions=[],
        )
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
        assert not result.needs_user_correction

    def test_empty_ground_truth_with_hallucinated_prediction(self) -> None:
        # Empty shelf but model hallucinates an apple
        result = calculate_scenario_metrics(
            scenario_id="s_empty_hallucination",
            ground_truth=[],
            predictions=["apple"],
        )
        assert result.precision == 0.0
        assert result.recall == 1.0
        assert result.f1 == 0.0
        assert result.false_positives == ["apple"]
        assert result.needs_user_correction

    def test_non_empty_ground_truth_with_zero_predictions(self) -> None:
        # Dim fridge with missed items
        result = calculate_scenario_metrics(
            scenario_id="s_missed_all",
            ground_truth=["paneer", "milk"],
            predictions=[],
        )
        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0
        assert result.false_negatives == ["milk", "paneer"]
        assert result.needs_user_correction

    def test_target_ingredients_filter(self) -> None:
        # Ground truth has a rare staple 'lotus_root' not in 30 targets
        target_set = {"tomato", "onion", "ginger"}
        result = calculate_scenario_metrics(
            scenario_id="s_filter",
            ground_truth=["tomato", "lotus_root"],
            predictions=["tomato", "dragon_fruit"],
            target_ingredients=target_set,
        )
        # Only 'tomato' is within target set
        assert result.ground_truth == ["tomato"]
        assert result.predictions == ["tomato"]
        assert result.precision == 1.0
        assert result.recall == 1.0


class TestEvaluationSummaryAggregation:
    """Verifies micro, macro, and per-ingredient metric aggregation across scenarios."""

    def test_summary_aggregation(self) -> None:
        target_set = {"tomato", "onion", "ginger", "garlic"}

        # Scenario 1: TP=2 (tomato, onion), FP=0, FN=0
        s1 = calculate_scenario_metrics(
            scenario_id="s1",
            ground_truth=["tomato", "onion"],
            predictions=["tomato", "onion"],
            target_ingredients=target_set,
        )

        # Scenario 2: TP=1 (ginger), FP=1 (garlic), FN=1 (onion)
        s2 = calculate_scenario_metrics(
            scenario_id="s2",
            ground_truth=["ginger", "onion"],
            predictions=["ginger", "garlic"],
            target_ingredients=target_set,
        )

        summary = calculate_evaluation_summary(
            scenario_results=[s1, s2],
            target_ingredients=target_set,
            precision_threshold=0.80,
            recall_threshold=0.60,
        )

        assert summary.total_scenarios == 2
        assert summary.total_target_ingredients == 4
        # Total TP = 2 + 1 = 3
        # Total FP = 0 + 1 = 1
        # Total FN = 0 + 1 = 1
        # Micro P = 3 / (3 + 1) = 0.75
        # Micro R = 3 / (3 + 1) = 0.75
        assert summary.micro_precision == 0.75
        assert summary.micro_recall == 0.75
        assert summary.meets_targets is False  # Precision 0.75 < 0.80 threshold
        assert summary.percentage_scenarios_needing_user_correction == 50.0  # 1 out of 2

    def test_empty_scenarios_summary(self) -> None:
        summary = calculate_evaluation_summary([], target_ingredients={"tomato"})
        assert summary.total_scenarios == 0
        assert summary.micro_precision == 0.0
        assert summary.micro_recall == 0.0
        assert summary.meets_targets is False
