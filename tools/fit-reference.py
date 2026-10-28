# SPDX-License-Identifier: GPL-3.0-or-later
"""Fit a normalized reference without Blender or private reference packs."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from head_workflow.reference.fit import fit_lid_profile

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--degree',type=int,default=6)
    parser.add_argument('--shell-thickness',type=float,help='eye-width units; caller choice, not measured')
    args = parser.parse_args()
    profile = json.loads(args.reference.read_text(encoding='utf-8-sig'))
    fit = fit_lid_profile(profile,args.degree,args.shell_thickness)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(fit,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(json.dumps({k:{'rms':v['fit_rms'],'max':v['fit_max']} for k,v in fit['eyes'].items()}))

if __name__ == '__main__':
    main()
