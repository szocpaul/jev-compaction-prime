# Implementation Plan: Verbatim kontextus-tömörítés döntés-alapú eldobással

**Branch**: `001-verbatim-context-compaction` | **Date**: 2026-09-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-verbatim-context-compaction/spec.md`

## Summary

A Prime Agent összefoglaló-alapú compactionja mellé/ helyére egy döntés-alapú, verbatim tömörítés: a `fast-jev-compaction` npm-csomag (módszer: tool call/result pontozás, eldobás vagy csonkítás, szövegek érintetlenek) egy vékony Node stdin/stdout JSON-bridge-en keresztül kapcsolódik a Python-oldali adapterhez, amely a Prime Agent JSONL-átiratait fordítja a csomag `Message[]` formátumára és vissza. Hiba vagy küszöb alatti tömörítési arány esetén a meglévő összefoglaló-compaction lép életbe (fallback), warning-loggal.

## Technical Context

**Language/Version**: Python 3.11+ (adapter, Prime Agent oldal); Node.js 20+ / TypeScript (bridge)

**Primary Dependencies**: `fast-jev-compaction` npm-csomag (**pinnelt verzió** — lebegő alias tilos, verzióváltás = SC-004 baseline újramérés); TypeSafe/Jev API (`TYPESAFE_API_KEY`)

**Storage**: Prime Agent append-only JSONL session-átiratok; tömörítési esemény-rekordok JSONL/JSON-logban (FR-006)

**Testing**: `pytest -q` (adapter + invariáns-tesztek); a bridge-re npm `node --test` vagy a pytestből indított subprocess-tesztek

**Target Platform**: a Prime Agent futtatókörnyezete (szerver, Linux); a bridge ugyanott, on-demand subprocessként (nincs állandó node-daemon)

**Project Type**: harness-bővítés (adapter + külső bridge)

**Constraints**: a bridge csak a compaction trigger pillanatában fut; Jev request-limit ~32k token — a becslés ráhagyásának mértéke a spec `[NEEDS CLARIFICATION]`-e, **ebben a planban dől el** (lásd Key Decisions 4)

**Scale/Scope**: tipikus session 80–150 tool call, 60–120 perc; baseline-mérés ≥5 valós áiraton (SC-004)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

A célrepó még nem létezik (a felhasználó hozza létre), constitution-fájl nincs → a kapu **kihagyva, jelölve**. Amint a repó és a constitution létezik, az első újraellenőrzésnél pótolnivaló. A plan a playbook-overlay szabályaival (baseline-előbb, MANUÁLIS KAPU, exit-code gate-ek) konzisztens.

## Architecture

```
Prime Agent (Python)
  │
  │ compaction trigger (küszöb vagy compact.run())
  ▼
adapter.py ── JSONL-átirat ──► Message[] (call/result párosítás, pinned-ablak)
  │                                   │
  │ subprocess: stdin (JSON)          │
  ▼                                   ▼
compact-server.mjs ── compactMessages() ──► Jev API (pontozás, batch-elve)
  │ stdout (JSON: messages, decisions, stats)
  ▼
adapter.py ◄── döntés: ratio ≥ küszöb?
  │igen                    │nem / hiba
  ▼                        ▼
verbatim kimenet     FALLBACK: meglévő összefoglaló-compaction
(FR-001..004)        + warning-log (FR-005)
  │
  ▼
