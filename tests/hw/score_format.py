#!/usr/bin/env python3
"""Score a run's transcriptions against a format test's answer key (made by make_format_test.py).

    python3 tests/hw/score_format.py runs/<run> tests/hw/retro/truth.json

For every answer the reader should have written, it finds the reader's closest item in the same box and sorts it:

    right      the same words (after ignoring case, punctuation and [?…] markers' brackets)
    flagged    not the same, but the reader marked it ([?word], [illegible], or in their unclear list): a person checks it
    silent     wrong and unflagged: the number that matters, because it would reach the page unnoticed
    missing    no item in the reader's file matches it

Dot votes must match exactly (a wrong count the reader flagged is "flagged"). A row's parts (what, who, when) are
scored one by one. Items the reader wrote that match no answer are listed as extra (an invented or split item).
"""
import argparse, difflib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "build"))
import config  # noqa: E402
import formats  # noqa: E402

RIGHT, CLOSE = 0.92, 0.55


def norm(s):
    # a certain expansion the reader added in brackets ("DoD [definition of done]") isn't part of what was written
    s = re.sub(r"\s*\[(?!\?|illegible\])[^\]]*\]", "", str(s or ""))
    s = re.sub(r"\[\?([^\]]*)\]", r"\1", s)
    s = s.lower().replace("’", "'").replace("&", "and")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", " ", s)).strip()


def sim(a, b):
    a, b = norm(a), norm(b)
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else (1.0 if a == b else 0.0)


def marked(s):
    return bool(re.search(r"\[\?|\[illegible\]", str(s or "")))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run")
    ap.add_argument("truth")
    a = ap.parse_args()
    run, truth = Path(a.run), json.loads(Path(a.truth).read_text())
    cfg = config.load(str(ROOT / "tests" / "golden" / f"{truth['workshop']}.config.json"))
    W = formats.load(cfg, truth["workshop"])
    tally = {"right": 0, "flagged": 0, "silent": 0, "missing": 0, "extra": 0}
    silent, flagged_list, extras, struck = [], [], [], []

    def judge(where, want, got, unclear_ids, gid, flag_ok=()):
        s = sim(want, got)
        kept = [w for line, w in struck if line == want and norm(w) in norm(got).split() and norm(w) not in norm(want).split()]
        if kept:
            silent.append(f"{where}: \"{got}\" keeps the crossed-out word \"{kept[0]}\"")
            return "silent"
        if s >= RIGHT and not marked(got):
            return "right"
        if marked(got) or gid in unclear_ids:
            flagged_list.append(f"{where}: \"{got}\" (answer \"{want}\")")
            return "flagged"
        if s >= RIGHT:
            return "right"
        if want in flag_ok and s >= 0.75:
            flagged_list.append(f"{where}: \"{got}\" (answer \"{want}\", scribbled word: right or flagged)")
            return "flagged"
        silent.append(f"{where}: \"{got}\" but the sheet says \"{want}\" ({s:.0%} alike)")
        return "silent"

    for t, answers in truth["teams"].items():
        f = run / "raw" / f"T{int(t):02d}.json"
        raw = json.loads(f.read_text()) if f.exists() else {}
        unclear_ids = {u.get("id") for u in raw.get("unclear", [])}
        flag_ok = set(answers.get("flag_ok", []))
        struck[:] = [tuple(x) for x in answers.get("struck", [])]
        for e in W.per_group():
            code = e["code"]
            if code not in answers:
                continue
            for b in e["boxes"]:
                key = b["key"]
                if key not in answers[code]:
                    continue
                want, got = answers[code][key], (raw.get(code) or {}).get(key)
                where = f"T{int(t):02d}.{code}.{key}"
                if b["type"] == "text":
                    got_text = (got or {}).get("text", "") if isinstance(got, dict) else ""
                    r = judge(where, want, got_text, unclear_ids, (got or {}).get("id") if isinstance(got, dict) else None, flag_ok) if got_text else "missing"
                    tally[r] += 1
                    continue
                got = list(got or [])
                used = set()
                for i, w in enumerate(want):
                    wtext = w.get(b.get("text_field", "text")) if isinstance(w, dict) else w
                    field = b.get("text_field", "text")
                    best = max(((sim(wtext, g.get(field, "")), j) for j, g in enumerate(got) if j not in used), default=(0, None))
                    if best[1] is None or best[0] < CLOSE:
                        tally["missing"] += 1
                        silent.append(f"{where} {i + 1}: \"{wtext}\" isn't in the transcription")
                        continue
                    j = best[1]
                    used.add(j)
                    g = got[j]
                    tally[judge(f"{where} {i + 1}", wtext, g.get(field, ""), unclear_ids, g.get("id"), flag_ok)] += 1
                    if b["type"] == "list+votes":
                        if int(g.get("votes") or 0) == w.get("votes", 0):
                            tally["right"] += 1
                        elif g.get("id") in unclear_ids:
                            tally["flagged"] += 1
                            flagged_list.append(f"{where} {i + 1}: {g.get('votes')} votes (answer {w.get('votes', 0)})")
                        else:
                            tally["silent"] += 1
                            silent.append(f"{where} {i + 1}: {g.get('votes')} votes, but the sheet has {w.get('votes', 0)}")
                    if b["type"] == "row":
                        for fld in b.get("fields", []):
                            k = fld["key"]
                            if k == field:
                                continue
                            if not w.get(k):
                                if g.get(k):
                                    tally["silent"] += 1
                                    silent.append(f"{where} {i + 1}: {k} \"{g[k]}\", but the sheet leaves it blank")
                                else:
                                    tally["right"] += 1
                                continue
                            tally[judge(f"{where} {i + 1} {k}", w[k], g.get(k, ""), unclear_ids, g.get("id"), flag_ok) if g.get(k) else "missing"] += 1
                            if not g.get(k):
                                silent.append(f"{where} {i + 1}: {k} \"{w[k]}\" isn't in the transcription")
                for j, g in enumerate(got):
                    if j not in used:
                        tally["extra"] += 1
                        extras.append(f"{where}: \"{g.get(b.get('text_field', 'text'), g)}\"")
    total = tally["right"] + tally["flagged"] + tally["silent"] + tally["missing"]
    print(f"{truth['workshop']}: {total} answers. Right {tally['right']}, flagged {tally['flagged']}, "
          f"silent errors {tally['silent']}, missing {tally['missing']}, extra items {tally['extra']}.")
    for title, rows in (("Silent errors and missing answers", silent), ("Flagged for a person to check", flagged_list), ("Extra items", extras)):
        if rows:
            print(f"\n{title}:")
            for r in rows:
                print("  - " + r)
    return 1 if tally["silent"] or tally["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
