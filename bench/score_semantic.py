#!/usr/bin/env python3
"""Score the unnamed semantic-retrieval probe (SpecPrefill quality).

Ground truth comes from ``bench/prompts/semantic-specprefill-128k.json``:
exactly one planted entry is ``audit-status: quarantined`` and exactly one
(different) entry is ``flag: amber-flagged``. Neither is named in the question,
so a correct answer means the sparse prefill kept chunks the selector had to
find by meaning.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re


def extract_content(result: dict) -> str:
    if isinstance(result.get("content"), str) and result["content"]:
        return result["content"]
    for measurement in reversed(result.get("measurements", [])):
        if isinstance(measurement.get("content"), str) and measurement["content"]:
            return measurement["content"]
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True)
    parser.add_argument(
        "--map",
        default="bench/prompts/semantic-specprefill-128k.json",
    )
    parser.add_argument("--write")
    args = parser.parse_args()

    ground = json.loads(pathlib.Path(args.map).read_text(encoding="utf-8"))
    expected = ground["expected"]
    result = json.loads(pathlib.Path(args.result).read_text(encoding="utf-8"))
    content = extract_content(result)

    def find(pair: str) -> bool:
        wanted = pair.replace(" ", "")
        if wanted in content.replace(" ", ""):
            return True
        entry, code = pair.split("=")
        for line in content.splitlines():
            if entry in line and code in line:
                return True
        return False

    quarantined_ok = find(expected["quarantined"])
    amber_ok = find(expected["amber"])
    swapped = (
        expected["quarantined"].split("=")[1] in content
        and expected["amber"].split("=")[1] in content
        and not (quarantined_ok and amber_ok)
    )
    codes = re.findall(r"\b[A-Z]{2,4}-?\d{3,5}\b", content)
    planted = {fact["code"] for fact in ground["facts"]}

    report = {
        "expected": expected,
        "quarantinedCorrect": quarantined_ok,
        "amberCorrect": amber_ok,
        "score": int(quarantined_ok) + int(amber_ok),
        "total": 2,
        "bothCodesPresentButMisattributed": swapped,
        "plantedCodesEmitted": sorted(set(codes) & planted),
        "unknownCodes": sorted(set(codes) - planted),
        "content": content,
    }
    if args.write:
        pathlib.Path(args.write).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "score": f"{report['score']}/{report['total']}",
                "quarantinedCorrect": quarantined_ok,
                "amberCorrect": amber_ok,
                "misattributed": swapped,
                "unknownCodes": report["unknownCodes"],
                "contentHead": content[:400],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
