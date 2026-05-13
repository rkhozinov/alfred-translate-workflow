"""
Latency benchmark for the translate workflow.

Run:
    python3 tests/bench.py
    BENCH_N=20 python3 tests/bench.py

Reports p50 / p95 / max wall time per case. Includes a 200ms sleep between
samples to be gentle on the unauthenticated endpoint.
"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main  # noqa: E402

CASES = [
    ("RU->EN short",    "Привет"),
    ("RU->EN sentence", "Жизнь прекрасна и мир восхитителен"),
    ("EN->RU short",    "hello"),
    ("EN->RU sentence", "Life is beautiful and the world is wonderful"),
    ("FR->RU",          "Bonjour le monde"),
]

N = int(os.environ.get("BENCH_N", "10"))
os.environ.setdefault("output_language", "ru")
os.environ.setdefault("input_language", "en")


def percentile(samples_sorted, p):
    if not samples_sorted:
        return 0.0
    k = (len(samples_sorted) - 1) * p
    f = int(k)
    c = min(f + 1, len(samples_sorted) - 1)
    return samples_sorted[f] + (samples_sorted[c] - samples_sorted[f]) * (k - f)


def main_bench():
    print(f"runs per case: {N}\n")
    print(f"{'case':22} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    print("-" * 50)
    overall = []
    for label, text in CASES:
        samples = []
        for _ in range(N):
            t0 = time.perf_counter()
            try:
                main.main_entry(text)
            except Exception as e:
                print(f"  ERROR on {label!r}: {e}")
                break
            samples.append((time.perf_counter() - t0) * 1000)
            time.sleep(0.2)
        if not samples:
            continue
        overall.extend(samples)
        samples.sort()
        p50 = percentile(samples, 0.50)
        p95 = percentile(samples, 0.95)
        print(f"{label:22} {p50:8.0f} {p95:8.0f} {max(samples):8.0f}")
    if overall:
        overall.sort()
        print("-" * 50)
        print(
            f"{'OVERALL':22} "
            f"{percentile(overall, 0.50):8.0f} "
            f"{percentile(overall, 0.95):8.0f} "
            f"{max(overall):8.0f}"
        )


if __name__ == "__main__":
    main_bench()
