# Feature Specification: Azonosító-megtartó összefoglaló recovery-pointerrel

**Feature Branch**: `002-identifier-preserving-summary`

**Created**: 2026-09-20

**Status**: Draft

**Input**: User description: „Hosszú futású agent-sessionökben a tömörítés utáni összefoglalóból hiányoznak a pontos azonosítók (fájlútvonalak, hibaüzenetek, parancsok), pedig azok a megmaradt teljes előzményből visszakereshetők lennének. Szükségem van rá, hogy az összefoglaló ezeket az azonosítókat verbatim őrizze meg, és hogy az agent mindig tudja, hol és hogyan keresse vissza a részleteket — így a tömörítés után se vesszen el gyakorlatilag semmi."

## Background (diagnózis)

A spec 001 baseline-mérései (rögzítve: `baseline_loss.json`, `baseline_recovery.json`, Agent.md 1. bejegyzés):

- A jelenlegi összefoglaló-compaction a később hivatkozott azonosítók **~53–74%-át eldobja** (6 valós áirat, 2 summarizer-modell, 3 futás/átirat, cache nélkül).
- A kiesett azonosítók **100%-a visszanyerhető egyetlen kereséssel** a megmaradt JSONL-historyból — de ez felső korlát: az élő agentnek sejtenie kell a hiányt, és meg kell fogalmaznia a keresést.
- Külső evidencia (hermes-agent#116246): a verbatim-megtartó alternatíva drágább és nem jobb; a nyerő minta a „summary + jó visszakeresés".

A diagnózis tehát pontosult: nem a compaction módszere a hiba, hanem hogy (a) a summary **nem tartja meg az azonosítókat**, és (b) az agent **nem kap explicit recovery-pointert**. Mindkettő olcsón javítható a meglévő folyamat módosításával.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Az azonosítók túlélik a tömörítést (Priority: P1)

Tömörítés után az összefoglaló végén strukturált, verbatim azonosító-lista szerepel (érintett fájlútvonalak, hibaüzenetek, parancsok) — nem az LLM szabad asszociációjaként, hanem az áiratból szabályosan kigyűjtve. Az agent a későbbi lépésekben ezeket közvetlenül látja, keresés nélkül.

**Why this priority**: Ez szünteti meg a mért 53–74%-os veszteséget — a feature létoka.

**Independent Test**: A 6 fixture-átiraton a tömörítés utáni kimenetben az összes később hivatkozott azonosító verbatim jelen van (closed-book), LLM-hívás nélkül is ellenőrizhető a kigyűjtés.

**Acceptance Scenarios**:

1. **Given** egy fixture-átirat és a régi baseline (`baseline_loss.json`), **When** az új tömörítés lefut, **Then** a később hivatkozott azonosítók ≤5%-a hiányzik a kimenetből (baseline: 53–74%).
2. **Given** egy áirat 100+ érintett útvonallal, **When** a tömörítés lefut, **Then** az azonosító-lista mérete korlátozott (dokumentált felső határ), és a korlátozás a legrégebbi, legkevésbé hivatkozott elemeket dobja.
3. **Given** egy tömörített session, **When** az agent egy későbbi üzenetben hivatkozik egy régi fájlra, **Then** az útvonal a summary-ból közvetlenül kiolvasható.

---

### User Story 2 - Az agent tudja, hol keressen (Priority: P2)

A tömörített kimenet mindig tartalmaz egy fix recovery-pointer blokkot: a teljes előzmény helye (session-fájl) és a konkrét keresési mód (hogyan kell benne keresni). Az agentnek nem kell kitalálnia, hogy létezik visszakeresési út.

**Why this priority**: A recovery-mérés (baseline_recovery.json) szerint minden visszanyerhető — az egyetlen gyenge láncszem, hogy az agent tudja-e, hogy keressen. Ez zárja be a kört.

**Independent Test**: A tömörített kimenet szövegesen tartalmazza a session-fájl útvonalát és a keresési instrukciót; fixture-ön statikusan ellenőrizhető.

**Acceptance Scenarios**:

1. **Given** bármelyik tömörített kimenet, **When** az agent beolvassa, **Then** benne van a teljes előzmény elérési útja és a keresés módja.
2. **Given** egy olyan kérdés, amire a válasz csak az eldobott előzményben van, **When** az agent a pointert követi, **Then** egyetlen kereséssel megkapja a részletet (a baseline_recovery.json módszertanával mérve).

---

### Edge Cases

- Mi van, ha az azonosító-lista túl nagy lenne (nagyon hosszú session)? → dokumentált felső határ + eldobási szabály (legrégebbi/legkevésbé hivatkozott először).
- Mi van, ha egy „azonosító" valójában érzékeny adat (token, jelszó az áiratban)? → a kigyűjtés szűrje a nyilvánvaló titok-mintákat (pl. `api_key=`, `Bearer `), és ezt a szűrés dokumentált legyen.
- Mi van üres/nagyon rövid sessionnél? → a lista üres lehet, a pointer akkor is kiíródik; nincs külön hibaág.
- Duplikált azonosítók (ugyanaz az útvonal többször)? → deduplikáció, hivatkozásszámlálóval.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A tömörítés kimenete tartalmazza az áiratból **szabályosan kigyűjtött** (nem LLM-generált) azonosító-listát: fájlútvonalak, hibaüzenet-töredékek, parancsok — verbatim, deduplikálva.
- **FR-002**: Az azonosító-lista mérete dokumentált felső korlát alatt marad; a korlátot meghaladó esetben az eldobási sorrend dokumentált (legrégebbi/legkevésbé hivatkozott először).
- **FR-003**: A kimenet minden tömörítésnél tartalmazza a recovery-pointer blokkot: a teljes előzmény fájl-útvonala + a keresés konkrét módja.
- **FR-004**: A titok-szűrés: nyilvánvaló credential-minták nem kerülhetnek az azonosító-listába; a szűrés szabályai dokumentáltak.
- **FR-005**: A meglévő compaction egyéb viselkedése (trigger, formátum, a summary szöveges része) változatlan marad; a változás kizárólag az azonosító-lista és a pointer hozzáadása.
- **FR-006**: Minden tömörítésről strukturált rekord készül (azonosítók száma, eldobott azonosítók száma, lista-méret), fájlba vagy logba — ez a validáció mérési alapja.

### Key Entities

- **Azonosító (identifier)**: verbatim string az áiratból (útvonal, hibaüzenet-töredék, parancs), amelyre a session későbbi része hivatkozik.
- **Recovery-pointer**: fix szövegblokk a tömörített kimenetben (előzmény-útvonal + keresési mód).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Azonosító-megtartás: a 6 fixture-átiraton a tömörítés utáni kimenetből a később hivatkozott azonosítók legfeljebb **5%-a** hiányzik (baseline: Qwen 55–65/88, Kimi K3 47–61/88), per-átirat × per-modell bontásban; gate: a spec 001 compare-scriptje újrafuttatva, exit-code-os.
- **SC-002**: Méretkorlát: a summary + azonosító-lista együttes mérete legfeljebb **+15%** a régi summary-mérethez képest (átlagosan a 6 áiraton) — a verbatim-túlárazás elkerülése végett.
- **SC-003**: Recovery-pointer jelenlét: a tömörített kimenetek 100%-ában statikusan kimutatható a pointer-blokk (útvonal + keresési mód); gate: `pytest -q`, exit-code-os.
- **SC-004**: Titok-szűrés: a fixture-ökbe szándékozott credential-mintákat ültetve egyik sem kerül a kimenetbe; gate: `pytest -q`.

## Assumptions

- A spec 001 fixture-átiratai és mérőscriptjei változatlanul használhatók (újramérés = ugyanaz a 6 áirat).
- Az azonosító-kigyűjtés determinisztikus (regex/heurisztika) — nem igényel LLM-hívást.
- A tömörítési prompt/folyamat a futtatókörnyezetben módosítható (a spec 001 Out of Scope-ja ezt kizárta; a spec 002 ezt most felülírja — dokumentált döntés).

## Out of Scope

- **A summary szöveges minőségének általános javítása** (stílus, tömörség) — csak az azonosító-megtartás és a pointer. *Újraindítási feltétel: ha a validáció azt mutatja, hogy a summary szövege önmagában is információt veszít az azonosítókon túl.*
- **Automatikus proaktív visszakeresés** (az agent maga keressen minden hiányzó dologra) — a pointer passzív; a proaktív keresés az agent viselkedése. *Újraindítási feltétel: ha a T-validáció azt mutatja, hogy a pointer ellenére sem keres az agent.*
- **A verbatim (spec 001) irány újraélesztése** — lezárva, Agent.md 1. bejegyzés; *újraindítási feltétel: ha a spec 002 validációja azt mutatja, hogy az azonosító-lista + pointer sem csökkenti a gyakorlati veszteséget.*
