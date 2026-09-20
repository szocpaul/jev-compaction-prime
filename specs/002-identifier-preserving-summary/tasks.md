# Tasks: Azonosító-megtartó összefoglaló recovery-pointerrel

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Prerequisites**: plan.md ✅ (jóváhagyva), spec.md ✅ (jóváhagyva); a spec 001 fixture-ái és mérőscriptjei a repóban (`tests/fixtures/transcripts/`, `scripts/baseline_loss.py`, `baseline_loss.json`)

**Tilalmak a végrehajtónak**: a MANUÁLIS KAPU-t (T110) NE pipáld; a meglévő summarizer-viselkedést a summary szövegén TÚL ne módosítsd (FR-005); a fixture-áiratokhoz NE nyúlj; a méréseknél cache TILOS; ha a Prime Agent dist-beli prompt-felület eltér a baseline által replikálttól → állj meg és jelentsd.

*(A task-számok T101-től indulnak, hogy ne ütközzenek a spec 001 T001–T016 azonosítóival.)*

---

## Phase 1: User Story 1 — Azonosító-megtartás (P1)

**Goal**: determinisztikus azonosító-kigyűjtés + a tömörített kimenetbe illesztés.

**Independent Test**: `pytest -q tests/test_identifiers.py` → exit 0 (SC-001, SC-004).

### Tesztek (ELŐBB, és bukjanak el implementáció előtt)

- [ ] T101 [P] [US1] `tests/test_identifiers.py`: kigyűjtés a fixture-ökön (útvonalak, hibaüzenet-töredékek, parancsok verbatim); dedup hivatkozásszámlálóval; korlát-eldobás sorrendje (legalacsonyabb hivatkozás → legrégebbi).
- [ ] T102 [P] [US1] Titok-szűrés teszt: a `tests/fixtures/secrets/` beültetett credential-mintái (Bearer, api_key=, password=, privát kulcs) sosem kerülnek a listába (SC-004).

### Implementáció

- [ ] T103 [US1] `compaction/identifiers.py`: `extract_identifiers(transcript) -> list[Identifier]` — regex/heurisztika, verbatim, dedup + számláló, titok-szűrés, ~2000 token korlát dokumentált eldobási sorrenddel (plan KD-1..KD-4).
- [ ] T104 [US1] `compaction/patch_summary.py`: a tömörített kimenet összeállítása = summary + azonosító-lista (+ pointer a Phase 2-ből); a meglévő summary-rész bájthelyesen változatlan (FR-005).
- [ ] T105 [US1] Esemény-rekord (FR-006): tömörítésenként lista-méret, eldobott azonosítók száma, méretarány — JSONL-logba.

**Checkpoint**: US1 önállóan zöld; a lista LLM-hívás nélkül, determinisztikusan reprodukálható.

---

## Phase 2: User Story 2 — Recovery-pointer (P2)

**Goal**: minden tömörített kimenetben fix pointer-blokk (előzmény-útvonal + keresési mód).

**Independent Test**: `pytest -q tests/test_pointer.py` → exit 0 (SC-003).

- [ ] T106 [P] [US2] `tests/test_pointer.py`: a pointer-blokk minden kimenetben jelen van, tartalmazza a session-fájl abszolút útvonalát és a keresési instrukciót (SC-003).
- [ ] T107 [US2] `compaction/pointer.py`: `recovery_pointer(session_path) -> str` fix formátum; integráció a `patch_summary.py`-be (plan KD-5).

**Checkpoint**: US1+US2 együtt zöld.

---

## Phase 3: Validáció + zárás

- [ ] T108 `scripts/identifiers_loss.py`: az új kimenetet a 6 fixture-ön méri a `baseline_loss.json` módszertanával (per-átirat × per-modell, cache nélkül): closed-book azonosító-veszteség ≤5% (SC-001) és méretnövekedés ≤+15% (SC-002); kimenet `identifiers_loss.json`.
  - Előfeltétel: a summarizer-modellek pinnelve (a spec 001 meta-blokkja szerint); modellcsere = az egész mérés újra.
- [ ] T109 A spec 001 verbatim-adapterének (`compaction/` félkész Phase 1 kód) sorsa: törlés vagy külön ág — a git-history megőrzi, a main-ből távozik.
- [ ] T110 **MANUÁLIS KAPU**: a felhasználó review-zza az `identifiers_loss.json`-t és a kódot; ha az SC-001 nem teljesül, a tradeoff-döntés (korlát-hangolás vs. elfogadás) az emberé, indoklással. Az agent NEM pipálhatja.
- [ ] T111 Zárás: Agent.md 2. bejegyzés (tények, döntések, gotchák — köztük a patch upstream-frissítési kockázata, backlog: korlát-hangolás ha kell), commit + push.

---

## Dependencies & Execution Order

- T101/T102 buknak implementáció előtt; T103 → T104 sorrend; T105 párhuzamosítható T104-gyel.
- Phase 2 független Phase 1-től a pointer-szövegig; az integráció (T107) T104 után.
- T108 csak T101–T107 után; T110 emberi kapu; T111 utolsó.

## Validation Checklist

- [ ] FR-001 → T103; FR-002 → T103, T108; FR-003 → T106, T107; FR-004 → T102, T103; FR-005 → T104; FR-006 → T105.
- [ ] SC-001 → T101, T108; SC-002 → T108; SC-003 → T106; SC-004 → T102.
- [ ] Mindkét user story önállóan tesztelhető; az egyetlen MANUÁLIS KAPU (T110) explicit.
