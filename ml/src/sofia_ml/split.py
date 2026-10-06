"""Leakage-free split (§8.6, REQ-13): by group (customer or paraphrase family) and, when there are dates, temporal.

Temporal: test = examples from the last `holdout_days`; then every group that landed in test is removed from train.
Without dates: each group falls entirely in train or in test according to a stable seeded hash.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import timedelta

from sofia_ml.labeling import LabeledExample


@dataclass
class Split:
    train: list[LabeledExample]
    test: list[LabeledExample]
    strategy: str
    info: dict = field(default_factory=dict)


def _bucket(group_id: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{group_id}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def group_split(
    examples: list[LabeledExample],
    test_size: float = 0.2,
    holdout_days: int | None = None,
    seed: int = 42,
) -> Split:
    dated = [e for e in examples if e.event_date is not None]
    if holdout_days and len(dated) == len(examples) and examples:
        cutoff = max(e.event_date for e in examples) - timedelta(days=holdout_days)
        test = [e for e in examples if e.event_date > cutoff]
        test_groups = {e.group_id for e in test}
        train = [e for e in examples if e.event_date <= cutoff and e.group_id not in test_groups]
        dropped = len(examples) - len(train) - len(test)
        split = Split(train, test, "temporal+group", {"cutoff": cutoff.isoformat(), "dropped_for_leakage": dropped})
    else:
        test = [e for e in examples if _bucket(e.group_id, seed) < test_size]
        train = [e for e in examples if _bucket(e.group_id, seed) >= test_size]
        split = Split(train, test, "group", {"test_size": test_size, "seed": seed})
    assert_no_leakage(split)
    split.info |= {"n_train": len(split.train), "n_test": len(split.test)}
    return split


def assert_no_leakage(split: Split) -> None:
    overlap = {e.group_id for e in split.train} & {e.group_id for e in split.test}
    if overlap:
        raise ValueError(f"leakage: {len(overlap)} groups in both train and test")
    texts = {e.text for e in split.train} & {e.text for e in split.test}
    if texts:
        raise ValueError(f"leakage: {len(texts)} identical texts in both train and test")
