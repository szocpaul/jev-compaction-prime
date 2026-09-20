# Runner-átadás — specs/002-identifier-preserving-summary

> A szerveren, a repó lokális clone-jában add át egy dedikált Prime Agent runnernek
> (autonomous-spec-runner skill). A runner a spec-FÁJLOKBÓL dolgozik, nem a promptból.

---

Implementáld a `specs/002-identifier-preserving-summary/` specet (spec.md, plan.md, tasks.md)
a tasks.md sorrendjében (T101–T111), checkbox-pipálással ahogy haladsz.

**Környezet:**
- Repo lokális útvonala: `/home/ubuntu/jev-compaction-prime/`
- Python interpreter: `/home/ubuntu/jev-compaction-prime/.venv/bin/python` — csak ezt használd.
- Nincs Node-bridge, nincs Jev-függőség ebben a specben (a spec 001-es irány lezárva).

**Preflight (MEGHISULT PREFLIGHT → NEM INDUL SEMMI):**
1. Az interpreter létezik, `pytest --version` fut.
2. A `tests/fixtures/transcripts/` 6 fixture-átirata és a `baseline_loss.json` megvan és parse-olható.
3. A Prime Agent dist-beli summarization-felület (`SUMMARIZATION_SYSTEM_PROMPT` / `SUMMARIZATION_PROMPT` / `serializeConversation`) egyezik azzal, amit a `scripts/baseline_loss.py` replikál — ha eltér (upstream-frissítés történt), **állj meg és jelentsd** (plan KD-6 kockázata).
4. A summarizer-modellek elérhetők a méréshez (a baseline_loss.json meta-blokkja szerinti Qwen és Kimi K3 endpointok).

**Gate-ek (exit-code-os, mindegyik zöld kell legyen):**
- `pytest -q tests/test_identifiers.py tests/test_pointer.py` (SC-001/SC-003/SC-004 egységtesztek)
- `python scripts/identifiers_loss.py` → `identifiers_loss.json`: azonosító-veszteség ≤5% és méretnövekedés ≤+15% (SC-001, SC-002)

**Limitek (autonomous-spec-runner minta szerint):** max 40 turn, max 8 continuation,
max 200 000 token, max 3 óra wall-clock; egy task többszöri bukása után állj meg és jelentsd.

**Autonomous-gate: szándékosan NINCS** (teszt-előbb workflow — lásd spec 001 handoff indoka).

**TILALMAK:**
- A MANUÁLIS KAPU-t (T110) NE pipáld — állj meg és jelentsd, amikor odaérsz.
- A meglévő summary-szöveget NE módosítsd — a változás kizárólag az azonosító-lista és a pointer HOZZÁADÁSA (FR-005).
- A fixture-átiratokhoz (`tests/fixtures/transcripts/`) NE nyúlj — azok a mérési etalonok.
- Méréseknél (T108) cache TILOS — minden futás élő.
- A summarizer-modelleket NE cseréld — a baseline meta-blokkja szerinti modellekkel mérj; modellcsere = a teljes mérés újra.
- A T109 (verbatim-adapter eltávolítása) során a `compaction/`-ból CSAK a spec 001-es félkész kódot távolítsd; az új (002-es) fájlok maradjanak.
- Ha a dist-felület eltér (preflight 3): állj meg és jelentsd — NE improvizálj adaptert.

**Befejezés:** küldj összefoglalót a main-sessionnek (kész taskok, gate-eredmények,
az identifiers_loss.json számai, mi maradt nyitva), aztán `goal.complete()`.

---

## Indítás a szerveren (autonomous-spec-runner skill)

A main-sessionben:

> „Implementáld a specs/002-identifier-preserving-summary specet az autonomous-spec-runner
> workflow-val. A szabályok a specs/002-identifier-preserving-summary/runner-handoff-002.md-ben
> vannak — a preflighttel kezdd, meghiusult preflight esetén ne induljon semmi.
> Interpreter: `/home/ubuntu/jev-compaction-prime/.venv/bin/python` — csak ezt használd.
> Három fő szabály: A MANUÁLIS KAPU-t (T110) NE PIPÁLD — állj meg és jelentsd.
> A meglévő summary-szöveget NE MÓDOSÍTSD, csak az azonosító-listát és a pointert add hozzá.
> A fixture-átiratokhoz NE NYÚLJ; mérésnél cache TILOS."

**Várható megállás:**

1. **T110 MANUÁLIS KAPU**: az `identifiers_loss.json` elkészülte után a runner megáll és üzen — te review-zod a számokat és a kódot, a tradeoff a tiéd.
