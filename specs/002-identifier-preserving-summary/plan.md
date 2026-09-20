# Implementation Plan: Azonosító-megtartó összefoglaló recovery-pointerrel

**Branch**: `002-identifier-preserving-summary` | **Date**: 2026-09-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-identifier-preserving-summary/spec.md`

## Summary

A meglévő összefoglaló-compaction kimenetét két determinisztikus elemmel egészítjük ki: (1) az áiratból **szabályosan kigyűjtött, verbatim azonosító-lista** (útvonalak, hibaüzenetek, parancsok — deduplikálva, korlátozva, titok-szűrve), és (2) egy **fix recovery-pointer blokk** (az előzmény-fájl útvonala + keresési mód). Nincs új szolgáltatás, nincs LLM-pontozás — a változás a compaction-prompt/kimenet összeállításában történik.

## Technical Context

**Language/Version**: TypeScript/Node (a Prime Agent dist-jének prompt-összeállítása) + Python 3.11 (mérés/validáció, a spec 001 fixture-infrastruktúrája)

**Primary Dependencies**: a Prime Agent summarization-promptja (`SUMMARIZATION_SYSTEM_PROMPT` / `SUMMARIZATION_PROMPT` a dist-ben — a baseline-scriptek már innen replikálták); nincs új külső függőség

**Storage**: spec 001 fixture-átiratai (`tests/fixtures/transcripts/`, 6 db) + mérési kimenetek (`identifiers_loss.json`)

**Testing**: `pytest -q` (azonosító-kigyűjtés egységtesztek + SC-gate-ek)

**Target Platform**: a Prime Agent futtatókörnyezete (szerver, Linux)

**Project Type**: harness-bővítés (prompt/kimenet-módosítás + mérés)

**Constraints**: summary + lista ≤ +15% méret (SC-002); az azonosító-kigyűjtés determinisztikus, LLM-hívás nélkül

## Constitution Check

A célrepóban továbbra sincs constitution — a kapu **kihagyva, jelölve** (ugyanaz az állapot, mint spec 001-nél).

## Architecture

```
JSONL-átirat
  │
  ├─► (meglévő) summarizer LLM ──► summary szöveg        ← változatlan
  │
  ├─► (ÚJ) identifier_extractor ──► azonosító-lista      ← determinisztikus:
  │     regex/heurisztika, dedup + hivatkozásszámláló,      regex + számláló
  │     titok-szűrés, méretkorlát + eldobási sorrend
  │
  ├─► (ÚJ) recovery_pointer(session_path)               ← fix szövegblokk
  │
  ▼
kimenet = summary + azonosító-lista + recovery-pointer
  │
  ▼
esemény-rekord (FR-006): lista-méret, eldobott azonosítók, méretarány
```

## Key Decisions

1. **Az azonosító-kigyűjtés determinisztikus (regex/heurisztika), nem LLM-es** — a verbatim-ság így konstrukció szerint garantált (nem a modell jóindulatán múlik), nulla extra token-költség, és egységtesztelhető. (Alternatíva: LLM kéri le a listát — elvetve; pont az LLM-asszociáció okozza a baseline-veszteséget.)
2. **A lista hivatkozásszámlálóval deduplikál** — a gyakran hivatkozott útvonalak értékesebbek; az eldobási sorrend így mérhető és reprodukálható. (Alternatíva: egyszerű recency-sorrend — elvetve; a régi, de sokat hivatkozott fájl (pl. konfig) kiesne.)
3. **Méretkorlát: az azonosító-lista ≤ ~2000 token (≈50–80 tétel), eldobás: legalacsonyabb hivatkozásszám, majd legrégebbi** — a spec SC-002 (+15%) mellett ez a konkrét felső határ; a validáció során mérjük, elég-e (ha nem, backlog: korlát-hangolás). (Alternatíva: dinamikus, summary-méretarányos korlát — elvetve v1-re; nehezebben tesztelhető.)
4. **A titok-szűrés engedélyező-lista helyett tiltó-mintás** (pl. `Bearer `, `api_key=`, `password=`, privát-kulcs-blokkok) — az azonosítók jellege előre nem enumerálható; a tiltó-minták a fixture-ökbe ültetett teszt-credentialokkal validáltak (SC-004). (Alternatíva: engedélyező-lista — elvetve; túl szűk, sok legális azonosítót dobna.)
5. **A recovery-pointer fix szöveg, minden tömörítésnél** — az élőblokk két sora: a session-fájl abszolút útvonala + a keresés módja (REPL/grep). Nem feltételes: ha nincs mit visszakeresni, akkor is ott van (a viselkedés egységes, tesztelhető). (Alternatíva: csak „ha volt eldobott tartalom" — elvetve; a feltételesség a baseline szerint gyakorlatilag mindig igaz, az egyszerűség nyer.)
6. **A módosítás a telepített Prime Agent summarization-összeállítására épül, vékony patch-ként** — a baseline-scriptek már bizonyították, hogy a promptok a dist-ből reprodukálhatók; a patch ugyanoda illeszkedik. (Alternatíva: fork — elvetve; az upstream-frissítések elvesznének.)

## Project Structure

```text
compaction/
├── identifiers.py         # azonosító-kigyűjtés (regex + dedup + titok-szűrés + korlát)
├── pointer.py             # recovery-pointer szövegblokk
└── patch_summary.py       # a summarization-kimenet összeállítása (summary + lista + pointer)

tests/
├── test_identifiers.py    # kigyűjtés, dedup, korlát, titok-szűrés (SC-004)
├── test_pointer.py        # pointer jelenlét és tartalom (SC-003)
├── fixtures/transcripts/  # spec 001 fixture-ök (változatlanul)
└── fixtures/secrets/      # beültetett credential-minták (SC-004)

scripts/
├── baseline_loss.py       # spec 001 (változatlan)
├── baseline_recovery.py   # spec 001 (változatlan)
└── identifiers_loss.py    # ÚJ: SC-001/SC-002 mérés a 6 fixture-ön, per-átirat × per-modell
```

**Structure Decision**: a spec 001 által kezdett `compaction/` + `scripts/` + `tests/` elrendezés folytatódik; a runner félkész Phase 1-es kódja (verbatim-adapter) NEM része ennek — külön ág/törlés a tasks.md dönti el.

## Phases

1. **Phase 1 (US1)**: `identifiers.py` (kigyűjtés, dedup, korlát, titok-szűrés) + tesztek + `patch_summary.py` összeállítás. Gate: SC-001, SC-004.
2. **Phase 2 (US2)**: `pointer.py` + integráció + tesztek. Gate: SC-003.
3. **Phase 3 — Validáció**: `identifiers_loss.py` futtatása a 6 fixture-ön (per-átirat × per-modell, a baseline_loss.json-nal összevetve) + SC-002 méretmérés + MANUÁLIS KAPU + napló/commit.