esemény-rekord (FR-006: stats, döntés-okok, arány) → mérési alap
```

## Key Decisions

1. **Node-bridge (subprocess JSON) a npm-csomag közvetlen használatára** — a `compactMessages()` upstream marad, frissítés `npm`-mel jön; a bridge ~25 sor, egy délután alatt elkészül. (Alternatíva: **Python-port** — elvetve, mert az aktívan fejlődő upstream minden javítását kézzel kellene utána vinni; újraindítási feltétel: ha a node-függőség a daemon-környezetben ténylegesen fáj, vagy az API stabilizálódik.)
2. **A Claude Code plugin (`hooks/`) NEM hordozható** — az Claude Code function-hook API-ra épül, Prime Agentben nincs ilyen belépési pont; csak az npm-csomagot (`src/`) használjuk. (Alternatíva: plugin-adapter — elvetve, technikailag lehetetlen.)
3. **A bridge on-demand subprocess, nem állandó szolgáltatás** — a daemon-ban nincs tartós node-processz; a compaction ritka esemény, a subprocess-overhead elhanyagolható a Jev API-költséghez képest. (Alternatíva: perzisztens HTTP-szerver — elvetve, felesleges lifecycle-kockázat.)
4. **Méretbecslési ráhagyás: a becsült state-limit a valódi limit 80%-a** (a spec NEEDS CLARIFICATION-ének eldöntése) — a karakteralapú becslés iránya és nagysága nem ismert előre; a 20% ráhagyás konzervatív, a validáció során mérjük a tényleges becslési hibát, és ha <10%, a ráhagyás csökkenthető. (Alternatíva: valódi tokenizer a bridge-ben — elvetve v1-re, extra függőség; a csomag request-szintű kalibrációja a saját becslésére épül, azt nem „javítjuk ki".)
5. **Részleges Jev-válasz = teljes hiba → fallback** — nem alkalmazunk félkész döntéshalmazt; az FR-005 fallback-ág olcsóbb, mint egy részlegesen tömörített kontextus hibája. (Alternatíva: részleges döntések alkalmazása konzervatív defaulttal — elvetve, nehezen tesztelhető viselkedés.)
6. **Az export/adapter (JSONL → Message[] és vissza) Pythonban, a Prime Agent oldalán** — a teljes integrációs munka ~70%-a ez (párosítás, pinned-ablak, fallback-logika, esemény-rekord); opciófüggetlen. (Alternatíva: az export a bridge-ben, TypeScriptben — elvetve, a JSONL-formátum a Python-oldal birtokában van.)

## Project Structure

### Documentation (this feature)

```text
specs/001-verbatim-context-compaction/
├── spec.md              # jóváhagyva
├── plan.md              # ez a fájl
└── tasks.md             # a tasks-fázis outputja
```

### Source Code (repository root)

```text
compaction/
├── adapter.py           # JSONL ↔ Message[] fordítás, párosítás, pinned-ablak, fallback-vezérlés
├── bridge/
│   ├── compact-server.mjs   # stdin/stdout JSON bridge a npm-csomagra
│   └── package.json         # fast-jev-compaction PINNELT verzióval
├── events.py            # FR-006 esemény-rekord írása
└── config.py            # küszöbök, pinned-ablak, ráhagyás (FR-004, FR-007, KD-4)

tests/
├── test_verbatim.py     # SC-001 gate
├── test_pairing.py      # SC-002 gate
├── test_fallback.py     # SC-003 gate
└── fixtures/transcripts/    # ≥5 rögzített valós áirat (SC-004 baseline)
```

**Structure Decision**: Single project; a `compaction/` modul a Prime Agent futtatókörnyezetébe illeszkedik, a bridge almappában, pinnelt npm-függőséggel. A meglévő összefoglaló-compaction kódjához NEM nyúlunk (spec Out of Scope).

## Phases

1. **Phase 0 — Baseline-mérés (SC-004 előfeltétel)**: ≥5 valós JSONL-átirat rögzítése változatlan környezetben; az összefoglaló-alapú compaction veszteségének számszerűsítése (hány később hivatkozott útvonal/hibaüzenet esik ki), per-átirat bontásban, fájlba írva. **Ez MINDEN változtatás előtt történik.**
2. **Phase 1 (US1)**: adapter (JSONL ↔ Message[], párosítás, pinned-ablak) + bridge (`compact-server.mjs`) + verbatim/párosítási tesztek (SC-001, SC-002).
3. **Phase 2 (US2)**: fallback-vezérlés (hiba, érvénytelen válasz, küszöb alatti arány) + warning-log + esemény-rekord (FR-005, FR-006) + fallback-tesztek (SC-003).
4. **Phase 3 — Validáció**: teljes pytest-csomag, SC-004 új tömörítéssel (veszteség = 0 a megtartott elemekben), SC-005 arány-mérés, naplóbejegyzés. A MANUÁLIS KAPU-kat a tasks.md jelöli.
