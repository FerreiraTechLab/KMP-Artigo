#!/usr/bin/env python3
"""Separa os downloads de um pacote no registro do conn_logger.py e soma os bytes por caminho.

Uso: analyze_conn.py LOG.jsonl INFOHASH aparelhos.json [SAIDA.csv]

aparelhos.json identifica quem é quem pelos endereços e portas, por exemplo:
  {"ips": {"163.176.18.211": "nó público"},
   "ports": {"6882": "PC (Publisher)", "34567": "console antigo"},
   "lan": "192.168.0.", "home_v6": "2001:db8:1:"}
Um download começa quando o pacote aparece incompleto e termina quando fica completo. Para cada um, mostra o
tempo, a rede do console e os bytes recebidos por aparelho, família (IPv4/IPv6), transporte (TCP/uTP) e origem
do peer (Tr tracker, Hg/Ha DHT, X PEX, Lpd rede local, M peer direto, C hole punching, I conexão de entrada).
"""
import csv
import json
import sys
from collections import defaultdict

SOURCES = {"Tr": "tracker", "Hg": "DHT", "Ha": "DHT", "X": "PEX", "Lpd": "rede local (LPD)",
           "M": "peer direto", "C": "hole punching", "I": "entrada"}


def device(path, devices):
    # A porta de escuta identifica o aparelho mesmo quando vários compartilham um IP (o IPv4 público da casa,
    # ou um IPv6 /128 que o roteador repetiu); o IP só decide quando a porta é desconhecida (conexão de entrada).
    ip, port = path.get("ip", ""), str(path.get("port", ""))
    name = devices.get("ports", {}).get(port)
    if name:
        return name
    if ip in devices.get("ips", {}):
        return devices["ips"][ip]
    if ip.startswith(devices.get("lan", "192.168.")):
        return f"rede local {ip}"
    return f"outro ({ip})"


def family(path):
    network = path.get("network", "")
    if network.endswith("6") or ":" in path.get("ip", ""):
        return "IPv6"
    return "IPv4"


def transport(path):
    return "uTP" if path.get("network", "").startswith("udp") else "TCP"


def runs(rows, infohash):
    """Lista de downloads: (início, fim, último registro com os totais, endereços do console)."""
    found, current, addresses = [], None, []
    for row in rows:
        if "addresses" in row:
            addresses = row["addresses"]
        for item in row.get("torrents", []):
            if item.get("hash") != infohash:
                continue
            complete = item["total"] and item["done"] >= item["total"]
            if current is None and not complete:
                current = {"start": row["t"], "addresses": addresses, "last": item}
            elif current is not None:
                if item.get("paths") is not None:
                    current["last"] = item
                if complete:
                    current["end"] = row["t"]
                    found.append(current)
                    current = None
    return found


def main():
    rows = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
    infohash, devices = sys.argv[2].lower(), json.load(open(sys.argv[3]))
    output = sys.argv[4] if len(sys.argv) > 4 else None
    table = []
    for number, run in enumerate(runs(rows, infohash), 1):
        item = run["last"]
        total, paths = item["total"], item.get("paths") or []
        attributed = sum(int(p["downloadedBytes"]) for p in paths)
        seconds = run["end"] - run["start"]
        network = ", ".join(a for a in run["addresses"] if not a.startswith(("fd", "fe80"))) or "?"
        print(f"\n== download {number}: {total / 1048576:.1f} MiB em {seconds:.0f} s "
              f"({total / 1048576 / seconds:.2f} MiB/s); rede do console: {network}")
        groups = defaultdict(int)
        for path in paths:
            key = (device(path, devices), family(path), transport(path), SOURCES.get(path["source"], path["source"]))
            groups[key] += int(path["downloadedBytes"])
        for key, value in sorted(groups.items(), key=lambda kv: -kv[1]):
            if value:
                print(f"  {value / 1048576:7.2f} MiB {value / total:6.1%}  {' · '.join(key)}")
                table.append([number, round(seconds, 1), total, *key, value, round(value / total, 4)])
        print(f"  atribuído {attributed / total:.1%} do pacote")
    if output:
        with open(output, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["download", "segundos", "tamanho_bytes", "aparelho", "familia", "transporte", "origem",
                             "bytes_recebidos", "fracao"])
            writer.writerows(table)


if __name__ == "__main__":
    main()
