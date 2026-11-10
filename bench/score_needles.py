#!/usr/bin/env python3
"""Score a bench result against a needle map (SpecPrefill quality measurement).

Works with both needle-map formats in use:

* ``bench/prompts/needles-120000.needles.json`` — ``{"vault": ..., "code": ...}``
* ``bench/prompts/needles-specprefill-128k.json`` — ``{"entry": ..., "code": ...}``

Reports three independent signals:

* **exact recall** — planted codes that appear anywhere in the answer;
* **attribution** — planted codes printed next to the right needle key;
* **hallucination** — emitted codes that were never planted.

Depth buckets require ``--prompt`` and the target tokenizer so the script can
map each needle to its token position in the prompt.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re

CODE_RE = re.compile(r"\b[A-Z]{2,4}-?\d{3,5}\b")


def load_map(path: pathlib.Path) -> tuple[dict, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    needles = []
    for needle in data.get("needles", []):
        if "vault" in needle:
            key = needle["vault"]
        elif "entry" in needle:
            key = needle["entry"]
        else:
            raise SystemExit(f"needle entry has no vault/entry key: {needle}")
        needles.append({"key": key, "code": needle["code"]})
    return data, needles


def extract_content(result: dict) -> str:
    if isinstance(result.get("content"), str) and result["content"]:
        return result["content"]
    for measurement in reversed(result.get("measurements", [])):
        if isinstance(measurement.get("content"), str) and measurement["content"]:
            return measurement["content"]
    return ""


def prime_depths(prompt_path: pathlib.Path, needles: list[dict], tokenizer_path: pathlib.Path) -> None:
    try:
        from tokenizers import Tokenizer  # type: ignore
    except Exception:
        return
    if not tokenizer_path.exists():
        return
    text = prompt_path.read_text(encoding="utf-8")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    total = len(tokenizer.encode(text).ids)
    for needle in needles:
        marker = str(needle["code"])
        at = text.find(marker)
        if at < 0:
            at = text.find(str(needle["key"]))
        if at < 0:
            continue
        needle["tokenIndex"] = len(tokenizer.encode(text[:at]).ids)
        needle["depth"] = needle["tokenIndex"] / total if total else None


def score(content: str, needles: list[dict]) -> dict:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    emitted = CODE_RE.findall(content)
    planted = {needle["code"] for needle in needles}
    details = []
    exact = 0
    attributed = 0
    for needle in needles:
        key, want = str(needle["key"]), needle["code"]
        found = None
        for line in lines:
            if key in line:
                codes = CODE_RE.findall(line)
                if codes:
                    found = codes[0]
                    break
        exact_ok = want in emitted
        attributed_ok = found == want
        exact += int(exact_ok)
        attributed += int(attributed_ok)
        details.append(
            {
                "key": key,
                "want": want,
                "found": found,
                "exact": exact_ok,
                "attributed": attributed_ok,
                "depth": needle.get("depth"),
                "tokenIndex": needle.get("tokenIndex"),
            }
        )
    try:
        from tokenizers import Tokenizer  # type: ignore

        tokenizer = None
    except Exception:
        tokenizer = None
    return {
        "total": len(needles),
        "exact": exact,
        "attributed": attributed,
        "exactAccuracy": exact / len(needles) if needles else None,
        "attributionAccuracy": attributed / len(needles) if needles else None,
        "hallucinated": sorted({code for code in emitted if code not in planted}),
        "details": details,
    }


def first_divergence(reference: str, candidate: str) -> dict:
    limit = min(len(reference), len(candidate))
    for i in range(limit):
        if reference[i] != candidate[i]:
            return {
                "charIndex": i,
                "reference": reference[max(0, i - 70) : i + 70],
                "candidate": candidate[max(0, i - 70) : i + 70],
            }
    if len(reference) != len(candidate):
        return {
            "charIndex": limit,
            "reference": reference[max(0, limit - 70) : limit + 70],
            "candidate": candidate[max(0, limit - 70) : limit + 70],
        }
    return {"charIndex": None, "reference": None, "candidate": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, help="bench result JSON")
    parser.add_argument("--map", required=True, help="needle map JSON")
    parser.add_argument("--prompt", help="prompt file (enables depth buckets)")
    parser.add_argument(
        "--tokenizer",
        default="~/.lmstudio/models/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed/tokenizer.json",
    )
    parser.add_argument("--reference", help="dense result JSON for divergence")
    parser.add_argument("--write", help="write the scored JSON here")
    args = parser.parse_args()

    result_path = pathlib.Path(args.result)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    _, needles = load_map(pathlib.Path(args.map))
    if args.prompt:
        prime_depths(
            pathlib.Path(args.prompt), needles, pathlib.Path(args.tokenizer).expanduser()
        )
    content = extract_content(result)
    report = score(content, needles)
    if args.reference:
        reference = json.loads(pathlib.Path(args.reference).read_text(encoding="utf-8"))
        report["divergence"] = first_divergence(
            extract_content(reference), content
        )

    measurement = (result.get("measurements") or [{}])[-1]
    report["run"] = {
        "label": result.get("label"),
        "file": result_path.name,
        "keepPct": (result.get("config") or {}).get("keep_pct")
        or ((result.get("config") or {}).get("per_model_json")),
        "promptTokens": measurement.get("promptTokens"),
        "prefillTokensPerSecond": measurement.get("prefillTokensPerSecond"),
        "nativePrefillTokensPerSecond": measurement.get("nativePrefillTokensPerSecond"),
        "decodeTokensPerSecond": measurement.get("decodeTokensPerSecond"),
        "ttftSeconds": measurement.get("ttftSeconds"),
    }

    depths = [d for d in (n.get("depth") for n in report["details"]) if d is not None]
    if depths:
        buckets = {"0-25%": [], "25-50%": [], "50-75%": [], "75-100%": []}
        for item in report["details"]:
            depth = item.get("depth")
            if depth is None:
                continue
            name = (
                "0-25%"
                if depth < 0.25
                else "25-50%"
                if depth < 0.5
                else "50-75%"
                if depth < 0.75
                else "75-100%"
            )
            buckets[name].append(int(item["exact"]))
        report["depthBuckets"] = {
            name: {
                "n": len(values),
                "exact": sum(values),
                "accuracy": (sum(values) / len(values)) if values else None,
            }
            for name, values in buckets.items()
        }

    if args.write:
        pathlib.Path(args.write).write_text(
            json.dumps({"report": report, "content": content}, indent=2),
            encoding="utf-8",
        )

    print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
