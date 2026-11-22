#!/usr/bin/env python3
"""Amostra CPU e memória de um processo a cada INTERVALO segundos, em JSON por linha.

Uso: sampler.py PID SAIDA [INTERVALO [PORTA_RPC SEGREDO [kmp|tr]]]
Memória em KiB, lida de smaps_rollup (ou smaps somado, em kernels antigos).
CPU em ticks acumulados (utime + stime); o controlador converte para % de um núcleo.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

FIELDS = ("Rss", "Pss", "Shared_Clean", "Shared_Dirty", "Private_Clean", "Private_Dirty", "Anonymous", "Swap")


def memory(pid):
    path = f"/proc/{pid}/smaps_rollup"
    if not os.path.exists(path):
        path = f"/proc/{pid}/smaps"
    total = dict.fromkeys(FIELDS, 0)
    with open(path) as handle:
        for line in handle:
            key, _, rest = line.partition(":")
            if key in total:
                total[key] += int(rest.split()[0])
    return total


def cpu_ticks(pid):
    with open(f"/proc/{pid}/stat") as handle:
        fields = handle.read().rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


def mem_available():
    with open("/proc/meminfo") as handle:
        for line in handle:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    return 0


SESSION = {"id": ""}


def transfer_tr(port):
    """Mesmo progresso, pela API do Transmission (repete a chamada quando ela pede a sessão)."""
    body = json.dumps({"method": "torrent-get", "arguments": {
        "fields": ["haveValid", "uploadedEver", "rateDownload", "rateUpload"]}}).encode()
    for _ in range(2):
        request = urllib.request.Request(f"http://127.0.0.1:{port}/transmission/rpc", body,
                                         {"X-Transmission-Session-Id": SESSION["id"]})
        try:
            with urllib.request.urlopen(request, timeout=3) as reply:
                items = json.load(reply)["arguments"]["torrents"]
        except urllib.error.HTTPError as error:
            if error.code == 409:
                SESSION["id"] = error.headers.get("X-Transmission-Session-Id", "")
                continue
            return {"rpc": False}
        except Exception:
            return {"rpc": False}
        return {"rpc": True, "done": sum(x["haveValid"] for x in items), "sent": sum(x["uploadedEver"] for x in items),
                "down": sum(x["rateDownload"] for x in items), "up": sum(x["rateUpload"] for x in items)}
    return {"rpc": False}


def transfer(port, secret):
    """Progresso lido do próprio motor, pela API local: não passa pelo Wi-Fi."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "aria2.tellActive", "params": [f"token:{secret}"]}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/jsonrpc", body), timeout=3) as reply:
            items = json.load(reply).get("result") or []
    except Exception:
        return {"rpc": False}
    return {"rpc": True, "done": sum(int(x["completedLength"]) for x in items),
            "sent": sum(int(x.get("uploadLength", 0)) for x in items),
            "down": sum(int(x["downloadSpeed"]) for x in items), "up": sum(int(x["uploadSpeed"]) for x in items)}


def main():
    pid, output = sys.argv[1], sys.argv[2]
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    port, secret = (sys.argv[4], sys.argv[5]) if len(sys.argv) > 5 else (None, None)
    mode = sys.argv[6] if len(sys.argv) > 6 else "kmp"
    hz = os.sysconf("SC_CLK_TCK")
    with open(output, "a", buffering=1) as out:
        while os.path.exists(f"/proc/{pid}"):
            try:
                row = {"t": time.time(), "ticks": cpu_ticks(pid), "hz": hz, "avail": mem_available()}
                row.update(memory(pid))
                if port:
                    asked = time.time()
                    row.update(transfer_tr(port) if mode == "tr" else transfer(port, secret))
                    row["rpc_s"] = round(time.time() - asked, 3)
            except (OSError, ValueError, IndexError):
                break
            out.write(json.dumps(row) + "\n")
            time.sleep(interval)


if __name__ == "__main__":
    main()
