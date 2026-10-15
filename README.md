# ChoiceCap

Implementation of **Conflict frontier enforcement of non-composable delegation alternatives**.

Implements minimal illegal-set compilation, independent exhaustive completeness checking, reservation before execution, immutable request summaries, and idempotent receipt settlement. Pending and unknown outcomes remain in prospective presence. Policies whose frontier exceeds the compilation budget use the exact alternative-mask decision.

## Install

Use Python 3.11 or newer. Create and activate a virtual environment, then install the package:

```bash
git clone https://github.com/Hqa77880011/ChoiceCap.git
cd ChoiceCap
python -m venv .venv
```

Activate with `source .venv/bin/activate` on Linux/macOS or `.venv\Scripts\Activate.ps1` in PowerShell.

```bash
python -m pip install -e .
```

## Prepare data

```bash
python -m choicecap prepare --count 200 --seed 17 --output data/workload.jsonl
```

The generator constructs finite workloads from the formal problem. It writes one JSON object per line. Import recorded or independently constructed cases with the same schema.

`universe` lists effect atoms; `alternatives` lists approved bundles. `operations` contains reserve and settle events. A reserve has an immutable `id` and `atoms`; settlement has `committed`, `no_effect`, or `unknown` as its outcome. The bundled generator creates high-order conflict families and mixed settlement schedules.

## Execute and compare

```bash
python -m choicecap run --data data/workload.jsonl --output runs/main
python -m choicecap suite --data data/workload.jsonl --methods frontier global_mask --output runs/comparison
```

Omit `--methods` in `suite` to include every comparison method and ablation.

`frontier` is the complete method; `global_mask` evaluates alternatives directly. `pairwise` retains pair constraints, `individual` checks each effect alone, `ignore_reservations` omits pending effects, and `refund_unknown` releases uncertain reservations.

These are algorithmic workloads without learned parameters. `--count` controls scenario count and `--seed` controls generation. Repeat with independent seeds for comparisons.

## Evaluate and visualize

Each method writes `records.jsonl` with per-case outputs and measurements, plus `metrics.json` with counts, means, sample standard deviations and quantiles. Rates are fractions. Conditional metrics exclude cases outside their denominator. Timers cover method execution; independent scoring is outside this timer.

Joint unauthorized-action rate, secure completion, admission, legal effects, frontier size, latency quantiles, CPU, serialized output bytes, process RSS and legal throughput.

```bash
python -m choicecap plot --inputs runs/comparison/frontier runs/comparison/global_mask --output figures
```

Plotting creates `summary.csv` and one PNG per numeric metric. RSS includes the Python runtime and imported libraries. Output bytes measure JSON serialization size.

## Implementation conventions

Transactions use SQLite with `BEGIN IMMEDIATE` for a durable, serialized local ledger. This preserves reservation semantics; it does not model PostgreSQL domain-lock scalability. One ledger is bound to one approval cohort and epoch. Calls to `settle` are the trusted receipt boundary. Integrations must authenticate their receipts before this call.


## Uncertainty and paired comparisons

```bash
python -m choicecap.statistics --records runs/main/frontier/records.jsonl --output results/intervals.json
```

Supply --reference with a matched record file for paired differences. Resampling uses independent case IDs, or explicit cluster IDs when provided. Repeated observations from one source unit must share cluster. Zero-event bounds refer to an event in an independent cluster.
