# Feature Specification: Verbatim kontextus-tömörítés döntés-alapú eldobással

**Feature Branch**: `001-verbatim-context-compaction` *(ideiglenes sorszám — a célrepóban ellenőrizendő)*

**Created**: 2026-09-18

**Status**: Closed — superseded (a premissza a T016-os kapunál megingott; a folytatás spec 002)

**Input**: User description: „Hosszú futású agent-sessionökben a meglévő kontextus-tömörítés összefoglalóval dolgozik, és az összefoglalóból elveszhetnek pontos fájlútvonalak, hibaüzenetek és parancsok, amelyek később a munka folytatásához kellenének. Szükségem van olyan tömörítésre, ami semmit nem ír át — csak eldobja, ami már nem kell, és verbatim megtart minden mást —, és hiba vagy elégtelen tömörítés esetén megbízhatóan visszaesik a jelenlegi viselkedésre."

## Background (diagnózis)

A spec cél-futtatókörnyezete a **Prime Agent** (PrimeIntellect-ai/prime-agent) összefoglaló-alapú compactionja. Jelenlegi működése (a hivatalos dokumentáció és az arXiv-preprint alapján):

- A compaction automatikusan indul, amikor a kontextus elér egy küszöböt, vagy az agent maga hívja meg a REPL-ben (`compact.run()`).
- A beszélgetés régebbi prefixét egy LLM-generált **összefoglaló helyettesíti** az aktív kontextusban.
- Az eredeti események nem semmisülnek meg: a teljes history append-only JSONL-fájlokban a diszken megmarad, és a REPL-en keresztül programozottan visszakereshető (`/tree`).

A probléma tehát nem végleges adatvesztés, hanem **láthatósági veszteség**: az összefoglaló definíció szerint átírás — a modell dönti el, mi maradjon benne, és a kihagyott részletek (pontos fájlútvonal, verbatim hibaüzenet, konkrét parancs) kikerülnek az aktív kontextusból. Visszakeresésük az agent tudatos lépését igényli: ha az agent nem sejti, hogy hiányzik valami, nem is keresi. A veszteség láthatatlan — az összefoglaló „jól hangzik", a hiány csak akkor derül ki, amikor a session egy későbbi lépésben hibás útvonalra vagy téves hibaértelmezésre épít.

A veszteség mértéke a baseline-mérés szerint jelentős: 6 valós áiraton, két summarizer-modellnél (Qwen3.8-27B: 55–65/88 jelölt; Kimi K3: 47–61/88) a később hivatkozott azonosítók ~53–74%-a elvész a summary-ból (lásd SC-004, `baseline_loss.json`).

**Új evidencia (2026-09-19/20)**: a NousResearch/hermes-agent#116246 eval ugyanezt a módszert (fast-jev-compaction Python-port) mérte ki: a verbatim-kar recall-előnye kizárólag a szöveg megtartásából fakad, kiegyenlített büdzsénél a pontozás döntetlen a recency-vel; a verbatim ~2,1× token-terhet jelent turnönként, ciklusonként prompt-cache-t tör, és >~500 tool call nem fér a döntési keretbe; a **summary + egy visszakeresés a megmaradt historyból** recall-ban és költségben is jobb (78,9% @ 55K vs 75,5% @ 115K). Mivel a Prime Agent is megtartja a teljes JSONL-historyt, a spec premisszája (a closed-book veszteség = gyakorlati veszteség) ellenőrzést igényel → **SC-004b kontroll-kar**, az emberi kapu dönt a folytatásról vagy átfogalmazásról.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tömörítés verbatim-megtartással (Priority: P1)

Hosszú session közben, amikor a kontextus eléri a tömörítési küszöböt, a rendszer nem összefoglalót készít, hanem elemről elemre dönt: ami már nem kell, azt eldobja (vagy rövidített jelöléssel helyettesíti), ami kell, azt változatlanul, eredeti sorrendben megtartja. A felhasználó által írt szövegek és az agent válaszszövegei mindig érintetlenek maradnak.

**Why this priority**: Ez a feature létoka — ha a tömörítés továbbra is átír, az egész spec értelmetlen. Ez az egyetlen story, ami önmagában is szállítható érték.

**Independent Test**: Egy rögzített, 80–150 tool call-os session-átiraton futtatva a tömörítés kimenete tartalmazza verbatim az összes megtartott elemet, és a kimenetben nincs olyan szöveg, ami az eredeti áiratban nem szerepelt.

