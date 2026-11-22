# Dados das medições

Gerados pelos scripts de `../scripts/benchmark/`. Cada experimento tem dois arquivos: o resumo por rodada e as amostras segundo a segundo.

| Arquivo | Experimento | Seção do artigo |
|---|---|---|
| `teste-ab-2026-11-20.csv` | Motor e interface da 0.2.56 contra a 0.2.60, no console 192.168.0.98, com descoberta pelo `kmp.addPeers` | Consumo de recursos (Q1) |
| `teste-ab-2026-11-20-amostras.csv` | Amostras do mesmo teste | Q1 |
| `kmp-vs-transmission-2026-11-22.csv` | kmp-torrentd 0.2.8 contra transmission-daemon 4.0.6, no console 192.168.0.57, com descoberta pelo tracker local | Comparação com um cliente de uso geral (Q3) |
| `kmp-vs-transmission-2026-11-22-amostras.csv` | Amostras do mesmo teste | Q3 |

| `conectividade-2026-11-22.csv` | De onde vieram os bytes de cada download do portátil 192.168.0.98, na mesma rede e nos dados móveis do celular | Conectividade entre consoles (Q2) |
| `conectividade-bruto/` | Registros do `conn_logger.py` e consultas de totais ao daemon, usados para gerar o CSV acima | Q2 |

**Conectividade** (gerado por `../scripts/conectividade/export_conn.py`): uma linha por caminho que entregou dados em cada download, com:
- o cenário e o pacote (Asphalt 5, Riptide GP ou Celeste 64);
- os minutos desde a troca de rede;
- a duração;
- o aparelho que enviou (nó público, PC/Publisher ou console antigo);
- a família (IPv4 ou IPv6) e o transporte (TCP ou uTP);
- a origem do peer (tracker, DHT, PEX, LPD, peer direto, hole punching ou entrada);
- os bytes e a fração do pacote.

**Privacidade:** os endereços IP públicos foram trocados por endereços de documentação (IPv4 em 203.0.113.0/24, IPv6 em 2001:db8::/32) pelo `../scripts/conectividade/anonymize.py`, sempre com o mesmo substituto para o mesmo endereço. O IP do nó público, que já é público, e os endereços da rede local ficaram como estão.

Os bytes vêm do `kmp.getPeerTotals` do kmp-torrentd 0.2.9-dev, que acumula também as conexões já encerradas. Na primeira rodada nos dados móveis, o registrador parou na troca de Wi-Fi; os totais foram lidos depois, direto do daemon, e o instante da troca veio do journal do console.

Os dois consoles têm o mesmo hardware: o processador do R36H e do R46H, com 1 GB de RAM (895 MB utilizáveis). Em cada rodada, o pacote é de 256 MiB de dados aleatórios, transferidos entre o console e um PC pela rede Wi-Fi doméstica, sem limite de banda.

**Resumo** (formato longo): uma linha por motor, rodada e métrica, com a unidade. A CPU está em porcentagem de um núcleo e a memória em MiB.

**Amostras:** uma linha por segundo, com:
- CPU acumulada em ticks (`ticks_por_s` por segundo);
- memória do motor em KiB, lida de `smaps_rollup`;
- `MemAvailable` do console;
- progresso e velocidades informados pela API do próprio motor.

`segundos` conta a partir do início do download, e `fase` marca as fases da rodada: `antes`, `download`, `entre`, `parado` e `envio`.

**Para regenerar a partir de uma execução do `bench.py`:**

```
python3 ../scripts/benchmark/export_csv.py ../scripts/benchmark/results/<pasta> <prefixo> 256 "<console>"
```

Exceção: o teste A/B de 2026-11-20 foi exportado antes do `export_csv.py` existir, por isso o formato das colunas dele é um pouco diferente. Os valores da CPU da interface vêm do `uicpu.py`.
