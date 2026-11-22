#!/usr/bin/env python3
"""Monta um transmission-daemon portátil a partir dos pacotes do Alpine Linux.

Uso: fetch-transmission.py [aarch64|x86_64] DESTINO   (padrão: aarch64 transmission)

Resolve as dependências pelo APKINDEX, baixa os .apk por HTTPS, extrai o executável e as bibliotecas
musl e escreve DESTINO/run.sh, que roda o daemon pelo carregador musl incluído, sem instalar nada.
"""
import gzip
import io
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ALPINE = "https://dl-cdn.alpinelinux.org/alpine/v3.22"
ROOT_PACKAGE = "transmission-daemon"
RUN_SH = """#!/bin/sh
# Roda o transmission-daemon do Alpine (musl) com as bibliotecas desta pasta, sem tocar no sistema.
here=$(cd "$(dirname "$0")" && pwd)
exec "$(ls "$here"/lib/ld-musl-*.so.1 | head -1)" --library-path "$here/lib" "$here/transmission-daemon" "$@"
"""


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def index(arch):
    packages, provides = {}, {}
    for repo in ("main", "community"):
        with tarfile.open(fileobj=io.BytesIO(fetch(f"{ALPINE}/{repo}/{arch}/APKINDEX.tar.gz"))) as archive:
            text = archive.extractfile("APKINDEX").read().decode()
        for block in text.split("\n\n"):
            fields = {}
            for line in block.splitlines():
                if len(line) > 2 and line[1] == ":":
                    fields.setdefault(line[0], line[2:])
            if "P" not in fields:
                continue
            name = fields["P"]
            packages[name] = {"version": fields["V"], "repo": repo, "depends": fields.get("D", "").split()}
            provides.setdefault(name, name)
            for item in fields.get("p", "").split():
                provides.setdefault(item.split("=")[0], name)
    return packages, provides


def resolve(packages, provides):
    wanted, seen = [ROOT_PACKAGE], []
    while wanted:
        dependency = wanted.pop()
        if dependency.startswith("!"):
            continue
        for separator in "<>=~":
            dependency = dependency.split(separator)[0]
        name = provides.get(dependency)
        if not name or name in seen or name.startswith("busybox"):
            continue
        seen.append(name)
        wanted += packages[name]["depends"]
    return seen


def only_binaries(member, path):
    """Extrai só o daemon e as bibliotecas, com o filtro de segurança do tarfile; o resto é ignorado."""
    if not (member.name.startswith(("lib/", "usr/lib/")) or member.name == "usr/bin/transmission-daemon"):
        return None
    try:
        return tarfile.data_filter(member, path)
    except tarfile.FilterError:
        return None


def main():
    arch = sys.argv[1] if len(sys.argv) > 1 else "aarch64"
    destination = Path(sys.argv[2] if len(sys.argv) > 2 else "transmission")
    packages, provides = index(arch)
    names = resolve(packages, provides)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name in names:
            info = packages[name]
            data = fetch(f"{ALPINE}/{info['repo']}/{arch}/{name}-{info['version']}.apk")
            # Um .apk são vários gzip concatenados (assinatura, controle e dados), cada um com seu tar.
            with tarfile.open(fileobj=io.BytesIO(gzip.decompress(data)), mode="r:", ignore_zeros=True) as archive:
                archive.extractall(root, filter=only_binaries)
        shutil.rmtree(destination, ignore_errors=True)
        (destination / "lib").mkdir(parents=True)
        shutil.copy2(root / "usr/bin/transmission-daemon", destination)
        loader = next((root / "lib").glob("ld-musl-*.so.1"))
        shutil.copy(loader, destination / "lib" / loader.name)
        shutil.copy(loader, destination / "lib" / loader.name.replace("ld-musl", "libc.musl"))
        for library in (root / "usr/lib").glob("*.so.*"):
            if library.name.rsplit(".so.", 1)[1].isdigit():
                shutil.copy(library.resolve(), destination / "lib" / library.name)
    (destination / "run.sh").write_text(RUN_SH)
    (destination / "run.sh").chmod(0o755)
    (destination / "VERSIONS.txt").write_text("".join(f"{n} {packages[n]['version']}\n" for n in names))
    print(f"{destination}: {ROOT_PACKAGE} {packages[ROOT_PACKAGE]['version']} ({arch}), {len(names)} pacotes")


if __name__ == "__main__":
    main()
