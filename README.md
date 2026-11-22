# KMP-Artigo

Artigo e artefatos do **KMP** para o Salão de Ferramentas do SBRC 2027.

O KMP distribui pacotes para consoles portáteis Linux de baixo custo (aarch64, 1 GB de RAM) a partir de um catálogo assinado, por BitTorrent, com semeação comunitária entre os próprios aparelhos. Este repositório reúne o texto do artigo, os scripts das medições e os dados brutos, para que os resultados possam ser conferidos e reproduzidos.

| Ferramenta | Repositório |
|---|---|
| Client e daemon `kmp-torrentd` | https://github.com/FerreiraTechLab/KMP |
| Publisher | https://github.com/FerreiraTechLab/KMP-Publisher |
| Catálogo assinado | https://github.com/FerreiraTechLab/KMP-catalog |
| Releases | https://github.com/FerreiraTechLab/KMP-releases |
| Documentação | https://kpm-ferreiratechlab.web.app |

## Conteúdo

| Pasta | O que tem |
|---|---|
| [`artigo/`](artigo/) | Texto em LaTeX no modelo da SBC (`main.tex`, `referencias.bib`). As pendências aparecem em vermelho no PDF, pela macro `\pendente{}`. |
| [`scripts/benchmark/`](scripts/benchmark/) | Scripts das medições: o teste A/B do KMP 0.2.56 contra 0.2.60 e a comparação do kmp-torrentd com o transmission-daemon. Ver o [README](scripts/benchmark/README.md). |
| [`scripts/conectividade/`](scripts/conectividade/) | Registrador e análise de por onde chega cada byte, na mesma rede e entre redes diferentes. Ver o [README](scripts/conectividade/README.md). |
| [`dados/`](dados/) | Resultados em CSV, com o resumo por rodada e as amostras segundo a segundo. Ver o [README](dados/README.md). |

## Gerar o PDF

Requer TeX Live com `latexmk`:

```
cd artigo
latexmk -pdf main.tex
```

## Reproduzir as medições

Requisitos:
- um console portátil aarch64 com acesso por SSH (o roteiro usa o usuário padrão `ark`/`ark` do ArkOS e do dArkOS) e o KMP fechado;
- um PC Linux na mesma rede, com Python 3, Go e `sshpass`;
- uma cópia do repositório [KMP](https://github.com/FerreiraTechLab/KMP) em `~/Documentos/GitHub/KMP`.

```
cd scripts/benchmark
# Binários: ver "Preparação" no README do benchmark
python3 bench.py <IP do console> --runs 3 --payload-mib 256                               # A/B do KMP
python3 bench.py <IP do console> --runs 3 --payload-mib 256 --compare new,transmission    # KMP × Transmission
python3 analyze.py results/<pasta> 256
python3 export_csv.py results/<pasta> ../../dados/<prefixo> 256 "<console>"
```

Cada rodada leva de 3 a 5 minutos. O README do benchmark explica as fases, as opções usadas para deixar as condições iguais entre os motores e os cuidados que aprendemos ao medir.

## Principais resultados

Medidos num console com o processador do R36H e do R46H e 1 GB de RAM, em 3 rodadas por motor; os valores são medianas.

| | Resultado |
|---|---|
| KMP 0.2.56 → 0.2.60 | Memória do motor semeando (RSS): 271 → 27 MB, com a mesma memória anônima. CPU da interface parada: 34,9% → 5,1%. Velocidade de transferência sem perda. |
| Conectividade (Q2) | Na mesma rede, o outro console e o PC entregaram de 71% a 91% de cada pacote. Na rede móvel, o nó público entregou ~100% nos primeiros ~9 min após a troca de rede; depois, os aparelhos de casa passaram a entregar de 31% a 73%, por IPv6/uTP via DHT. |
| kmp-torrentd × Transmission 4.0.6 | O kmp começa a transferir em 0,4 s, contra 10,6 s, e gasta 146 contra 200 s de CPU por GiB baixado. O Transmission gasta menos parado: 0,7% contra 3,1% de CPU. |

## Licenças

- **Scripts** (`scripts/`): GNU GPL versão 3 ou posterior; ver [LICENSE](LICENSE).
- **Texto do artigo** (`artigo/main.tex`, `artigo/referencias.bib`) **e dados** (`dados/`): Creative Commons Atribuição 4.0 Internacional; ver [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0).
- **Modelo da SBC** (`artigo/sbc-template.sty`, `artigo/sbc.bst`, `artigo/modelo-sbc/`): arquivos da Sociedade Brasileira de Computação, incluídos só para compilar o artigo; não estão cobertos pelas licenças acima.
- **Ferramentas comparadas:** o transmission-daemon e as bibliotecas que o `fetch-transmission.py` baixa do Alpine Linux mantêm as próprias licenças, e não são distribuídos neste repositório.

Copyright (C) 2026 Weslei Ferreira Santos.
