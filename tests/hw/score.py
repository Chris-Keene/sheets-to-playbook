#!/usr/bin/env python3
"""Score a run's raw transcriptions against a handwriting test's answer key.

    python3 tests/hw/score.py runs/<run>                                      # rounds 1 and 2 (tests/hw/truth.json)
    python3 tests/hw/score.py runs/<run> --truth tests/hw/round3/truth.json   # round 3
    python3 tests/hw/score.py runs/<run> --json report.json                   # also save the full report

The run is an ingest run folder: it reads raw/T<nn>.json and raw/commitments.json, plus labels-blind.json
(with manifest.json) if a blind labeller wrote one.

Per item, in order of how much it matters on the day:
  silent   wrong, with no [?word] / [illegible] marker and not in `unclear`: would reach the review unflagged
  missed   on the sheet, not in the transcription
  extra    in the transcription, not on the sheet (a crossed-out item that crept back in counts here)
  flagged  wrong or unsure, but marked, so the human review catches it
  exact    right (case, punctuation and [expansions] ignored)
Plus the special checks: crossed-out text kept out, ticks, the table-number mismatch, the arrow, the tally and
"best thing" boxes, card names and organisations, and photo labelling if labels-blind.json is there.
"""
import argparse, difflib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\[\?([^\]]*)\]", r"\1", s)        # [?word] -> word: the best reading counts if it's right
    s = re.sub(r"\[[^\]]*\]", " ", s)              # [illegible], [executive] expansions
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9£%.@/ ]", " ", s)
    s = re.sub(r"(?<![a-z0-9])\.|\.(?![a-z0-9])", " ", s)   # keep dots inside 1.4.3 and URLs only
    return " ".join(s.split())


def flagged(text):
    return "[?" in (text or "") or "[illegible" in (text or "").lower()


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def word_errors(gt, got):
    a, b = norm(gt).split(), norm(got).split()
    sm = difflib.SequenceMatcher(None, a, b)
    return sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"), len(a)


