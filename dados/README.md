# Dados das medições

Gerados pelos scripts de `../scripts/benchmark/`. Cada experimento tem dois arquivos: o resumo por rodada e as amostras segundo a segundo.

| Arquivo | Experimento | Seção do artigo |
|---|---|---|
| `teste-ab-2026-11-20.csv` | Motor e interface da 0.2.56 contra a 0.2.60, no console 192.168.0.98, com descoberta pelo `kmp.addPeers` | Consumo de recursos (Q1) |
| `teste-ab-2026-11-20-amostras.csv` | Amostras do mesmo teste | Q1 |
| `kmp-vs-transmission-2026-11-22.csv` | kmp-torrentd 0.2.8 contra transmission-daemon 4.0.6, no console 192.168.0.57, com descoberta pelo tracker local | Comparação com um cliente de uso geral (Q3) |
| `kmp-vs-transmission-2026-11-22-amostras.csv` | Amostras do mesmo teste | Q3 |

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
