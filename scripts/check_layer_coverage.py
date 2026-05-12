"""
Per-layer coverage gate.

Parses coverage.xml (Cobertura format from pytest-cov) and asserts that the
union of files whose path contains `/<layer>/` meets a minimum line-coverage
threshold. Used in CI to enforce Rules §5:

    Domain      ≥ 95%
    Application ≥ 85%
    Overall     ≥ 80% (pytest --cov-fail-under handles this)
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET


def layer_coverage(xml_path: str, layer: str) -> float:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    hits = 0
    total = 0
    for cls in root.iter("class"):
        filename = cls.attrib.get("filename", "")
        if f"/{layer}/" not in filename:
            continue
        for line in cls.iter("line"):
            total += 1
            if int(line.attrib.get("hits", "0")) > 0:
                hits += 1
    if total == 0:
        return 100.0
    return (hits / total) * 100.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", required=True)
    parser.add_argument("--layer", required=True)
    parser.add_argument("--min", type=float, required=True)
    args = parser.parse_args()

    pct = layer_coverage(args.xml, args.layer)
    print(f"{args.layer} layer coverage: {pct:.2f}% (min {args.min}%)")
    if pct + 1e-6 < args.min:
        print(f"FAIL: {args.layer} coverage below threshold", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