def match(gt_items, got_items, unclear_ids, text_only=False):
    """Greedy best-first pairing. got_items: [(text, id)]. Returns rows and unmatched got."""
    pairs = sorted(((sim(g, t), i, j) for i, g in enumerate(gt_items) for j, (t, _) in enumerate(got_items)), reverse=True)
    used_g, used_t, rows = set(), set(), {}
    for s, i, j in pairs:
        if s < 0.5 or i in used_g or j in used_t:
            continue
        used_g.add(i); used_t.add(j)
        text, iid = got_items[j]
        if norm(text) == norm(gt_items[i]):
            kind = "exact"
        elif flagged(text) or (iid in unclear_ids and not text_only):
            kind = "flagged"
        else:
            kind = "silent"
        e, n = word_errors(gt_items[i], text)
        rows[i] = dict(gt=gt_items[i], got=text, kind=kind, werr=e, words=n, marked=flagged(text) or (iid in unclear_ids and not text_only))
    out = [rows.get(i, dict(gt=g, got=None, kind="missed", werr=len(norm(g).split()), words=len(norm(g).split()), marked=False))
           for i, g in enumerate(gt_items)]
    extra = [got_items[j][0] for j in range(len(got_items)) if j not in used_t]
    return out, extra


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def score_table(n, truth, raw, not_shot=lambda s: False):
    unclear_ids = {u.get("id") for u in raw.get("unclear", [])}
    unclear_text = " ".join(json.dumps(u) for u in raw.get("unclear", []))
    notes = (raw.get("notes") or "") if isinstance(raw.get("notes"), str) else json.dumps(raw.get("notes"))
    sec = lambda *path: _dig(raw, path)
    sections = []
    def add(label, gt, got):
        rows, extra = match(gt, got, unclear_ids, text_only=label.startswith("S3"))
        sections.append(dict(section=label, rows=rows, extra=extra))
    get = lambda lst, f="text": [(x.get(f, "") if isinstance(x, dict) else x, x.get("id") if isinstance(x, dict) else None) for x in (lst or [])]
    if not_shot("S1"):
        for k in [k for k in truth if k.startswith("S1.")]:
            truth = {**truth, k: [] if isinstance(truth[k], list) else ""}
        truth = {**truth, "countries": None, "tally": {}}
    add("S1 challenges", truth.get("S1.challenges", []), get(sec("S1", "challenges")))
    add("S1 top three", truth.get("S1.top3", []), get(sec("S1", "top3")))
    pick = sec("S1", "pick")
    add("S1 pick", [truth["S1.pick"]] if truth.get("S1.pick") else [], get([pick] if isinstance(pick, dict) else [pick] if pick else []))
    for k in ("helped", "hindered", "lessons"):
        add(f"S2 {k}", truth.get(f"S2.{k}", []), get(sec("S2", k)))
    acts = sec("S3", "actions") or []
    for f in ("action", "needs", "sticks"):
        add(f"S3 {f}", [a[f] for a in truth.get("S3.actions", [])], [(a.get(f, ""), a.get("id")) for a in acts])
    for k in ("quotes", "questions"):
        add(f"SS {k}", truth.get(f"SS.{k}", []), get(sec("SS", k)))
    add("SS resources", truth.get("SS.resources", []),
        [(" ".join(dict.fromkeys(filter(None, [r.get("text", ""), r.get("url", "")]))) if isinstance(r, dict) else r, r.get("id") if isinstance(r, dict) else None) for r in (sec("SS", "resources") or [])])

    everything = " ".join(strings(raw))
    checks = []
    # ticks: pair each true action with the transcribed one it matched
    for i, a in enumerate(truth.get("S3.actions", [])):
        best = max(acts, key=lambda x: sim(a["action"], x.get("action", "")), default=None)
        if not best or sim(a["action"], best.get("action", "")) < 0.5:
            continue
        got = sorted(best.get("stages") or [])
        if a.get("ambiguous_tick"):
            ok = best.get("id") in unclear_ids or "tick" in (notes + unclear_text).lower()
            checks.append(("ambiguous tick flagged", ok, f"stages {got}; unclear/notes mention it: {ok}"))
        else:
            checks.append((f"ticks, action {i + 1}", got == sorted(a["stages"]), f"want {sorted(a['stages'])}, got {got}"))
    legit = [x for k, v in truth.items() if k[:2] in ("S1", "S2", "SS") and isinstance(v, list) for x in v if isinstance(x, str)]
    for g in truth.get("gone", []):
        hit = [s for s in strings(raw) if (sim(g, s) > 0.75 or norm(g) in norm(s))
               and not any(sim(l, s) > sim(g, s) for l in legit)]
        checks.append(("crossed-out item kept out", not hit, f"'{g}'" + (f" found as '{hit[0]}'" if hit else "")))
    for e in truth.get("effects", []):
        if "footer" in e:
            ok = bool(re.search(r"\b8\b", notes + unclear_text)) and bool(re.search(r"\b9\b", notes + unclear_text))
            checks.append(("table numbers disagree: noted", ok, notes[:160]))
        if e.startswith("arrow"):
            checks.append(("arrow noted", "arrow" in notes.lower(), notes[:160]))
    # v0.4.0 fields: exact checks when the reader used them
    room = sec("S1", "room")
    if isinstance(room, dict) and truth.get("countries"):
        got_t = {k: v for k, v in (room.get("tally") or {}).items() if v}
        checks.append(("S1.room tally exact", got_t == truth["tally"], f"want {truth['tally']}, got {got_t}"))
        checks.append(("S1.room countries", norm(room.get("countries")) == norm(truth["countries"]), f"want {truth['countries']!r}, got {room.get('countries')!r}"))
    best = sec("SS", "best")
    if isinstance(best, dict) and truth.get("SS.best"):
        ok = norm(best.get("text")) == norm(truth["SS.best"]) or flagged(best.get("text"))
        checks.append(("SS.best field", ok, f"want {truth['SS.best']!r}, got {best.get('text')!r}"))
    # boxes the raw format had no field for before v0.4.0: did the reader keep them anywhere?
    if truth.get("countries") and not isinstance(room, dict):
        c_ok = all(c.strip().lower() in everything.lower() for c in truth["countries"].split(","))
        checks.append(("countries kept somewhere", c_ok, truth["countries"]))
        t_ok = any(s.lower() in everything.lower() for s in truth["tally"]) and "tally" in everything.lower()
        checks.append(("sector tally kept somewhere", t_ok, json.dumps(truth["tally"])))
    if truth.get("SS.best") and not isinstance(best, dict):
        b_ok = norm(truth["SS.best"]) in norm(everything)
        checks.append(("'best thing' box kept somewhere", b_ok, truth["SS.best"]))
    return sections, checks


