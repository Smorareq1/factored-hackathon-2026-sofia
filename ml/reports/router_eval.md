# Router: baseline vs proposed (REQ-13)

Split: `{"strategy": "group", "test_size": 0.2, "seed": 42, "n_train": 200, "n_test": 56}`

Served: `hybrid-0.1[rules-ds-0.2+tfidf-lr-0.1]` · agent clarifies below `0.35`

| System | n | macro-F1 | needs_human recall | accuracy | language acc. | macro-F1 ES | macro-F1 PT |
|---|---|---|---|---|---|---|---|
| rules-ds-0.2 | 56 | 0.377 | 0.0 | 0.482 | 0.946 | 0.392 | 0.36 |
| tfidf-lr-0.1 | 56 | 0.641 | 0.7 | 0.643 | 0.946 | 0.571 | 0.716 |
| hybrid-0.1[rules-ds-0.2+tfidf-lr-0.1] | 56 | 0.728 | 0.7 | 0.75 | 0.946 | 0.677 | 0.778 |
