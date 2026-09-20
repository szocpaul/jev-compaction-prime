# Agent.md — döntési napló

## 1. Verbatim compaction (spec 001) — lezárva implementáció nélkül (2026-09-20)

**Mi történt (tények, számok):**
- spec 001 (verbatim, döntés-alapú tömörítés fast-jev-compaction-nel) spec + plan + tasks
  jóváhagyva; a Phase 0 baseline lefutott, a Phase 1 a T016-os kapu előtt leállt.
- `baseline_loss.json` (6 valós áirat × 3 futás, cache nélkül): az összefoglaló-compaction
  a később hivatkozott azonosítók ~53–74%-át eldobja (Qwen3.8-27B: 55–65/88; Kimi K3: 47–61/88).
- `baseline_recovery.json` (SC-004b kontroll-kar): a kiesett jelöltek **100%-a** visszanyerhető
  EGY kereséssel a megmaradt JSONL-historyból (181/181, 164/164) — felső korlát, mert a
  mérés a pontos stringet kereste; az élő agentnek a hiányt sejtenie és a queryt
  megfogalmaznia kell.
- Külső evidencia: NousResearch/hermes-agent#116246 — a verbatim-kar closed-bookban nyer
  csak; summary+search recall-ban és költségben is jobb (78,9% @ 55K vs 75,5% @ 115K);
  verbatim ~2,1× token/turn, ciklusonként prompt-cache-törés; >~500 tool call nem fér
  a döntési keretbe.

**Döntések és indoklás:**
- A T003 kapu approve-olva (a closed-book diagnózis igazolódott mindkét modellnél).
- A T016 kapu: premissza MEGINGOTT → Phase 1 leállítva, spec lezárva implementáció nélkül.
  (Elvetett alternatíva: Phase 1 folytatása — a recovery-kar és a hermes-eval alapján a
  verbatim-út drágább és nem jobb, mint a meglévő summary + jó visszakeresés.)
- A valódi probléma újrafogalmazva: nem a compaction módszere a hiba, hanem hogy
  (a) a summary nem tartja meg az azonosítókat (útvonalak, hibaüzenetek), és
  (b) az agent nem kap erős recovery-pointert (mit, hol keressen).

**Tanulságok / gotchák:**
- A closed-book mérés önmagában félrevezet: azt kell mérni, amit a rendszer
  TÉNYLEGESEN tud (a recovery-felülettel együtt), nem a legrosszabb verzióját.
- A „megoldás megvan, csak portolni kell" érzés (npm-csomag, kész módszer) nem ment
  a saját baseline + kontroll-kar mérésétől — a kontroll-kar volt a spec legolcsóbb
  és legértékesebb része.
- npm-publikáció feltételezése: a `fast-jev-compaction` nincs a registry-ben;
  a pinning commit-hashre történt (plan KD-7).

**Backlog:**
- spec 002: „azonosító-megtartó summary + recovery-pointer" — a summary kötelezi a
  fájlútvonalak/hibaüzenetek verbatim felsorolását + explicit „itt keresd" pointert.
- Ha az npm-en megjelenik a fast-jev-compaction: a plan KD-7 visszaállítható
  verzió-pinningre (nem prioritás).
