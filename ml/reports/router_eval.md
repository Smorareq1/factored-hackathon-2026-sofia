# Router: baseline vs proposed (REQ-13)

Split: `{"strategy": "group", "test_size": 0.2, "seed": 42, "n_train": 200, "n_test": 56}`

Served: `hybrid-0.1[rules-ds-0.2+tfidf-lr-0.1]` · agent clarifies below `0.35`

| System | n | macro-F1 | needs_human recall | accuracy | language acc. | macro-F1 ES | macro-F1 PT |
|---|---|---|---|---|---|---|---|
| rules-ds-0.2 | 56 | 0.476 | 0.3 | 0.536 | 0.946 | 0.515 | 0.431 |
| tfidf-lr-0.1 | 56 | 0.641 | 0.7 | 0.643 | 0.946 | 0.571 | 0.716 |
| hybrid-0.1[rules-ds-0.2+tfidf-lr-0.1] | 56 | 0.746 | 0.8 | 0.768 | 0.946 | 0.715 | 0.778 |
