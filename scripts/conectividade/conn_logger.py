#!/usr/bin/env python3
"""Registra, no próprio console, de quem chegam e para quem saem os bytes de cada torrent.

Uso: conn_logger.py SAIDA.jsonl [DURAÇÃO_S] [INTERVALO_S]   (padrão: 3600 s, 2 s)

Lê o endereço e o segredo da API em /roms/ports/KMP/conf/daemon/rpc.env e consulta o kmp-torrentd local.
A cada intervalo grava uma linha com o progresso de cada torrent ativo e os bytes recebidos e enviados por
caminho: endereço do peer, origem (Tr, Hg/Ha, X, Lpd, M, C, I) e transporte/família (tcp4, udp6…). Os totais
são acumulados pelo próprio daemon e incluem as conexões já encerradas.
Roda sem depender da rede do PC: serve para o console que está em outra rede (dados móveis).
Também registra as interfaces de rede, para saber em qual rede o console estava em cada momento, e a cada 5 s os
contadores de descoberta e hole punching (kmp.getNetworkStats). Para sobreviver à troca de Wi-Fi pelo menu do
ArkOS/dArkOS, que mata processos da sessão, inicie-o como serviço transitório:
  sudo systemd-run --unit=kmp-conn-logger --uid=ark python3 conn_logger.py SAIDA.jsonl 10800 2
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

ENV = os.environ.get("KMP_RPC_ENV", "/roms/ports/KMP/conf/daemon/rpc.env")


def settings():
    values = {}
    with open(ENV) as handle:
        for line in handle:
            key, _, value = line.strip().partition("=")
            values[key] = value
    return values["KMP_ARIA2_RPC"], values["KMP_ARIA2_SECRET"]


def rpc(url, secret, method, *params):
    body = json.dumps({"jsonrpc": "2.0", "id": "log", "method": method, "params": [f"token:{secret}", *params]})
    with urllib.request.urlopen(urllib.request.Request(url, body.encode()), timeout=5) as reply:
        data = json.load(reply)
    if "error" in data:
        raise RuntimeError(data["error"])
    return data["result"]


def addresses():
    """Endereços IPv4/IPv6 globais do console, para saber em que rede ele estava."""
    try:
        out = subprocess.run(["ip", "-o", "addr", "show", "scope", "global"], capture_output=True, text=True,
                             timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return sorted({line.split()[3] for line in out.splitlines() if len(line.split()) > 3})


def main():
    output = sys.argv[1]
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 3600
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    end = time.time() + duration
    last_addresses, last_net_check, last_stats = None, 0, 0
    with open(output, "a", buffering=1) as out:
        out.write(json.dumps({"t": time.time(), "event": "start", "host": socket.gethostname()}) + "\n")
        while time.time() < end:
            row = {"t": time.time()}
            if time.time() - last_net_check > 10:
                last_net_check = time.time()
                current = addresses()
                if current != last_addresses:
                    row["addresses"] = last_addresses = current
            try:
                url, secret = settings()
                torrents = []
                for item in rpc(url, secret, "aria2.tellActive"):
                    entry = {"gid": item["gid"], "hash": item.get("infoHash", ""),
                             "total": int(item.get("totalLength", 0)), "done": int(item.get("completedLength", 0)),
                             "down": int(item.get("downloadSpeed", 0)), "up": int(item.get("uploadSpeed", 0)),
                             "sent": int(item.get("uploadLength", 0))}
                    # Só detalha os torrents com tráfego, para não pesar no console. O kmp.getPeerTotals
                    # (kmp-torrentd 0.2.9+) já soma as conexões encerradas; o getPeers só vê as abertas.
                    if entry["down"] or entry["up"] or entry["done"] < entry["total"]:
                        try:
                            entry["paths"] = rpc(url, secret, "kmp.getPeerTotals", item["gid"])
                        except RuntimeError:
                            entry["peers"] = [
                                {k: p.get(k) for k in ("ip", "port", "source", "network", "downloadedBytes",
                                                       "uploadedBytes")}
                                for p in rpc(url, secret, "aria2.getPeers", item["gid"])]
                    torrents.append(entry)
                row["torrents"] = torrents
                # Contadores de descoberta e de hole punching, e de onde vieram os peers conhecidos de cada
                # torrent: mostram quem o console conhecia mesmo sem conseguir conectar.
                if time.time() - last_stats >= 5:
                    last_stats = time.time()
                    stats = rpc(url, secret, "kmp.getNetworkStats")
                    active = {t["hash"] for t in torrents if "paths" in t or "peers" in t}
                    stats["torrents"] = [t for t in stats.get("torrents", []) if t.get("infoHash") in active]
                    row["network"] = stats
            except Exception as error:  # daemon reiniciando, Client fechado etc.
                row["error"] = str(error)[:200]
            out.write(json.dumps(row) + "\n")
            time.sleep(interval)
        out.write(json.dumps({"t": time.time(), "event": "end"}) + "\n")


if __name__ == "__main__":
    main()