**Acceptance Scenarios**:

1. **Given** egy session-átirat történeti tool-hívásokkal, **When** a tömörítés lefut, **Then** a megtartott tool-hívások és eredmények bájthelyesen azonosak az eredetivel, és a sorrend változatlan.
2. **Given** egy session-átirat, **When** a tömörítés eldob egy tool-hívást, **Then** a hozzá tartozó eredmény is eltűnik (nincs eredmény hívás nélkül, és fordítva).
3. **Given** egy session-átirat, **When** a tömörítés lefut, **Then** a legfrissebb N üzenet (konfigurálható) és az első üzenet mindig érintetlen marad.

---

### User Story 2 - Megbízható visszaesés (Priority: P2)

Ha az elem-alapú tömörítés elhasal (külső szolgáltatás-hiba, hibás válasz, túl nagy áirat) vagy az elérhető tömörítési arány egy küszöb alatt marad (nem éri meg), a rendszer figyelmeztető log mellett visszaesik a meglévő, összefoglaló-alapú viselkedésre — a session sosem akad el a tömörítés miatt.

**Why this priority**: Ez teszi élesszíthatóvá az US1-et: új hibaforrást viszünk be, ezért a régi út biztonsági hálóként megmarad. Nélküle az US1 kockázatosabb, mint a status quo.

**Independent Test**: Szimulált hibákkal (elérhetetlen végpont, hibás válasz, alacsony tömörítési arány) a kimenet mindig a meglévő viselkedés, és a log tartalmazza a visszaesés okát.

**Acceptance Scenarios**:

1. **Given** elérhetetlen külső döntési szolgáltatás, **When** a tömörítésnek le kellene futnia, **Then** a meglévő összefoglaló-alapú tömörítés fut le, és warning-log keletkezik az okkal.
2. **Given** egy áirat, amiből az elem-alapú tömörítés kevesebb mint a beállított arányt tudná eldobni, **When** lefut, **Then** az eredeti áirat marad érvényben (vagy az összefoglaló-fallback), és a döntés naplózva van.

---

### Edge Cases

