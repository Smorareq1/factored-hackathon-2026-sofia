# Router: baseline vs propuesto (REQ-13)

Split: `{"strategy": "group", "test_size": 0.2, "seed": 42, "n_train": 200, "n_test": 56}`

| Sistema | n | macro-F1 | recall needs_human | accuracy | acc. idioma | macro-F1 ES | macro-F1 PT |
|---|---|---|---|---|---|---|---|
| rules-ds-0.1 | 56 | 0.377 | 0.0 | 0.482 | 0.946 | 0.392 | 0.36 |
| tfidf-lr-0.1 | 56 | 0.641 | 0.7 | 0.643 | 0.946 | 0.571 | 0.716 |
