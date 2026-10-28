# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert a private embedded GLB/VRM to a fresh private PD pack directory."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from head_workflow.pd_pack.convert import convert

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(convert(args.source, args.output), indent=2))
