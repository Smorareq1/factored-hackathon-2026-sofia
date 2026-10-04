"""Fill the `{{file:key}}` placeholders in the docs from the versioned result files (DS).

    uv run --package sofia-analysis python analysis/fill_placeholders.py          # check what resolves
    uv run --package sofia-analysis python analysis/fill_placeholders.py --write  # replace in place

Default targets: README.md, docs/*.md, docs/slides/*.md. Paths: `results/x.json` → analysis/results/x.json; anything
else is relative to the repo root. Key syntax: `a.b` nested keys (keys may contain dots, e.g. `rules-ds-0.1`: the
longest matching key wins), `list[0]` by index, `list[X]` the element whose first field equals X, `"quoted key"`.
`.py` files resolve `GEMINI_PRICE_*`-style settings from their `default=…, validation_alias="NAME"`.
`{{PENDIENTE:…}}` is never touched. Metric objects from ds_stats render as `rate [95% CI], n` / `value [95% CI], n`.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"\{\{([^{}]+)\}\}")
DEFAULT_TARGETS = ("README.md", "docs/*.md", "docs/slides/*.md")


class Missing(Exception):
    pass


def source_path(name: str) -> Path:
    return ROOT / "analysis" / name if name.startswith("results/") else ROOT / name


def load(name: str, cache: dict[str, Any]) -> Any:
    if name not in cache:
        path = source_path(name)
        if not path.exists():
            raise Missing(f"file not found: {name}")
        cache[name] = path.read_text(encoding="utf-8") if name.endswith(".py") else json.loads(path.read_text("utf-8"))
    return cache[name]


def resolve(obj: Any, rest: str) -> Any:
    rest = rest.lstrip(".")
    if not rest:
        return obj
    if rest.startswith("["):
        inner, rest = rest[1:].split("]", 1)
        if not isinstance(obj, list):
            raise Missing(f"[{inner}] on a non-list")
        if inner.isdigit():
            if int(inner) >= len(obj):
                raise Missing(f"index {inner} out of range")
            return resolve(obj[int(inner)], rest)
        match = next((e for e in obj if isinstance(e, dict) and e and str(next(iter(e.values()))) == inner), None)
        if match is None:
            raise Missing(f"no element [{inner}]")
        return resolve(match, rest)
    if not isinstance(obj, dict):
        raise Missing(f"key {rest!r} on a non-object")
    if rest.startswith('"'):
        key, rest = rest[1:].split('"', 1)
        if key not in obj:
            raise Missing(f"no key {key!r}")
        return resolve(obj[key], rest)
    candidates = [k for k in obj if rest == k or rest.startswith(k + ".") or rest.startswith(k + "[")]
    if not candidates:
        raise Missing(f"no key for {rest!r}")
    key = max(candidates, key=len)
    return resolve(obj[key], rest[len(key) :])


def resolve_py(source: str, name: str) -> Any:
    found = re.search(rf'default=([0-9.]+),\s*validation_alias="{re.escape(name)}"', source)
    if not found:
        raise Missing(f"no default for {name}")
    return float(found.group(1))


def number(x: float) -> str:
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, int):
        return f"{x:,}"
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:.4g}"


def render(value: Any) -> str:
    if value is None:
        return "not defined"
    if isinstance(value, dict) and "ci" in value and ("rate" in value or "value" in value):
        is_rate = "rate" in value
        point = value["rate"] if is_rate else value["value"]
        if point is None:
            return f"not defined, n = {value.get('n', '?')}"
        fmt = (lambda v: f"{100 * v:.1f}%") if is_rate else number
        ci = f" [{fmt(value['ci'][0])}–{fmt(value['ci'][1])}]" if value.get("ci") else ""
        return f"{fmt(point)}{ci}, n = {value.get('n', '?')}"
    if isinstance(value, list):
        if value and all(isinstance(e, dict) for e in value):
            return "; ".join(", ".join(f"{k}: {render(v)}" for k, v in list(e.items())[:3]) for e in value)
        return ", ".join(render(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {render(v)}" for k, v in value.items())
    if isinstance(value, (int, float)):
        return number(value)
    return str(value)


def fill(text: str, cache: dict[str, Any]) -> tuple[str, list[tuple[str, str]]]:
    """Returns the filled text and a (placeholder, status) list; unresolved placeholders stay as they are."""
    report = []

    def sub(m: re.Match) -> str:
        body = m.group(1)
        if body.startswith("PENDIENTE:"):
            report.append((body, "pending"))
            return m.group(0)
        name, _, key = body.partition(":")
        if not name.endswith((".json", ".py")):  # prose examples like {{file:key}} or {{…}}
            return m.group(0)
        try:
            data = load(name, cache)
            value = resolve_py(data, key) if name.endswith(".py") else resolve(data, key)
        except (Missing, ValueError) as exc:
            report.append((body, f"missing ({exc})"))
            return m.group(0)
        report.append((body, "ok"))
        return render(value)

    return PLACEHOLDER.sub(sub, text), report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="markdown files (default: README and docs)")
    parser.add_argument("--write", action="store_true", help="replace resolved placeholders in place")
    args = parser.parse_args()
    files = [Path(f) for f in args.files] or sorted({p for pat in DEFAULT_TARGETS for p in ROOT.glob(pat)})

    cache: dict[str, Any] = {}
    totals = {"ok": 0, "pending": 0, "missing": 0}
    for path in files:
        text = path.read_text(encoding="utf-8")
        filled, report = fill(text, cache)
        counts = {s: sum(1 for _, st in report if st.startswith(s)) for s in totals}
        for s in totals:
            totals[s] += counts[s]
        print(f"{path.relative_to(ROOT) if path.is_absolute() else path}: {counts}")
        for body, status in report:
            if status.startswith("missing"):
                print(f"  - {{{{{body}}}}}  {status}")
        if args.write and filled != text:
            path.write_text(filled, encoding="utf-8")
    print(f"total: {totals}" + ("" if args.write else "  (check only; --write to replace)"))
    sys.exit(0)


if __name__ == "__main__":
    main()
