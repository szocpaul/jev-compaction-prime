# Runner-átadás — specs/001-verbatim-context-compaction

> Ezt a promptot a szerveren, a repó lokális clone-jában add át egy dedikált Prime Agent
> runnernek (autonomous-spec-runner minta: tmux + `prime-agent --autonomous`).
> A runner a spec-FÁJLOKBÓL dolgozik, nem a promptból — a prompt csak a kereteket adja.

---

Implementáld a `specs/001-verbatim-context-compaction/` specet (spec.md, plan.md, tasks.md)
a tasks.md sorrendjében, checkbox-pipálással ahogy haladsz.

**Környezet:**
- Repo lokális útvonala: `<TÖLTSD KI: a clone útvonala a szerveren>`
- Python interpreter: `<TÖLTSD KI: pl. .venv/bin/python>` — csak ezt használd.
- A bridge Node 20+-ot igényel; `node --version` ellenőrzés a preflight része.

**Preflight (MEGHISULT PREFLIGHT → NEM INDUL SEMMI):**
1. `node --version` ≥ 20
2. `npm install` a `compaction/bridge/` alatt sikeres (fast-jev-compaction PINNELT verzió)
3. `TYPESAFE_API_KEY` beállítva; egy minimális Jev-hívás sikeres (smoke-teszt)
4. A Prime Agent JSONL-átiratok elérhetők a baseline-fixture-ökhöz (T001)

**Gate-ek (exit-code-os, mindegyik zöld kell legyen):**
- `pytest -q tests/test_verbatim.py` (SC-001)
- `pytest -q tests/test_pairing.py` (SC-002)
- `pytest -q tests/test_fallback.py` (SC-003)
- `pytest -q` teljes csomag a validációs fázisban (T012)

**Limitek:** max 8 turn, max 2 óra wall-clock; egy task többszöri bukása után állj meg és jelentsd.

**TILALMAK:**
- A MANUÁLIS KAPU taskokat (T003, T013) NE pipáld — azok emberi döntések; állj meg és jelentsd, amikor odaérsz.
- A Prime Agent meglévő összefoglaló-compaction kódjához NE nyúlj (fallback-ként változatlanul marad).
- A `fast-jev-compaction` verzióját a baseline rögzítése (T002) után NE változtasd — verzióváltás = baseline újramérés.
- A baseline-mérésnél (T002) NE használj cache-t — a mérés tényleg fusson.
- Részleges Jev-választ NE alkalmazz — részleges válasz = teljes fallback (plan KD-5).
- Ha a Jev API vagy az npm-csomag elérhetetlen: állj meg és jelentsd — NE improvizálj helyettesítőt.

**Befejezés:** küldj összefoglalót a main-sessionnek (kész taskok, gate-eredmények,
baseline/validációs számok, mi maradt nyitva), aztán `goal.complete()`.

---

## Kitöltendő a felhasználó által

- [ ] `<TÖLTSD KI: a clone útvonala a szerveren>` — pl. `/home/<user>/jev-compaction-prime`
- [ ] `<TÖLTSD KI: pl. .venv/bin/python>` — ha nincs venv, a rendszer-python abszolút útvonala
- [ ] A spec-fájlok át lettek másolva a repóba (specs/001-verbatim-context-compaction/) és commitolva
- [ ] `Agent.md` létrehozva a repó gyökerében (zárási naplóbejegyzés célpontja)

---

## Indítás a szerveren (másolható parancssorozat)

> Feltétel: a két `<TÖLTSD KI>` mező kitöltve, a szerveren `prime-agent`, `tmux`,
> `node ≥ 20` és `git` elérhető.

```bash
# 0) Repó klónozása a szerveren (ha még nincs)
git clone https://github.com/szocpaul/jev-compaction-prime.git
cd jev-compaction-prime

# 1) Környezeti előfeltételek (ezeket TE futtatod, nem a runner)
node --version                      # ≥ 20 kell
export TYPESAFE_API_KEY=<a kulcsod> # a tmux-session ÖRÖKLI → előbb exportáld!

# 2) Dedikált tmux-session a runnernek
tmux new-session -d -s spec001-runner -c "$(pwd)"

# 3) Runner indítása autonomous módban, a handoff-prompttal
#    (a prompt a FÁJLRA hivatkozik, nem másoljuk bele a tasklistát)
tmux send-keys -t spec001-runner 'prime-agent --autonomous \
  --goal "Implementáld a specs/001-verbatim-context-compaction/ specet a runner-handoff.md szabályai szerint" \
  --max-turns 8 --max-hours 2' Enter

# 4) Elküldöd neki a handoffot első üzenetként
tmux send-keys -t spec001-runner \
  'Olvasd el a specs/001-verbatim-context-compaction/runner-handoff.md fájlt, és a benne lévő preflight-tal kezdd. Meghiusult preflight → állj meg és jelentsd.' Enter

# 5) (Opcionális) elnevezed, hogy címezhető legyen
prime-agent rename spec001-runner 2>/dev/null || true
```

**Közben (neked):**

```bash
prime-agent list                          # runner státusza (working/idle)
prime-agent attach spec001-runner         # belenézés élőben, bármikor
grep -c '^\- \[x\]' specs/001-verbatim-context-compaction/tasks.md   # haladás
prime-agent send spec001-runner "korrekció..."   # út közbeni irányítás
```

**Várható megállások (ezek NEM hibák):**

1. **T003 MANUÁLIS KAPU**: a runner elkészíti a `baseline_loss.json`-t, megáll, és üzen neked — te nézed át és hagyod jóvá (vagy állítod le a láncot, ha a veszteség ≈ 0).
2. **T013 MANUÁLIS KAPU**: a validáció (`validation.json` + teljes pytest) után újra megáll — te review-zod a kódot és a méréseket, a tradeoff-döntés a tiéd.

**Takarítás a végén (a runner csinálja, ellenőrizd):**

```bash
tmux kill-session -t spec001-runner   # ha a runner nem tette meg
git log --oneline -3                  # a záró commit + Agent.md bejegyzés megvan?
```
