#!/usr/bin/env python3
"""Compara motores BitTorrent num console: por padrão o KMP 0.2.56 contra o 0.2.60 (A/B), ou, com
--compare new,transmission, o kmp-torrentd atual contra o transmission-daemon (Q3 do artigo).

Cada rodada, no mesmo console e com a mesma carga:
  1. download: o PC semeia um pacote sintético e o console baixa só dele (pela rede local);
  2. parado: 45 s semeando sem ninguém pedindo;
  3. upload: um daemon novo no PC baixa o pacote só do console;
  4. parado: 15 s.
Durante tudo, o console amostra CPU (ticks) e memória (RSS, PSS, privada, anônima) do motor a cada 1 s.
Os dois motores rodam com as mesmas opções: sem limite de download nem de upload, para medir a capacidade
do motor, e sem descoberta local. As rodadas alternam old/new para diluir variações do Wi-Fi.

No modo --discovery tracker, os peers se encontram por um tracker HTTP local no PC (tools/dev-tracker.py
do repositório KMP), igual para todos os motores; no modo addpeers (padrão do A/B), pelo kmp.addPeers.

Uso: bench.py CONSOLE_IP --runs 3 [--payload-mib 256] [--compare old,new | new,transmission]
                         [--discovery addpeers | tracker]
"""
import argparse
import base64
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REMOTE = "/roms/ports/.kmp-bench"
CONSOLE_RPC, CONSOLE_PORT = 36801, 45002
SEED_RPC, SEED_PORT = 46801, 45001
LEECH_RPC, LEECH_PORT = 46803, 45003
TUNNEL = 36901
SECRET = secrets.token_hex(8)
SLOW, LATENCY = [], {}
TRACKER_PORT = 6969
DISCOVERY = "addpeers"
KMP_REPO = Path.home() / "Documentos/GitHub/KMP"
_TR_SESSION = {}


