# Experimento de conectividade (Q2)

Mede de onde chega cada byte que um console baixa: o nó público, outro console ou o PC com o Publisher. Para cada caminho, separa a família (IPv4 ou IPv6), o transporte (TCP ou uTP) e a origem do peer (tracker, DHT, PEX, descoberta local, peer passado pelo Client, hole punching ou conexão de entrada).

| Arquivo | Onde roda | O que faz |
|---|---|---|
| `conn_logger.py` | console | A cada 2 s, consulta o kmp-torrentd local e grava os totais por caminho, os contadores de descoberta e hole punching e os endereços de rede do console |
| `analyze_conn.py` | PC | Separa cada download de um pacote no registro e mostra os bytes por aparelho e caminho |
| `export_conn.py` | PC | Gera o CSV de `../../dados/conectividade-*.csv` a partir dos registros |

## Requisito: kmp-torrentd 0.2.9 ou posterior

Os totais por caminho vêm do `kmp.getPeerTotals`, que soma também as conexões já encerradas. Ele existe a partir do kmp-torrentd 0.2.9; no momento do experimento, era a versão de desenvolvimento do repositório [KMP](https://github.com/FerreiraTechLab/KMP).

Compile e instale no console, guardando o original:

```
cd ~/Documentos/GitHub/KMP/torrentd
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -ldflags='-s -w' -o kmp-torrentd-aarch64 ./cmd/kmp-torrentd
# no console, com o KMP fechado e o daemon parado:
#   cp /roms/ports/KMP/libs.aarch64/kmp-torrentd ~/kmp-torrentd.orig
#   cp kmp-torrentd-aarch64 /roms/ports/KMP/libs.aarch64/kmp-torrentd
```

## Protocolo usado em 22/11/2026

1. **Aparelhos:** o console A fica na rede doméstica, com o KMP aberto e o nó comunitário ligado (semeando). O PC fica na mesma rede, com o Publisher aberto. O nó público está no ar.
2. **Console B:** nó comunitário desligado no menu do KMP, para que o daemon não tenha os pacotes.
3. **Registrador no console B:** precisa sobreviver a dois encerramentos. A troca de Wi-Fi pelo menu do firmware mata processos da sessão, e o PortMaster roda `killall python3` ao sair de qualquer jogo. Por isso, inicie-o como serviço e com outro nome de processo:

   ```
   ln -s /usr/bin/python3 /roms/ports/.kmp-exp/kmp-connlog
   sudo systemd-run --unit=kmp-conn-logger --uid=ark /roms/ports/.kmp-exp/kmp-connlog conn_logger.py saida.jsonl 10800 2
   ```

4. **Na rede doméstica:** baixe Asphalt 5, Riptide GP e Celeste 64 pelo botão "Só P2P", que não usa espelhos HTTP e recria o torrent a cada vez.
5. **Na rede móvel do celular:** repita os downloads, anotando o horário da troca de rede.
6. **Análise:**

   ```
   python3 analyze_conn.py saida.jsonl <infohash> aparelhos.json
   python3 export_conn.py ../../dados/conectividade-<data>.csv aparelhos.json "cenário=saida.jsonl" ...
   ```

   O `aparelhos.json` identifica cada aparelho pela porta de escuta (exemplo em `../../dados/conectividade-bruto/`).

Se o registrador parar, os totais continuam no daemon enquanto o torrent existir. Dá para lê-los depois pelo `kmp.getPeerTotals` e exportar indicando o instante da troca de rede (`arquivo.json@INSTANTE`).
