# Teste A/B do consumo do KMP no console

Scripts usados em 20/11/2026 para comparar a 0.2.56 com a 0.2.60 num portátil de 1 GB de RAM, com o mesmo processador do R36H e do R46H. Os resultados estão em `KMP-Web/metrics-data/`; a pasta está no `.gitignore`.

| Arquivo | Onde roda | O que faz |
|---|---|---|
| `bench.py` | PC | Controla as rodadas: semeia ou baixa pelo PC, liga o motor no console por SSH e junta os resultados |
| `sampler.py` | console | A cada 1 s, registra a CPU (ticks), a memória (smaps_rollup), o MemAvailable e o progresso, pela API local do motor |
| `analyze.py` | PC | Mostra a mediana e a faixa por motor e grava `summary.json` |
| `uicpu.py` | console | Mede a CPU da interface (LÖVE) em janelas de 60 s |
| `export_csv.py` | PC | Exporta uma execução para o resumo e as amostras em CSV (ver `../../dados/`) |
| `fetch-transmission.py` | PC | Monta o transmission-daemon portátil a partir dos pacotes do Alpine |

## Preparação (no PC)

O `bench.py` procura os binários ao lado dele:

```
old/kmp-torrentd   # aarch64, de KMP/libs.aarch64 do KMP-v0.2.56.zip
new/kmp-torrentd   # aarch64, de KMP/libs.aarch64 do KMP-v0.2.60.zip
pc/kmp-torrentd    # x86_64, compilado do torrentd do repositório KMP:
                   # CGO_ENABLED=0 go build -o pc/kmp-torrentd ./cmd/kmp-torrentd
```

Ele também usa `~/Documentos/GitHub/KMP/tools/make-file-torrent.py` para criar o torrent do pacote sintético, e precisa do `sshpass`. O console é acessado como `ark`/`ark`.

## Execução

1. Ligue o console e deixe o KMP **fechado**. O script se recusa a rodar se o `kmp-torrentd` do KMP estiver ativo.
2. No PC:

   ```
   python3 bench.py 192.168.0.98 --runs 3 --payload-mib 256
   python3 analyze.py results/<pasta-da-execução> 256
   ```

Cada rodada passa por quatro fases:
1. o console baixa o pacote só do PC;
2. fica 45 s parado;
3. um daemon novo no PC baixa o pacote só do console;
4. fica mais 15 s parado.

As rodadas alternam old/new (old, new; new, old; …).

Os dois motores rodam com as mesmas opções: `--upload-limit=0 --download-limit=0`. O novo também recebe `--memory-limit=192`, como o `daemon.sh` faz nos consoles de até 1,5 GB, e `--local-discovery=false`, porque o antigo não tem descoberta local.

`python3 bench.py local --runs 1 --payload-mib 64` faz um ensaio no próprio PC. Ele exige binários x86 em `local/old` e `local/new`.

## Comparação com o Transmission (Q3)

```
python3 bench.py 192.168.0.98 --runs 3 --payload-mib 256 --compare new,transmission
```

O roteiro é o mesmo do A/B, com duas diferenças:

- **Descoberta pelo tracker.** O Transmission não tem um equivalente ao `kmp.addPeers`. Por isso, nesse modo, todos os participantes se encontram pelo tracker HTTP local do PC (`tools/dev-tracker.py` do repositório KMP, porta 6969, anúncio a cada 5 s), tanto o kmp-torrentd quanto o Transmission.
- **Configuração do Transmission.** Ele roda com a configuração padrão, exceto pelo que precisa ser igual ao kmp-torrentd: sem limite de banda e de proporção, descoberta local desligada, DHT, PEX, uTP e mapeamento de porta ligados. O `bench.py` escreve o `settings.json` (ver `transmission_settings`).

**Como montar o pacote do Transmission.** É o `transmission-daemon` 4.0.6 do Alpine Linux 3.22, com as bibliotecas musl de que precisa:

```
python3 fetch-transmission.py aarch64 transmission          # para o console
python3 fetch-transmission.py x86_64 local/transmission     # para o ensaio no PC
```

O script resolve as dependências pelo `APKINDEX` e baixa os `.apk` de `dl-cdn.alpinelinux.org`. Ele extrai só o executável e as bibliotecas, incluindo o carregador `ld-musl-*.so.1`, e escreve um `run.sh` que roda o daemon por esse carregador com `--library-path`, sem instalar nada no firmware. As versões ficam em `VERSIONS.txt`.

O `analyze.py` também separa o **tempo até o primeiro byte** da **velocidade contada a partir do primeiro byte**. No ensaio local, o Transmission levou cerca de 10 s para começar, e o kmp-torrentd menos de 1 s.

## Interface

Para medir a interface, troque só o `game.love` do console, guardando uma cópia do original. Abra o KMP, deixe parado na loja e rode no console:

```
python3 uicpu.py 3
```

## Cuidados

- **Sem consultas pelo Wi-Fi durante a transferência.** A transferência sem limite satura o Wi-Fi do console: o ping chegou a 850 ms. Por isso o progresso do download é lido pelo `sampler.py` no próprio console e pelo semeador no PC.
- **Sem `pkill -f` por SSH.** O padrão aparece na própria linha de comando e encerra a sessão; o script usa PIDs.
- **O relógio do console é diferente do PC.** O `bench.py` mede a diferença a cada rodada (`offset` em `*.marks.json`), e o `analyze.py` converte os tempos.
