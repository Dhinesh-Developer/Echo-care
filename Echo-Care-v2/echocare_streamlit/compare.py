"""Side-by-side comparison of two specialist opinions with word-level difference highlighting
and simple, explainable conflict signals (no LLM needed)."""
import difflib
import html
import re

NEGATION = re.compile(r"\b(no|not|without|unlikely|rule[sd]? out|normal|negative|absent|nothing|never)\b", re.I)
STOP = set("the a an and or of to in on for with is are was were be this that it as at by from".split())


def _norm(tok: str) -> str:
    return tok.lower().strip(".,;:!?()\"'")


def diff_html(a: str, b: str) -> tuple[str, str]:
    ta, tb = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, [_norm(t) for t in ta], [_norm(t) for t in tb])
    out_a, out_b = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        seg_a, seg_b = html.escape(" ".join(ta[i1:i2])), html.escape(" ".join(tb[j1:j2]))
        if tag == "equal":
            out_a.append(seg_a)
            out_b.append(seg_b)
        else:
            if seg_a:
                out_a.append(f'<mark class="ec-diff-a">{seg_a}</mark>')
            if seg_b:
                out_b.append(f'<mark class="ec-diff-b">{seg_b}</mark>')
    return " ".join(out_a), " ".join(out_b)


def conflict_signals(a: str, b: str) -> dict:
    words_a = {_norm(w) for w in a.split() if len(_norm(w)) > 3 and _norm(w) not in STOP}
    words_b = {_norm(w) for w in b.split() if len(_norm(w)) > 3 and _norm(w) not in STOP}
    shared = sorted(words_a & words_b)
    sim = difflib.SequenceMatcher(None, a.lower().split(), b.lower().split()).ratio()
    neg_mismatch = bool(NEGATION.search(a)) != bool(NEGATION.search(b))
    return {"similarity": round(sim, 2), "shared_terms": shared[:8], "negation_mismatch": neg_mismatch,
            "possible_conflict": len(shared) >= 2 and neg_mismatch}
