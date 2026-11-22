#!/usr/bin/env python3
"""Resume os resultados do bench.py: mediana e faixa (mín–máx) de cada métrica por motor."""
import json
import statistics
import sys
from pathlib import Path


def load(results, tag):
    marks = json.loads((results / f"{tag}.marks.json").read_text())
    offset = marks["offset"]
    samples = [json.loads(line) for line in (results / f"{tag}.samples.jsonl").read_text().splitlines() if line.strip()]
    for row in samples:
        row["t"] -= offset  # para o relógio do PC
    return marks, samples


def window(samples, start, end):
    inside = [row for row in samples if start <= row["t"] <= end]
    return inside


def cpu_percent(samples, start, end):
    rows = window(samples, start - 1, end + 1)
    if len(rows) < 2:
        return None, None
    first, last = rows[0], rows[-1]
    seconds = (last["ticks"] - first["ticks"]) / first["hz"]
    return 100 * seconds / (last["t"] - first["t"]), seconds


def summarize(results, total_mib):
    per_engine = {}
    for marks_file in sorted(results.glob("*.marks.json")):
        tag = marks_file.name.removesuffix(".marks.json")
        marks, samples = load(results, tag)
        add, first, done = marks["download"]
        uadd, ufirst, udone = marks["upload"]
        down_cpu, down_sec = cpu_percent(samples, add, done)
        up_cpu, up_sec = cpu_percent(samples, uadd, udone)
        idle_cpu, _ = cpu_percent(samples, *marks["idle1"])
        mib = lambda kib: kib / 1024
        # Primeiro byte do download pelo progresso que o próprio console registrou.
        first = next((r["t"] for r in samples if r.get("rpc") and r.get("done", 0) > 0 and r["t"] >= add - 1), add)
        first = max(first, add)
        row = {
            "download MiB/s": total_mib / (done - add),
            "upload MiB/s": total_mib / (udone - uadd),
            "download após 1º byte MiB/s": total_mib / max(done - first, 0.001),
            "upload após 1º byte MiB/s": total_mib / max(udone - ufirst, 0.001),
            "download 1º byte s": first - add,
            "upload 1º byte s": ufirst - uadd,
            "CPU no download %": down_cpu,
            "CPU no upload %": up_cpu,
            "CPU s por GiB baixado": down_sec * 1024 / total_mib,
            "CPU s por GiB enviado": up_sec * 1024 / total_mib,
            "CPU parado %": idle_cpu,
            "RSS pico MB": mib(max(r["Rss"] for r in samples)),
            "PSS pico MB": mib(max(r["Pss"] for r in samples)),
            "anônima pico MB": mib(max(r["Anonymous"] for r in samples)),
            "arquivo mapeado pico MB": mib(max(r["Rss"] - r["Anonymous"] for r in samples)),
            "RSS no fim MB": mib(samples[-1]["Rss"]),
            "MemAvailable mín MB": mib(min(r["avail"] for r in samples)),
            "API local pior resposta s": max([r.get("rpc_s", 0) for r in samples] or [0]),
            "API local sem resposta (amostras)": sum(1 for r in samples if r.get("rpc") is False),
        }
        per_engine.setdefault(marks["engine"], []).append(row)
    keys = list(next(iter(per_engine.values()))[0])
    order = [e for e in ("old", "new", "transmission") if e in per_engine]
    print(f"{'métrica':28} " + " ".join(f"{e:>26}" for e in order))
    for key in keys:
        cells = []
        for engine in order:
            values = [r[key] for r in per_engine[engine] if r[key] is not None]
            med = statistics.median(values)
            cells.append(f"{med:9.2f} ({min(values):7.2f}–{max(values):7.2f})")
        print(f"{key:28} " + " ".join(f"{c:>26}" for c in cells))
    print("n =", {e: len(v) for e, v in per_engine.items()})
    return per_engine


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    data = summarize(folder, float(sys.argv[2]) if len(sys.argv) > 2 else 256)
    (folder / "summary.json").write_text(json.dumps(data, indent=1))