- Mi történik, ha az áirat annyira nagy, hogy a döntési állapot sem fér el a külső szolgáltatás keretében? → a tömörítés hibát dob, és az US2 fallback lép életbe (nem csonkolunk „mégiscsak").
- Mi történik üres vagy nagyon rövid sessionnél? → a tömörítési arány a küszöb alatt marad, fallback; nincs értelmetlen döntési kör.
- Mi történik, ha a külső szolgáltatás részben hibás választ ad (néhány elemre nincs döntés)? → az egész kérés hibának számít, fallback — részleges döntést nem alkalmazunk.
- Hogyan viselkedik a rendszer nagyon kód-sűrű vagy nem-latin áiratnál, ahol a méretbecslés pontatlan? → [NEEDS CLARIFICATION: a becslés konzervativizmusának mértéke nem specifikált — kell-e biztonsági ráhagyás és mekkora?]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A rendszer a tömörítés során a megtartott elemeket bájthelyesen változatlanul és eredeti sorrendben adja vissza; a kimenetben nem szerepelhet az eredeti áiratban nem létező tartalom.
- **FR-002**: A rendszer a törlési döntéseket elem-szinten (hívás + hozzá tartozó eredmény egységként) hozza meg; árva eredmény vagy árva hívás a kimenetben nem maradhat.
- **FR-003**: A felhasználói és agent-szövegek a kimenetben mindig érintetlenek maradnak; törlés/csökkentés csak műveleti elemekre (tool-hívás, tool-eredmény) vonatkozhat.
- **FR-004**: A legfrissebb N üzenet és a legelső üzenet mindig „pinned" (érintetlen); N konfigurálható, alapértelmezés dokumentált.
- **FR-005**: Külső szolgáltatás-hiba, érvénytelen válasz vagy a küszöb alatti tömörítési arány esetén a rendszernek a meglévő összefoglaló-alapú tömörítésre kell visszaesnie, warning-loggal (hiba oka + melyik szabály váltotta ki).
- **FR-006**: Minden tömörítési eseményről strukturált statisztika készül (elemek száma előtte/utána, döntés-okok bontása, tömörítési arány), fájlba vagy logba írva — ez a mérési alap.
- **FR-007**: A döntési küszöbök (megtartási valószínűség, minimális tömörítési arány, pinned-ablak) konfigurálhatóak, rögzített alapértékekkel.

### Key Entities

- **Session-átirat (transcript)**: sorrendezett üzenetek; üzenet = szerep + szöveg + műveleti elemek (hívások, eredmények). A tömörítés bemenete és kimenete is ez a forma.
- **Döntési egység**: egy hívás + a hozzá tartozó eredmény párosa; a megtartás/eldobás/rövidítés erre vonatkozik.
- **Tömörítési esemény-rekord**: egy tömörítés eredménye — döntések, statisztikák, esetleges fallback-ok (FR-006).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Verbatim-teszt: rögzített teszt-átiratokon a megtartott elemek 100%-a bájthelyes az eredetivel; gate-parancs: `pytest -q tests/test_verbatim.py` (exit code 0).
- **SC-002**: Párosítási invariáns: a kimenetben 0 árva eredmény és 0 árva hívás; gate: `pytest -q tests/test_pairing.py` (exit code 0).
- **SC-003**: Fallback-teszt: minden szimulált hibaforrásra (elérhetetlen szolgáltatás, hibás válasz, küszöb alatti arány) a meglévő viselkedés lép életbe, és a log tartalmazza az okot; gate: `pytest -q tests/test_fallback.py` (exit code 0).
- **SC-004**: Diagnózis-mérés: ≥5 rögzített valós session-átiraton az összefoglaló-alapú tömörítés után számszerűen rögzítve, hány később hivatkozott fájlútvonal/hibaüzenet veszett el (baseline, változtatás előtt, fájlba írva); és ugyanezen áiratokon az új tömörítésnél ez a veszteség 0 (a megtartott elemek között minden hivatkozott útvonal/hibaüzenet verbatim jelen van). Gate: compare-script számszerű küszöbbel, per-átirat bontásban.
- **SC-004b (új evidencia utáni kontroll-kar)**: ugyanazon az ≥5 áiraton mérve kell azt is, hogy a summary után **egyetlen visszakeresés** a megmaradt JSONL-historyból az elveszett jelöltek hány százalékát hozza vissza (az agent valós recovery-útvonalát szimulálva). Ha a closed-book-veszteség ≥90%-a egy kereséssel visszanyerhető, a feature premisszája megingott, és a spec átfogalmazandó (az emberi kapu dönt). Indok: a NousResearch/hermes-agent#116246 eval szerint a verbatim-kar csak closed-book mérésben nyer; summary + egy keresés recall-ja és token-költsége is jobb (78,9% @ 55K vs 75,5% @ 115K), és a verbatim-kar ~2,1× token-terhet jelent turnönként romló cadence-szel.
- **SC-005**: Tömörítési arány: a baseline-átiratokon az új tömörítés karakterarányos méretcsökkentése ≥ 25% (a fallback-küszöb felett), különben a feature az adott sessionön nem váltja ki a régi viselkedést — ez mérve és naplózva van.

## Assumptions

- A Prime Agent session-átiratai gépileg kinyerhetők jóldefiniált formában (append-only JSONL, hívás–eredmény párosítással); ha ez nem teljesül, az a validáció során kiderül, és az FR-002 nem teljesíthető — a lánc megáll.
- A tömörítési döntéshez rendelkezésre áll egy külső, pontozásra képes szolgáltatás; annak hitelesítése és kvótája a futtató környezetben beállított.
- A teszt-átiratok (SC-004, ≥5 db) a felhasználó valós sessionjeiből származnak, rögzítve a változtatás előtt.

## Out of Scope

- **A tömörített kimenet „szépsége" vagy olvashatósága** — a kimenet gépnek szól; emberi minőség-értékelés nem cél. *Újraindítási feltétel: ha a verbatim-kimenetet ember is olvassa (pl. napló-review), külön spec formázási követelményekkel.*
- **A döntési szolgáltatás minőségének hangolása** (milyen döntéseket hoz) — ebben a specben a küszöbök fix, dokumentált alapértékeken maradnak. *Újraindítási feltétel: ha a baseline-mérés (SC-004) azt mutatja, hogy a döntési pontosság a szűk keresztmetszet, külön spec kalibrációval és zaj-méréssel.*
- **A meglévő összefoglaló-alapú tömörítés módosítása** — az fallback-ként változatlanul megmarad; ezen spec nem nyúl hozzá.
- **Más agent-keretrendszerek támogatása** — a spec a Prime Agent futtatókörnyezetére szól. *Újraindítási feltétel: ha a megoldás hordozhatóvá válik, külön spec az adapter-rétegről.*
