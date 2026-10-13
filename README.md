# LawCodex — El Salvador (sv)

Salvadoran legislation as Markdown, from the documentation centre of the **Asamblea
Legislativa** ("Leyes y Decretos", https://www.asamblea.gob.sv/leyes-y-decretos): the
**Constitución de la República (1983)**, **codes**, **laws**, **legislative decrees**,
and **regulations** recorded there, each with the text of the PDF the Asamblea
publishes for it.

Part of [LawCodex](https://github.com/LawCodex): one public repository per jurisdiction.

Retrieved: **2026-10-13**. Language: Spanish (`es`).

Status: **full for the records of the Asamblea Legislativa's documentation centre (consolidated texts where amended)**

## What is covered

| Category (record type) | Directory | Files |
|---|---|---|
| Constitución | `constitucion/` | 1 |
| Códigos | `codigos/` | 12 |
| Leyes | `leyes/<year>/` | 651 |
| Decretos (legislative decrees of every kind) | `decretos/<year>/` | 5,013 |
| Reglamentos | `reglamentos/<year>/` | 1 |

`<year>` is the year of the decree (Fecha de Emisión). For laws and codes that have been amended,
the documentation centre's PDF is a consolidated text: the reformed provisions are inserted
(often in capitals) and an *índice legislativo* at the end lists the amending decrees.
`status` is left `unknown` because the record does not state it. Front matter includes the
Diario Oficial reference (number, tomo, date), the subject (`materia`), and the Asamblea's
summary is quoted under the title.

The record pages /view/1 … /view/9000 yield 5,767 records; 5,678 PDFs were converted, 5 are
scans without text layer and 84 records have no PDF. Many PDFs carry a few bytes before the
PDF header; these are stripped before parsing.

## What is NOT covered

- The few records whose PDF is a scanned image or missing (see above) — no OCR.
- Executive decrees and other norms not issued by the Asamblea.

## Source

Record pages `https://www.asamblea.gob.sv/leyes-y-decretos/view/<id>` (ids 1 … ~8,000) and the
linked PDFs (`/sites/default/files/documents/decretos/...`). The server does not send its
intermediate TLS certificate; the scripts add Sectigo's intermediate (fetched from the
certificate's AIA URL) to the CA bundle so that verification still happens.

## Copyright

El Salvador's Ley de Propiedad Intelectual excludes official texts (laws, decrees, judicial
decisions) from copyright protection.

## Regenerate

```
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
RAW=/path/to/scratch .venv/bin/python scripts/sv_fetch.py all
```

robots.txt allows these paths; up to 3 parallel connections at 1 request/s each.
