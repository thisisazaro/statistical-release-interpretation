# US payrolls rose by 73,000. Why was the published level 185,000 below June’s first estimate?

Evgenii Azarov · StatGazer methods note · version 1.0.1

Seasonally adjusted U.S. nonfarm payroll employment. Both figures start from the July level in the August 1, 2025 release, 159,539,000 jobs. Each uses a different base.

**+73,000 jobs.** July minus the revised June level in that same [August 1, 2025 release](https://www.bls.gov/news.release/archives/empsit_08012025.htm). The base is the revised June estimate, 159,466,000 jobs.

**−185,000 jobs.** July minus the first June estimate in the [July 3, 2025 release](https://www.bls.gov/news.release/archives/empsit_07032025.htm). The base is that first June estimate, 159,724,000 jobs.

[Read the note in the browser](https://github.com/thisisazaro/statistical-release-interpretation/blob/v1.0.1/methods-note.md) · [Download the PDF](https://github.com/thisisazaro/statistical-release-interpretation/releases/download/v1.0.1/methods-note.pdf) · [Source tables](https://github.com/thisisazaro/statistical-release-interpretation/blob/v1.0.1/examples.md)

## What the model replied

The direct prompt asked how payrolls changed from June to July inside the August 1 release. The saved reply in `model/responses/3d765f7ee428.json` uses the subtraction C − B = +73 and begins with the word «Ниже».

> Ниже на 73 thousand jobs.  
> Ячейки: C − B = +73.

```sh
./reproduce.sh
```

## What this check can support

Seven specially selected pairs of releases were studied: 14 questions and 28 saved answers from one model, Qwen3-4B (Q4_K_M), under two prompt variants. In the four pairs where the questions required opposite directions, the model gave both answers the same direction under each prompt variant. A programmed sentence template, with the comparison base fixed in advance, gave 14 correct answers out of 14. The frequency of this error in the ordinary stream of publications is unknown.

The score table, including magnitude, units, and the named pair of cells, is in [results.md](results.md). The questions, the two prompts, the denominators, and the rules for an ambiguous reply were written down before the replies, in [protocol.md](protocol.md).

## Check the saved answers

This operation reads the replies already stored in the repository. It uses Python 3.10 or later (the standard library, including `decimal`), Poppler’s `pdftotext`, and `shasum`. It does its work offline: the 14 archived releases are in this folder.

From the repository root:

```sh
./reproduce.sh
```

The script re-reads the table rows from the 14 archived releases, checks the Bureau of Labor Statistics files and the Federal Reserve files, matches them to the reference levels and the client sentences, rebuilds the prompts, and checks the scores against the saved replies and the rating log.

## Run the model again

This operation is optional. It asks the model for new replies. The saved answers were produced on an Apple M4 with 24 GiB of memory, macOS 27.2.1, and Metal.

On Apple Silicon macOS, start the local server in one terminal:

```sh
./model/start.sh
```

The script checks the SHA-256 of llama.cpp release b8177 and of the Qwen3-4B Q4_K_M weights. When a file is missing it downloads that file from its public source, then listens only on 127.0.0.1:18197. The runtime and the weights stay in the local cache. They are not part of this repository.

In a second terminal:

```sh
python3 -B experiment.py run --outdir rerun/responses
python3 -B experiment.py blind --outdir rerun/responses
```

New replies and the blinded text are written under `rerun/`. The saved observations remain in `model/`. Stop the server with Ctrl-C. Greedy decoding fixes the token-selection rule. A different compute kernel or driver can still change the text where two token scores tie.

To rate a new run, read only `rerun/blind.json` and record the direction, the magnitude, the unit, and the named pair of cells. The prompt variant is in `model/requests.json`, to be opened after the rating.

## Files

| Path | Contents |
| --- | --- |
| [methods-note.md](methods-note.md), [methods-note.pdf](methods-note.pdf) | The methods note. The PDF is one page. |
| [examples.md](examples.md) | Seven pairs, the subtractions, 14 client sentences, and links to each official table and the local copy. The worked examples are in Russian, the language of the prompts and the saved replies. |
| [protocol.md](protocol.md) | Protocol fixed on 22 November 2026, before the replies. |
| [results.md](results.md) | Scores for the saved replies and for the sentence template. |
| [reference.py](reference.py) | Reference answers. The client’s choice arrives as `monthly` or `since`, so the base is fixed before the sentence is written. |
| [experiment.py](experiment.py), [score.py](score.py), [reproduce.sh](reproduce.sh) | Prompts, scoring, and the offline check. |
| [bls/manifest.json](bls/manifest.json) | Six Employment Situation PDFs. Release dates: 4 October 2024, 1 November 2024, 7 February 2025, 7 March 2025, 3 July 2025, and 1 August 2025. Each row records the BLS release page, a FRASER copy, the local file, and its SHA-256. |
| [g17/](g17/README.md) | Eight G.17 summaries: 17 January 2024, 15 February 2024, 18 March 2025, 16 April 2025, 15 August 2025, 16 September 2025, 16 April 2026, and 15 May 2026. The folder also holds the release calendar, the revision documentation, and the vintage archive. Those snapshots were checked on 22 November 2026. |
| [model/packets.json](model/packets.json), [model/requests.json](model/requests.json) | The document excerpts and the 28 requests, in run order. |
| [model/responses/](model/responses/) | The 28 raw replies from the local server. |
| [model/blind.json](model/blind.json), [model/ratings.json](model/ratings.json) | Blinded phrases and the rating log. |
| [model/design.sha256](model/design.sha256) | SHA-256 of the locked design files. |
| [model/start.sh](model/start.sh) | Optional local server for a new run. |
| [CITATION.cff](CITATION.cff) | Citation metadata for version 1.0.1. |

The July 3 and August 1 payroll tables used above are also stored as [employment-situation-2025-07-03.pdf](bls/releases/employment-situation-2025-07-03.pdf) and [employment-situation-2025-08-01.pdf](bls/releases/employment-situation-2025-08-01.pdf).

## Use and attribution

The methods note, this README, the protocol, the worked examples, the results commentary, and the checking code are by Evgenii Azarov. They are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribute the note as: Evgenii Azarov, StatGazer, “US payrolls rose by 73,000. Why was the published level 185,000 below June’s first estimate?”, version 1.0.1, <https://github.com/thisisazaro/statistical-release-interpretation>.

The six PDFs in `bls/releases/` are publications of the U.S. Bureau of Labor Statistics. BLS states that material on its website is in the public domain unless otherwise noted, and it asks to be cited: <https://www.bls.gov/bls/copyright.htm>. `bls/manifest.json` also records a FRASER copy for each release. FRASER is a service of the Federal Reserve Bank of St. Louis.

The files in `g17/releases/`, together with `g17/release-calendar.html`, `g17/revision-documentation.html`, and `g17/revision-vintages.txt`, are publications of the Board of Governors of the Federal Reserve System. The Board’s website terms are at <https://www.federalreserve.gov/disclaimer.htm>.

Those agency files are included so the check can be repeated. The CC BY 4.0 license applies to the author’s materials. It does not apply to the Bureau of Labor Statistics files, the Federal Reserve files, or the FRASER copies, and it does not change their status. Cite the Bureau of Labor Statistics, the Board of Governors of the Federal Reserve System, or FRASER, as appropriate.

## Cite this note

Citation metadata for GitHub and reference managers is in [CITATION.cff](CITATION.cff).