def _dig(d, path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def score_cards(truth_cards, raw):
    cards = raw.get("cards", [])
    unclear_ids = {u.get("id") for u in raw.get("unclear", [])}
    rows, extra = match([c["text"] for c in truth_cards], [(c.get("text", ""), c.get("id")) for c in cards], unclear_ids)
    checks = []
    for tc in truth_cards:
        best = max(cards, key=lambda c: sim(tc["text"], c.get("text", "")), default=None)
        if not best or sim(tc["text"], best.get("text", "")) < 0.5:
            continue
        for f in ("name", "org"):
            want, got = tc.get(f), best.get(f)
            if want is None:
                ok = not got
                checks.append((f"card {f} left blank", ok, f"'{tc['text'][:40]}': got {got!r}"))
            else:
                ok = norm(want) == norm(got) or ((flagged(got) or best.get("id") in unclear_ids) and sim(want, got or "") > 0.5)
                checks.append((f"card {f}", ok, f"want {want!r}, got {got!r}"))
    return [dict(section="Commitment cards", rows=rows, extra=extra)], checks


def summarise(sections):
    rows = [r for s in sections for r in s["rows"]]
    c = {k: sum(r["kind"] == k for r in rows) for k in ("exact", "flagged", "silent", "missed")}
    c["extra"] = sum(len(s["extra"]) for s in sections)
    c["items"] = len(rows)
    werr, words = sum(r["werr"] for r in rows), sum(r["words"] for r in rows)
    c["word_acc"] = round(100 * (1 - werr / words), 1) if words else None
    c["over_flagged"] = sum(r["kind"] == "exact" and r["marked"] for r in rows)
    return c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="the ingest run folder to score")
    ap.add_argument("--json", help="also write the full report here")
    ap.add_argument("--truth", default=str(HERE / "truth.json"), help="answer key; each round keeps its own copy "
                    "(default tests/hw/truth.json, from make_hw_tests.py)")
    a = ap.parse_args()
    run = Path(a.run)
    if not Path(a.truth).exists():
        sys.exit(f"No answer key at {a.truth}. Make it with python3 tests/hw/make_hw_tests.py "
                 "(or make_round3.py, then pass --truth tests/hw/round3/truth.json).")
    if not (run / "raw").is_dir():
        sys.exit(f"No raw/ folder in {run}: point this at an ingest run whose readers have written raw/T<nn>.json.")
    truth = json.loads(Path(a.truth).read_text())
    report = {"tables": {}, "cards": None}
    for n, tt in truth["tables"].items():
        f = run / "raw" / f"T{int(n):02d}.json"
        if not f.exists():
            print(f"T{int(n):02d}: no raw file"); continue
        raw = json.loads(f.read_text())
        missing = truth.get("expect", {}).get("missing", [])
        sections, checks = score_table(int(n), tt, raw, lambda s, n=int(n): f"T{n:02d} {s}" in missing)
        report["tables"][n] = dict(profile=tt["profile"], summary=summarise(sections), sections=sections, checks=checks)
    f = run / "raw" / "commitments.json"
    if f.exists():
        sections, checks = score_cards(truth["cards"], json.loads(f.read_text()))
        report["cards"] = dict(summary=summarise(sections), sections=sections, checks=checks)
    lab = run / "labels-blind.json"
    if lab.exists():
        man = json.loads((run / "manifest.json").read_text())
        blind = json.loads(lab.read_text())["photos"]
        res = []
        for p in man["photos"]:
            want = truth["photos"].get(Path(p["source"]).name) or truth["photos"].get(Path(p["source"]).with_suffix(".HEIC").name)
            got = blind.get(p["id"], {})
            if want is None:   # a photo this answer key doesn't know: a different inbox, or one added by hand
                print(f"note: {p['source']} isn't in the answer key; not scored")
                continue
            if want["sheet"] == "stubs":
                ok = got.get("kind") == "stubs"
            else:
                # round 3: one photo of two sheets is "S2+S3" in the key and ["S2", "S3"] in labels (ingest v0.4.2)
                sheet = got.get("sheet")
                sheet = "+".join(sheet) if isinstance(sheet, list) else sheet
                ok = got.get("table") == want["table"] and sheet == want["sheet"]
            res.append(dict(id=p["id"], want=want, got=got, ok=ok))
        report["labels"] = res

    tot = {k: 0 for k in ("items", "exact", "flagged", "silent", "missed", "extra", "over_flagged")}
    print(f"{'Table':6} {'items':>5} {'exact':>5} {'flag':>5} {'SILENT':>6} {'miss':>5} {'extra':>5} {'words%':>7}  profile")
    for n, t in list(report["tables"].items()) + ([("cards", report["cards"])] if report["cards"] else []):
        s = t["summary"]
        for k in tot:
            tot[k] += s[k]
        print(f"{('T%02d' % int(n)) if n != 'cards' else 'Cards':6} {s['items']:>5} {s['exact']:>5} {s['flagged']:>5} {s['silent']:>6} {s['missed']:>5} {s['extra']:>5} {s['word_acc']:>7}  {t.get('profile', 'commitment card halves')[:60]}")
    print(f"{'All':6} {tot['items']:>5} {tot['exact']:>5} {tot['flagged']:>5} {tot['silent']:>6} {tot['missed']:>5} {tot['extra']:>5}")
    print(f"\nCorrect but marked unsure anyway: {tot['over_flagged']}")
    print("\nSILENT ERRORS (wrong and unflagged):")
    for n, t in list(report["tables"].items()) + ([("cards", report["cards"])] if report["cards"] else []):
        for s in t["sections"]:
            for r in s["rows"]:
                if r["kind"] == "silent":
                    print(f"  {n:>5} {s['section']:<16} want: {r['gt']}\n  {'':>5} {'':<16} got:  {r['got']}")
    print("\nMISSED:")
    for n, t in list(report["tables"].items()) + ([("cards", report["cards"])] if report["cards"] else []):
        for s in t["sections"]:
            for r in s["rows"]:
                if r["kind"] == "missed":
                    print(f"  {n:>5} {s['section']:<16} {r['gt']}")
    print("\nEXTRA (not on the sheet as an item):")
    for n, t in list(report["tables"].items()) + ([("cards", report["cards"])] if report["cards"] else []):
        for s in t["sections"]:
            for x in s["extra"]:
                print(f"  {n:>5} {s['section']:<16} {x}")
    print("\nCHECKS:")
    for n, t in list(report["tables"].items()) + ([("cards", report["cards"])] if report["cards"] else []):
        for name, ok, detail in t["checks"]:
            print(f"  {'PASS' if ok else 'FAIL'}  {n:>5} {name}: {detail}")
    if "labels" in report:
        bad = [r for r in report["labels"] if not r["ok"]]
        print(f"\nBLIND LABELLING: {len(report['labels']) - len(bad)} of {len(report['labels'])} photos right")
        for r in bad:
            print(f"  {r['id']}: want {r['want']}, got {r['got']}")
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
