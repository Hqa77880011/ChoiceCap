# ChoiceCap

Implementation of **Conflict frontier enforcement of non-composable delegation alternatives**.

## Installation

Requires Python `>=3.11`. Run from the repository root in an activated environment.

```bash
python -m pip install -e .
```

Inspection environment: Python 3.13.5; numpy 2.1.3, matplotlib 3.10.0. Checks: Python syntax, configuration parsing and CLI/source argument matching. Training and full evaluation were not run.

## Data

The generator constructs finite workloads from the formal problem. It writes one JSON object per line. Import recorded or independently constructed cases with the same schema.

The bundled generator writes synthetic finite-model scenarios as JSONL. Fix the seed and keep the generated input for paired comparisons.

```bash
python -m choicecap prepare --count 200 --seed 17 --output data/generated.jsonl
```

## Execution and evaluation

```bash
python -m choicecap run --data data/generated.jsonl --output runs/main
```

## Comparisons and ablations

```bash
python -m choicecap suite --data data/generated.jsonl --output runs/comparison
```

Use `--methods` to select: `frontier`, `global_mask`, `pairwise`, `individual`, `ignore_reservations`, `refund_unknown`.

## Outputs

`runs/main/frontier/records.jsonl` stores per-case results; `metrics.json` stores aggregate measurements. Comparison outputs use one directory per method.

```bash
python -m choicecap plot --inputs runs/comparison/frontier --output figures
```

Plotting writes `figures/summary.csv` and metric PNGs. Statistical intervals can be computed from a retained record file:

```bash
python -m choicecap.statistics --records runs/main/frontier/records.jsonl --output results/intervals.json
```
