#!/usr/bin/env python3
"""Troca endereços IP públicos por endereços de documentação antes de publicar os registros.

Uso: anonymize.py ARQUIVO [ARQUIVO ...]   (altera os arquivos no lugar)

Cada IPv4 público vira um endereço de 203.0.113.0/24 (RFC 5737) e cada prefixo IPv6 global /64 vira um
prefixo de 2001:db8::/32 (RFC 3849), sempre o mesmo substituto para o mesmo endereço em todos os arquivos.
Ficam como estão: o nó público do catálogo (já público), endereços privados, CGNAT, link-local e ULA.
"""
import ipaddress
import re
import sys

KEEP = {"163.176.18.211"}  # nó público do KMP, anunciado no catálogo
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
IPV6 = re.compile(r"(?<![0-9A-Fa-f:])((?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{0,4}(?:::[0-9A-Fa-f:]*)?)(?![0-9A-Fa-f:])")


class Anonymizer:
    def __init__(self):
        self.v4, self.v6 = {}, {}

    def ipv4(self, match):
        text = match.group(1)
        try:
            address = ipaddress.IPv4Address(text)
        except ValueError:
            return text
        if text in KEEP or not address.is_global:
            return text
        if text not in self.v4:
            self.v4[text] = f"203.0.113.{len(self.v4) + 1}"
        return self.v4[text]

    def ipv6(self, match):
        text = match.group(1)
        try:
            address = ipaddress.IPv6Address(text)
        except ValueError:
            return text
        if not address.is_global:
            return text
        prefix = address.exploded.split(":")[:4]
        key = ":".join(prefix)
        if key not in self.v6:
            self.v6[key] = f"2001:db8:{len(self.v6) + 1:x}:0"
        host = ipaddress.IPv6Address(int(address) & ((1 << 64) - 1))
        return str(ipaddress.IPv6Address(f"{self.v6[key]}:{host.exploded[20:]}"))

    def text(self, value):
        return IPV4.sub(self.ipv4, IPV6.sub(self.ipv6, value))


def main():
    anonymizer = Anonymizer()
    for name in sys.argv[1:]:
        with open(name, encoding="utf-8") as handle:
            content = handle.read()
        with open(name, "w", encoding="utf-8") as handle:
            handle.write(anonymizer.text(content))
    print(f"{len(sys.argv) - 1} arquivos: {len(anonymizer.v4)} IPv4 públicos e {len(anonymizer.v6)} prefixos IPv6 substituídos")
    for original, new in list(anonymizer.v6.items())[:3]:
        print(f"  prefixo {original[:9]}… → {new}")


if __name__ == "__main__":
    main()
