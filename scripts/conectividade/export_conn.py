#!/usr/bin/env python3
"""Exporta os downloads do experimento de conectividade (Q2) para CSV, um caminho por linha.

Uso: export_conn.py SAIDA.csv aparelhos.json ENTRADA [ENTRADA ...]
Cada ENTRADA é CENÁRIO=arquivo[@INSTANTE_DA_TROCA], onde o arquivo é um registro do conn_logger.py (.jsonl) ou
uma consulta de totais tirada do daemon depois do teste (.json, usada quando o registrador parou durante a troca de
rede). Para os .json, o instante Unix da troca de rede (do journal do console) dá os minutos após a troca.
Os pacotes considerados são os três do protocolo: Asphalt 5, Riptide GP e Celeste 64.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_conn import SOURCES, device, family, runs, transport  # noqa: E402

PACKAGES = {"a2bafe010c2757764a03fb87437ff57b0f00007c": "Asphalt 5",
            "7a8eff09cd760a36c144e1eeffc62a0faa61a0e5": "Riptide GP",
            "c915ac63e216603f039cbdb5ff061ad0f0016109": "Celeste 64"}
COLUMNS = ["cenario", "pacote", "inicio_unix", "minutos_apos_troca_de_rede", "duracao_s", "tamanho_bytes",
           "rede_do_console", "aparelho", "familia", "transporte", "origem", "ip", "porta", "bytes_recebidos", "fracao"]


def from_log(path):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    switch = None
    for row in rows:
        if "addresses" in row and switch is None and any(a.startswith(("10.", "100.")) for a in row["addresses"]):
            switch = row["t"]
    for infohash, name in PACKAGES.items():
        for run in runs(rows, infohash):
            network = " ".join(a for a in run["addresses"] if not a.startswith(("fd", "fe80")))
            yield (name, run["start"], run["end"] - run["start"], run["last"]["total"], network,
                   (run["start"] - switch) / 60 if switch else "", run["last"].get("paths") or [])


def from_totals(path, switch=None):
    data = json.load(open(path))
    for item in data["torrents"]:
        name = PACKAGES.get(item["hash"])
        if name and item.get("end_mtime"):
            minutes = (item["start"] - switch) / 60 if switch else ""
            yield (name, item["start"], item["end_mtime"] - item["start"], item["total"], "", minutes, item["paths"])


def main():
    output, devices = sys.argv[1], json.load(open(sys.argv[2]))
    count = 0
    with open(output, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for spec in sys.argv[3:]:
            scenario, path = spec.split("=", 1)
            path, _, switch = path.partition("@")
            source = from_totals(path, float(switch) if switch else None) if path.endswith(".json") else from_log(path)
            for name, start, seconds, total, network, minutes, paths in sorted(source, key=lambda r: r[1]):
                for path_row in paths:
                    received = int(path_row["downloadedBytes"])
                    if not received:
                        continue
                    writer.writerow([scenario, name, round(start), round(minutes, 2) if minutes != "" else "",
                                     round(seconds, 1), total, network, device(path_row, devices), family(path_row),
                                     transport(path_row), SOURCES.get(path_row["source"], path_row["source"]),
                                     path_row["ip"], path_row.get("port", ""), received, round(received / total, 4)])
                    count += 1
    print(f"{output}: {count} linhas")


if __name__ == "__main__":
    main()
