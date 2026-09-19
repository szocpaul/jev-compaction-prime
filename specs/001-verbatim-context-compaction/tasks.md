# Tasks: Verbatim kontextus-tömörítés döntés-alapú eldobással

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Prerequisites**: plan.md ✅ (jóváhagyva), spec.md ✅ (jóváhagyva)

**Tilalmak a végrehajtónak**: a MANUÁLIS KAPU-kat NE pipáld; a meglévő összefoglaló-compaction kódjához NE nyúlj; a `fast-jev-compaction` verzióját NE változtasd a baseline rögzítése után (újramérés kötelező); ha a Jev API vagy az npm-csomag elérhetetlen → állj meg és jelentsd, ne improvizálj.

---

## Phase 0: Baseline-mérés (SC-004 előfeltétel — MINDEN változtatás előtt)

- [x] T001 Rögzíts ≥5 valós Prime Agent session-átiratot (JSONL) a `tests/fixtures/transcripts/` alá, változatlan környezetben; minden áirat 80–150 tool call-os legyen.
- [ ] T002 Írj `scripts/baseline_loss.py` scriptet: minden fixture-átiraton lefuttatja a meglévő összefoglaló-compactiont, és számszerűen rögzíti, hány később hivatkozott fájlútvonal/hibaüzenet esett ki — per-átirat bontásban, `baseline_loss.json`-be.
  - Kis mintás zajmérés: a mérést 2–3× ismételd ugyanazon áiratokon; az intervallumokat is rögzítsd.
- [ ] T003 **MANUÁLIS KAPU**: a felhasználó átnézi a `baseline_loss.json`-t, és jóváhagyja, hogy a diagnózis igazolódott (vagy a lánc megáll, ha a veszteség ≈ 0). Az agent NEM pipálhatja.

---

## Phase 1: User Story 1 — Verbatim tömörítés (P1)

**Goal**: JSONL → Message[] fordítás, bridge, verbatim/párosítási invariánsok teljesülnek.

**Independent Test**: `pytest -q tests/test_verbatim.py tests/test_pairing.py` → exit 0 (SC-001, SC-002).

### Tesztek (ELŐBB, és bukjanak el implementáció előtt)

- [ ] T004 [P] [US1] `tests/test_verbatim.py`: fixture-átiraton a megtartott elemek 100%-a bájthelyes, sorrend változatlan; a kimenetben nincs eredetiben nem létező szöveg (SC-001).
- [ ] T005 [P] [US1] `tests/test_pairing.py`: 0 árva eredmény, 0 árva hívás; pinned-ablak (első + utolsó N üzenet) mindig érintetlen (SC-002, FR-003, FR-004).

### Implementáció

- [ ] T006 [US1] `compaction/adapter.py`: JSONL-átirat → `Message[]` export (call/result párosítás `tool_use_id` szerint, pinned-ablak, első üzenet mindig pinned) és a tömörített `Message[]` visszafordítása.
- [ ] T007 [P] [US1] `compaction/bridge/compact-server.mjs` + `package.json`: stdin JSON → `compactMessages()` → stdout JSON (`messages`, `decisions`, `stats`); `fast-jev-compaction` **pinnelt verzió**.
- [ ] T008 [US1] `compaction/config.py`: küszöbök és pinned-ablak dokumentált alapértékekkel (FR-007); 20%-os becslési ráhagyás (plan KD-4).
  - Előfeltétel: preflight — `node --version`, npm-csomag telepítve, `TYPESAFE_API_KEY` beállítva; ha hiányzik → megállás + jelentés.

**Checkpoint**: US1 önállóan tesztelhető — a bridge subprocess mock-Jevvel is fut (élő API nélkül is zöld tesztek).

---

## Phase 2: User Story 2 — Megbízható visszaesés (P2)

**Goal**: minden hibaforrásra a meglévő compaction lép életbe, warning-loggal.

**Independent Test**: `pytest -q tests/test_fallback.py` → exit 0 (SC-003).

### Tesztek (ELŐBB)

- [ ] T009 [P] [US2] `tests/test_fallback.py`: szimulált hibák (elérhetetlen végpont, érvénytelen/részleges Jev-válasz, küszöb alatti tömörítési arány, **túl nagy áirat — a state nem fér el a döntési keretben**) → fallback a meglévő viselkedésre, log az okkal (SC-003, plan KD-5, spec Edge Cases 1–3).

### Implementáció

- [ ] T010 [US2] `compaction/adapter.py`: fallback-vezérlés (hiba → fallback; `reductionRatio < 0.25` → fallback vagy eredeti áirat megtartása), warning-log ok-bontással (FR-005).
- [ ] T011 [P] [US2] `compaction/events.py`: FR-006 esemény-rekord (elemek előtte/utána, döntés-okok, arány, fallback-ok) JSONL-be.

**Checkpoint**: US1+US2 együtt zöld; a Prime Agent meglévő compactionja érintetlen.

---

## Phase 3: Validáció + zárás

- [ ] T012 Teljes csomag: `pytest -q` exit 0; SC-004 ismételve az új tömörítéssel (a megtartott elemekben 0 elveszett hivatkozott útvonal/hibaüzenet); SC-005 arány-mérés az ≥5 fixture-ön, eredmények fájlba (`validation.json`).
- [ ] T013 **MANUÁLIS KAPU**: a felhasználó review-zza a `validation.json`-t és a kódot; tradeoff-döntés (ha valamelyik áiraton a küszöb alatt marad az arány) indoklással dokumentálva. Az agent NEM pipálhatja.
- [ ] T014 Naplóbejegyzés (Agent.md: tények, döntések, gotchák, backlog — pl. „ráhagyás finomítása, ha a becslési hiba <10%"), commit + push.

---

## Dependencies & Execution Order

- **Phase 0 blokkol mindent** — baseline nélkül nincs implementáció (mérés-fegyelem).
- T004/T005 és T009 tesztek buknak, mielőtt a megfelelő implementációs task elkezdődik.
- T006 → T008 (a config a vezérléshez kell); T007 párhuzamosítható T006-tal.
- T010 T006 után; T011 párhuzamos.
- A MANUÁLIS KAPU-k (T003, T013) emberi döntések — agent sosem pipálja.

## Validation Checklist (a tasks-template szerint)

- [ ] Minden FR-hez tartozik task: FR-001/002 → T004–T006; FR-003/004 → T005, T006; FR-005 → T009, T010; FR-006 → T011; FR-007 → T008.
- [ ] Minden SC-hez tartozik gate: SC-001 → T004; SC-002 → T005; SC-003 → T009; SC-004 → T002, T012; SC-005 → T012.
- [ ] Minden user story lefedett és önállóan tesztelhető (US1: Phase 1; US2: Phase 2).
- [ ] Emberi kapuk explicit jelölve (T003, T013).
