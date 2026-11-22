#!/usr/bin/env python3
"""Exporta uma execução do bench.py para dois CSVs: resumo por rodada e amostras segundo a segundo.

Uso: export_csv.py PASTA_DE_RESULTADOS PREFIXO_DE_SAIDA [TAMANHO_MIB] [DESCRIÇÃO_DO_CONSOLE]
Gera PREFIXO.csv (formato longo: data, console, motor, versão, rodada, métrica, valor, unidade)
e PREFIXO-amostras.csv.
"""
import contextlib
import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402

NAMES = {
    "download MiB/s": ("download", "MiB/s"), "upload MiB/s": ("upload", "MiB/s"),
    "download após 1º byte MiB/s": ("download_apos_primeiro_byte", "MiB/s"),
    "upload após 1º byte MiB/s": ("upload_apos_primeiro_byte", "MiB/s"),
    "download 1º byte s": ("download_primeiro_byte", "s"), "upload 1º byte s": ("upload_primeiro_byte", "s"),
    "CPU no download %": ("cpu_motor_baixando", "% de um núcleo"),
    "CPU no upload %": ("cpu_motor_enviando", "% de um núcleo"),
    "CPU s por GiB baixado": ("cpu_s_por_gib_baixado", "s"), "CPU s por GiB enviado": ("cpu_s_por_gib_enviado", "s"),
    "CPU parado %": ("cpu_motor_parado", "% de um núcleo"),
    "RSS pico MB": ("rss_motor_pico", "MiB"), "PSS pico MB": ("pss_motor_pico", "MiB"),
    "anônima pico MB": ("anonima_motor_pico", "MiB"), "arquivo mapeado pico MB": ("mapeado_motor_pico", "MiB"),
    "RSS no fim MB": ("rss_motor_fim", "MiB"), "MemAvailable mín MB": ("ram_disponivel_min", "MiB"),
    "API local pior resposta s": ("api_pior_resposta", "s"),
    "API local sem resposta (amostras)": ("api_sem_resposta", "amostras"),
}
SAMPLE_COLUMNS = ["motor", "versao", "rodada", "segundos", "fase", "cpu_ticks", "ticks_por_s", "rss_kib", "pss_kib",
                  "anonima_kib", "private_clean_kib", "private_dirty_kib", "shared_clean_kib", "swap_kib",
                  "ram_disponivel_kib", "baixado_bytes", "enviado_bytes", "download_bps", "upload_bps",
                  "api_resposta_s", "api_respondeu"]


def main():
    folder, prefix = Path(sys.argv[1]), Path(sys.argv[2])
    total_mib = float(sys.argv[3]) if len(sys.argv) > 3 else 256
    console = sys.argv[4] if len(sys.argv) > 4 else folder.name.rsplit("-", 2)[0].replace("_", ".")
    with contextlib.redirect_stdout(io.StringIO()):
        per_engine = analyze.summarize(folder, total_mib)
    marks = {path.name.removesuffix(".marks.json"): json.loads(path.read_text())
             for path in sorted(folder.glob("*.marks.json"))}
    date = datetime.fromtimestamp(next(iter(marks.values()))["download"][0]).strftime("%Y-%m-%d")
    versions = {m["engine"]: m.get("version", m["engine"]) for m in marks.values()}

    with open(prefix.with_suffix(".csv"), "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["data", "console", "motor", "versao", "rodada", "descoberta", "metrica", "valor", "unidade"])
        for engine, runs in per_engine.items():
            tags = sorted(t for t, m in marks.items() if m["engine"] == engine)
            for tag, row in zip(tags, runs):
                for key, value in row.items():
                    name, unit = NAMES[key]
                    writer.writerow([date, console, engine, versions[engine], marks[tag]["run"] + 1,
                                     marks[tag].get("discovery", "addpeers"), name, round(value, 3), unit])

    count = 0
    with open(prefix.with_name(prefix.name + "-amostras.csv"), "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(SAMPLE_COLUMNS)
        for tag, mark in marks.items():
            offset, start = mark["offset"], mark["download"][0]
            phases = [("download", mark["download"][0], mark["download"][2]), ("parado", *mark["idle1"]),
                      ("envio", mark["upload"][0], mark["upload"][2])]
            for line in (folder / f"{tag}.samples.jsonl").read_text().splitlines():
                row = json.loads(line)
                t = row["t"] - offset
                phase = next((name for name, a, b in phases if a <= t <= b), "antes" if t < start else "entre")
                writer.writerow([mark["engine"], versions[mark["engine"]], mark["run"] + 1, round(t - start, 2), phase,
                                 row["ticks"], row["hz"], row["Rss"], row["Pss"], row["Anonymous"], row["Private_Clean"],
                                 row["Private_Dirty"], row["Shared_Clean"], row["Swap"], row["avail"],
                                 row.get("done", ""), row.get("sent", ""), row.get("down", ""), row.get("up", ""),
                                 row.get("rpc_s", ""), "" if "rpc" not in row else int(bool(row["rpc"]))])
                count += 1
    print(f"{prefix.with_suffix('.csv')} e {prefix.name}-amostras.csv: {len(marks)} rodadas, {count} amostras")


if __name__ == "__main__":
    main()
