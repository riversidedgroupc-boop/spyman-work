"""Fusion strategy definitions and utilities."""

from src.fusion.decision_types import FusionStrategy

STRATEGY_NAMES: dict[FusionStrategy, str] = {
    FusionStrategy.YOLO_ONLY: "YOLO Only",
    FusionStrategy.ANOMALY_ONLY: "Anomaly Only",
    FusionStrategy.YOLO_PRIORITY: "YOLO Priority",
    FusionStrategy.ANOMALY_PRIORITY: "Anomaly Priority",
    FusionStrategy.RULE_BASED: "Rule Based Fusion",
    FusionStrategy.DOUBLE_CONFIRM: "Double Confirm",
    FusionStrategy.EXPLORATION_FIRST: "Exploration First",
    FusionStrategy.FEW_SHOT: "Few-Shot Learning",
    FusionStrategy.PRODUCTION_RETEST: "Production Retest",
    FusionStrategy.STABLE_PRODUCTION: "Stable Production",
}

STRATEGY_DESCRIPTIONS: dict[FusionStrategy, str] = {
    FusionStrategy.YOLO_ONLY: "Only use YOLO detection results for decision.",
    FusionStrategy.ANOMALY_ONLY: "Only use anomaly detection scores for decision.",
    FusionStrategy.YOLO_PRIORITY: "YOLO takes priority; anomaly consulted when YOLO is uncertain.",
    FusionStrategy.ANOMALY_PRIORITY: "Anomaly takes priority; YOLO used for class confirmation.",
    FusionStrategy.RULE_BASED: "Comprehensive rules combining all models with geometry and density checks.",
    FusionStrategy.DOUBLE_CONFIRM: "Both YOLO and anomaly must agree for NG; otherwise SUSPECT.",
    FusionStrategy.EXPLORATION_FIRST: "Anomaly primary for unknown defect discovery; YOLO optional if model exists.",
    FusionStrategy.FEW_SHOT: "YOLO handles known defect classes; anomaly catches unknowns.",
    FusionStrategy.PRODUCTION_RETEST: "YOLO + anomaly in parallel; fusion emits OK/NG/Suspect/Unknown.",
    FusionStrategy.STABLE_PRODUCTION: "YOLO primary with TensorRT; anomaly as drift/unknown monitor only.",
}


def get_strategy_name(strategy: FusionStrategy) -> str:
    """Return human-readable name for a fusion strategy."""
    return STRATEGY_NAMES.get(strategy, strategy.value)


def get_strategy_description(strategy: FusionStrategy) -> str:
    """Return description for a fusion strategy."""
    return STRATEGY_DESCRIPTIONS.get(strategy, "")


def list_strategies() -> list[dict[str, str]]:
    """Return all available strategies with names and descriptions."""
    return [
        {
            "id": s.value,
            "name": STRATEGY_NAMES.get(s, s.value),
            "description": STRATEGY_DESCRIPTIONS.get(s, ""),
        }
        for s in FusionStrategy
    ]
