# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Rebuild renderable original-lash blink arrays from runtime native evidence.

This source-only entrypoint does not export a model. The native Lab assembles,
exports, reimports and renders its own artifact; visual motion is acceptance.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--boundaries',required=True);parser.add_argument('--probes',required=True);parser.add_argument('--roles',required=True);parser.add_argument('--configuration',required=True);parser.add_argument('--repository',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();sys.path.insert(0,args.repository)
    from lab_recipes.source_band_margin import fit_source_band_margins
    from lab_recipes.original_lash_motion import build_original_lash_motion
    out=Path(args.output)
    if out.exists():raise ValueError('Output directory already exists; preserve prior evidence')
    paths={k:Path(getattr(args,k)) for k in ['source','boundaries','probes','roles','configuration']};hashes={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()};source=dict(np.load(paths['source']));boundaries=dict(np.load(paths['boundaries']));probes=dict(np.load(paths['probes']));roles=json.loads(paths['roles'].read_text());cfg=json.loads(paths['configuration'].read_text());scale=float(np.ptp(source['vertices'][:,2]));fitted=fit_source_band_margins(source,boundaries,probes,roles,cfg,scale);motion=build_original_lash_motion(source,fitted['arrays'],probes,roles,cfg,scale);unchanged=all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[k] for k,p in paths.items())
    if not unchanged:raise ValueError('Runtime inputs changed during construction')
    out.mkdir(parents=True,exist_ok=False);np.savez(out/'hoods.npz',**fitted['arrays']);np.savez(out/'source-motion.npz',**motion['arrays']);report={'source_scale':scale,'input_hashes':hashes,'input_files_unchanged':unchanged,'margin_fit':fitted['report'],'source_motion':motion['report'],'control_values':cfg['controls']['blink']['samples'],'acceptance':'Native Lab renders of its own exported/reimported artifact in front, oblique and profile close/reopen motion','host_generated_model_uploaded':False};(out/'report.json').write_text(json.dumps(report,indent=2));print('Renderable original-lash blink arrays built; visual review required.')
if __name__=='__main__':main()