def tr_rpc(port, method, arguments=None):
    """API do Transmission: a primeira chamada recebe 409 com o cabeçalho de sessão a reenviar."""
    body = json.dumps({"method": method, "arguments": arguments or {}}).encode()
    for _ in range(2):
        headers = {"Content-Type": "application/json", "X-Transmission-Session-Id": _TR_SESSION.get(port, "")}
        request = urllib.request.Request(f"http://127.0.0.1:{port}/transmission/rpc", body, headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                reply = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 409:
                _TR_SESSION[port] = error.headers.get("X-Transmission-Session-Id", "")
                continue
            raise
        if reply.get("result") != "success":
            raise RuntimeError(f"{method}: {reply.get('result')}")
        return reply.get("arguments", {})
    raise RuntimeError(f"{method}: sessão do Transmission recusada")


def wait_tr(port, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            return tr_rpc(port, "session-get", {"fields": ["version"]})
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Transmission na porta {port} não respondeu")


def transmission_settings(remote):
    """Padrões do Transmission, exceto o que precisa ser igual ao kmp-torrentd no teste."""
    return {
        "rpc-enabled": True, "rpc-port": CONSOLE_RPC, "rpc-bind-address": "127.0.0.1",
        "rpc-authentication-required": False, "rpc-whitelist-enabled": True, "rpc-whitelist": "127.0.0.1",
        "rpc-host-whitelist-enabled": False,
        "peer-port": CONSOLE_PORT, "peer-port-random-on-start": False,
        "download-dir": f"{remote}/run/data", "incomplete-dir-enabled": False,
        "speed-limit-down-enabled": False, "speed-limit-up-enabled": False, "alt-speed-enabled": False,
        "ratio-limit-enabled": False, "idle-seeding-limit-enabled": False,
        "dht-enabled": True, "pex-enabled": True, "utp-enabled": True, "lpd-enabled": False,
        "port-forwarding-enabled": True, "start-added-torrents": True, "message-level": 2,
    }


def log(*args):
    print(time.strftime("%H:%M:%S"), *args, flush=True)


class Console:
    def __init__(self, host, user="ark", password="ark"):
        self.host, self.user = host, user
        self.env = {**os.environ, "SSHPASS": password}
        self.base = ["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
                     f"{user}@{host}"]

    def run(self, command, check=True, timeout=120):
        result = subprocess.run(self.base + [command], env=self.env, capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(f"{command!r}: {result.stderr.strip()}")
        return result.stdout

    def put(self, local, remote):
        subprocess.run(["sshpass", "-e", "scp", "-q", "-o", "StrictHostKeyChecking=no", str(local),
                        f"{self.user}@{self.host}:{remote}"], env=self.env, check=True)

    def get(self, remote, local):
        subprocess.run(["sshpass", "-e", "scp", "-q", "-o", "StrictHostKeyChecking=no",
                        f"{self.user}@{self.host}:{remote}", str(local)], env=self.env, check=True)

    def tunnel(self):
        return subprocess.Popen(["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no", "-N",
                                 "-L", f"{TUNNEL}:127.0.0.1:{CONSOLE_RPC}", f"{self.user}@{self.host}"],
                                env=self.env)

    def clock_offset(self):
        before = time.time()
        remote = float(self.run("date +%s.%N"))
        after = time.time()
        return remote - (before + after) / 2


class LocalConsole(Console):
    """Ensaio no próprio PC, com binários x86 em local/, para validar o roteiro."""

    def __init__(self):
        self.host = "127.0.0.1"

    def run(self, command, check=True, timeout=120):
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(f"{command!r}: {result.stderr.strip()}")
        return result.stdout

    def put(self, local, remote):
        subprocess.run(["cp", str(local), remote], check=True)

    def get(self, remote, local):
        subprocess.run(["cp", remote, str(local)], check=True)

    def tunnel(self):
        return subprocess.Popen(["sleep", "100000"])

    def clock_offset(self):
        return 0.0


def rpc(port, method, *params):
    body = json.dumps({"jsonrpc": "2.0", "id": "b", "method": method,
                       "params": [f"token:{SECRET}", *params]}).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{port}/jsonrpc", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        reply = json.load(response)
    if reply.get("error"):
        raise RuntimeError(f"{method}: {reply['error']}")
    return reply["result"]


def wait_rpc(port, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            return rpc(port, "aria2.getVersion")
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"RPC na porta {port} não respondeu")


def lan_ip(target):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((target, 9))
        return sock.getsockname()[0]


def pc_daemon(name, rpc_port, listen_port, data_dir):
    state = HERE / "work" / name
    subprocess.run(["rm", "-rf", str(state)], check=True)
    state.mkdir(parents=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    out = open(state / "log.txt", "w")
    process = subprocess.Popen([str(HERE / "pc" / "kmp-torrentd"), f"--rpc-listen=127.0.0.1:{rpc_port}",
                                f"--rpc-secret={SECRET}", f"--state-dir={state}", f"--data-dir={data_dir}",
                                f"--listen-port={listen_port}", "--upload-limit=0", "--download-limit=0",
                                "--local-discovery=false"], stdout=out, stderr=out, start_new_session=True)
    wait_rpc(rpc_port)
    return process


def stop(process):
    if process and process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()


def wait_complete(port, gid, total, label, limit=900):
    first = None
    start = time.time()
    last_print = 0
    while time.time() - start < limit:
        asked = time.time()
        try:
            status = rpc(port, "aria2.tellStatus", gid)
        except (TimeoutError, OSError) as error:
            SLOW.append([label, asked, time.time() - asked, "falhou"])
            log(f"  {label}: status sem resposta ({error})")
            continue
        latency = time.time() - asked
        LATENCY.setdefault(label, []).append(latency)
        if latency > 2:
            SLOW.append([label, asked, latency, "lento"])
        done = int(status["completedLength"])
        if done > 0 and first is None:
            first = time.time()
        if done >= total and status.get("status") in ("complete", "active"):
            return start, first or start, time.time()
        if time.time() - last_print > 10:
            log(f"  {label}: {done / total:6.1%}  ↓{int(status['downloadSpeed']) / 1048576:5.2f} MiB/s")
            last_print = time.time()
        time.sleep(0.25)
    raise RuntimeError(f"{label}: não terminou em {limit} s")


def wait_seeder(port, gid, total, label, limit=900):
    """Acompanha o download do console pelo semeador no PC, sem tocar no Wi-Fi do console."""
    start, quiet, last_print = time.time(), 0, 0
    while time.time() - start < limit:
        status = rpc(port, "aria2.tellStatus", gid)
        sent, speed = int(status["uploadLength"]), int(status["uploadSpeed"])
        quiet = quiet + 1 if sent >= total * 0.98 and speed == 0 else 0
        if quiet >= 6:
            return
        if time.time() - last_print > 10:
            log(f"  {label}: PC enviou {sent / total:6.1%}  {speed / 1048576:5.2f} MiB/s")
            last_print = time.time()
        time.sleep(0.5)
    raise RuntimeError(f"{label}: não terminou em {limit} s")


def console_done_time(console, total):
    """Primeiro instante (relógio do console) em que o motor relatou o pacote completo."""
    rows = console.run(f"cat {REMOTE}/run/samples.jsonl")
    for line in rows.splitlines():
        row = json.loads(line)
        if row.get("rpc") and row.get("done", 0) >= total:
            return row["t"]
    return None


def prepare_payload(mib, tracker=None):
    payload = HERE / "work" / "seed-data" / f"kmp-bench-{mib}m.bin"
    torrent = HERE / "work" / (f"kmp-bench-{mib}m-tracker.torrent" if tracker else f"kmp-bench-{mib}m.torrent")
    if not payload.exists():
        payload.parent.mkdir(parents=True, exist_ok=True)
        log(f"gerando {mib} MiB aleatórios")
        with open(payload, "wb") as handle:
            for _ in range(mib):
                handle.write(os.urandom(1 << 20))
    if not torrent.exists():
        extra = ["--tracker", tracker] if tracker else []
        subprocess.run([sys.executable, str(KMP_REPO / "tools/make-file-torrent.py"),
                        str(payload), "--output", str(torrent), *extra], check=True, capture_output=True)
    return payload, torrent


def one_run(console, engine, run_index, torrent_b64, total, pc_ip, console_ip, results_dir):
    tag = f"{engine}-{run_index}"
    log(f"=== rodada {tag}")
    console.run(f"rm -rf {REMOTE}/run && mkdir -p {REMOTE}/run/state {REMOTE}/run/data {REMOTE}/run/tr-config")
    if engine == "transmission":
        settings = HERE / "work" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(transmission_settings(REMOTE), indent=1))
        console.put(settings, f"{REMOTE}/run/tr-config/settings.json")
        start = f"setsid ./transmission/run.sh -f -g {REMOTE}/run/tr-config"
        mode = "tr"
    else:
        flags = (f"--rpc-listen=127.0.0.1:{CONSOLE_RPC} --rpc-secret={SECRET} --state-dir={REMOTE}/run/state "
                 f"--data-dir={REMOTE}/run/data --listen-port={CONSOLE_PORT} --upload-limit=0 --download-limit=0")
        if engine == "new":
            # O console de 1 GB recebe esse teto do daemon.sh desde a 0.2.58; a 0.2.56 não tinha a opção.
            flags += " --memory-limit=192 --local-discovery=false"
        start = f"setsid ./kmp-bench-{engine} {flags}"
        mode = "kmp"
    pid = console.run(f"cd {REMOTE}; {start} </dev/null >run/log.txt 2>&1 & echo $!").strip()
    console.run(f"cd {REMOTE} && (setsid python3 sampler.py {pid} run/samples.jsonl 1 {CONSOLE_RPC} {SECRET} {mode} </dev/null >/dev/null 2>&1 &)")
    tunnel = console.tunnel()
    seeder = leecher = None
    marks = {"engine": engine, "run": run_index, "offset": console.clock_offset(), "discovery": DISCOVERY}
    try:
        if engine == "transmission":
            marks["version"] = wait_tr(TUNNEL).get("version")
        else:
            marks["version"] = wait_rpc(TUNNEL).get("version")
        seeder = pc_daemon("seeder", SEED_RPC, SEED_PORT, HERE / "work" / "seed-data")
        seed_gid = rpc(SEED_RPC, "aria2.addTorrent", torrent_b64, [], {})
        wait_complete(SEED_RPC, seed_gid, total, "PC conferindo", 300)
        time.sleep(15)
        marks["idle0"] = [time.time() - 14, time.time()]

        if engine == "transmission":
            tr_rpc(TUNNEL, "torrent-add", {"metainfo": torrent_b64, "download-dir": f"{REMOTE}/run/data"})
        else:
            gid = rpc(TUNNEL, "aria2.addTorrent", torrent_b64, [], {"dir": f"{REMOTE}/run/data"})
            if DISCOVERY == "addpeers":
                rpc(TUNNEL, "kmp.addPeers", gid, [f"{pc_ip}:{SEED_PORT}"])
        added = time.time()
        wait_seeder(SEED_RPC, seed_gid, total, f"{tag} baixando")
        done_at = None
        for _ in range(60):
            done_at = console_done_time(console, total)
            if done_at:
                break
            time.sleep(5)
        if not done_at:
            raise RuntimeError(f"{tag}: o console não completou o download")
        marks["download"] = [added, added, done_at - marks["offset"]]
        stop(seeder)
        seeder = None
        start = time.time()
        time.sleep(45)
        marks["idle1"] = [start + 5, time.time()]

        leecher = pc_daemon("leecher", LEECH_RPC, LEECH_PORT, HERE / "work" / "leech-data")
        leech_gid = rpc(LEECH_RPC, "aria2.addTorrent", torrent_b64, [], {"dir": str(HERE / "work" / "leech-data")})
        if DISCOVERY == "addpeers":
            rpc(LEECH_RPC, "kmp.addPeers", leech_gid, [f"{console_ip}:{CONSOLE_PORT}"])
        marks["upload"] = list(wait_complete(LEECH_RPC, leech_gid, total, f"{tag} enviando"))
        stop(leecher)
        leecher = None
        subprocess.run(["rm", "-rf", str(HERE / "work" / "leech-data")])
        start = time.time()
        time.sleep(15)
        marks["idle2"] = [start + 3, time.time()]
    finally:
        stop(seeder)
        stop(leecher)
        tunnel.terminate()
        console.run(f"kill {pid} 2>/dev/null; sleep 3; kill -9 {pid} 2>/dev/null; true", check=False)
    console.get(f"{REMOTE}/run/samples.jsonl", results_dir / f"{tag}.samples.jsonl")
    console.get(f"{REMOTE}/run/log.txt", results_dir / f"{tag}.log.txt")
    marks["slow"] = [row for row in SLOW if row[0].startswith(tag)]
    marks["latency"] = {k: v for k, v in LATENCY.items() if k.startswith(tag)}
    (results_dir / f"{tag}.marks.json").write_text(json.dumps(marks))
    log(f"  {tag}: download {total / 1048576 / (marks['download'][2] - marks['download'][0]):.2f} MiB/s, "
        f"upload {total / 1048576 / (marks['upload'][2] - marks['upload'][0]):.2f} MiB/s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("console")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--payload-mib", type=int, default=256)
    parser.add_argument("--compare", default="old,new", help="dois motores entre old, new e transmission")
    parser.add_argument("--discovery", choices=("addpeers", "tracker"), default=None)
    args = parser.parse_args()
    engines = args.compare.split(",")
    if len(engines) != 2 or not set(engines) <= {"old", "new", "transmission"}:
        sys.exit("--compare precisa de dois motores entre old, new e transmission")

    global REMOTE, TUNNEL, DISCOVERY
    # O Transmission não tem como receber um peer pela API; nesse caso todos usam o tracker local.
    DISCOVERY = args.discovery or ("tracker" if "transmission" in engines else "addpeers")
    if DISCOVERY == "addpeers" and "transmission" in engines:
        sys.exit("o Transmission só funciona com --discovery tracker")
    binaries = HERE
    if args.console == "local":
        console, REMOTE, TUNNEL, binaries = LocalConsole(), str(HERE / "work" / "local-console"), CONSOLE_RPC, HERE / "local"
        args.console = "127.0.0.1"
    else:
        console = Console(args.console)
    busy = console.run("pgrep -x kmp-torrentd; pgrep -x transmission-da || true").strip()
    if busy and not isinstance(console, LocalConsole):
        sys.exit(f"o kmp-torrentd do KMP está rodando no console (pid {busy}); feche o KMP antes do teste")
    console.run(f"mkdir -p {REMOTE}")
    for engine in engines:
        if engine == "transmission":
            subprocess.run(["sshpass", "-e", "scp", "-q", "-r", "-o", "StrictHostKeyChecking=no",
                            str(binaries / "transmission"), f"{console.user}@{console.host}:{REMOTE}/"],
                           env=console.env, check=True) if not isinstance(console, LocalConsole) else \
                subprocess.run(["cp", "-r", str(binaries / "transmission"), f"{REMOTE}/"], check=True)
            console.run(f"chmod +x {REMOTE}/transmission/run.sh {REMOTE}/transmission/transmission-daemon "
                        f"{REMOTE}/transmission/lib/ld-musl-*.so.1")
        else:
            console.put(binaries / engine / "kmp-torrentd", f"{REMOTE}/kmp-bench-{engine}")
            console.run(f"chmod +x {REMOTE}/kmp-bench-{engine}")
    console.put(HERE / "sampler.py", f"{REMOTE}/sampler.py")
    info = console.run("uname -r; grep MemTotal /proc/meminfo; cat /proc/device-tree/model 2>/dev/null | tr -d '\\0'; echo; "
                       "grep -c ^processor /proc/cpuinfo; df -m /roms | tail -1")
    pc_ip = lan_ip(args.console)
    tracker = None
    if DISCOVERY == "tracker":
        (HERE / "work").mkdir(parents=True, exist_ok=True)
        tracker_log = open(HERE / "work" / "tracker.log", "w")
        tracker = subprocess.Popen([sys.executable, str(KMP_REPO / "tools/dev-tracker.py"), "--port", str(TRACKER_PORT)],
                                   stdout=tracker_log, stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(1)
    payload, torrent = prepare_payload(args.payload_mib, f"http://{pc_ip}:{TRACKER_PORT}/announce" if tracker else None)
    total = payload.stat().st_size
    torrent_b64 = base64.b64encode(torrent.read_bytes()).decode()
    results = HERE / "results" / f"{args.console.replace('.', '_')}-{time.strftime('%Y%m%d-%H%M%S')}"
    results.mkdir(parents=True)
    (results / "console.txt").write_text(info)
    log(f"console {args.console}, PC {pc_ip}, pacote {args.payload_mib} MiB, {engines[0]} × {engines[1]}, "
        f"descoberta {DISCOVERY}, resultados em {results}")
    first, second = engines
    order = []
    for index in range(args.runs):
        order += [(first, index), (second, index)] if index % 2 == 0 else [(second, index), (first, index)]
    try:
        for engine, index in order:
            one_run(console, engine, index, torrent_b64, total, pc_ip, args.console, results)
    finally:
        stop(tracker)
    console.run(f"rm -rf {REMOTE}/run", check=False)
    log("fim")


if __name__ == "__main__":
    main()
