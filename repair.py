# SPDX-License-Identifier: GPL-3.0-or-later
"""One entry point: change profile parameters, then rerun."""
import argparse,sys,traceback,time,hashlib,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from head_repair.config import load,write,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',required=True);p.add_argument('--workspace',required=True);p.add_argument('--output',required=True);p.add_argument('--set',action='append',default=[]);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    profile,changes=load(a.profile,a.set);workspace=Path(a.workspace);out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    write(out/'resolved-profile.json',profile);write(out/'parameter-diff.json',changes)
    root=Path(__file__).parent;files=sorted(root.rglob('*.py'));sources={str(f.relative_to(root)):sha(f) for f in files};digest=hashlib.sha256(str(sorted(sources.items())).encode()).hexdigest();archive=root/'source-archives'/f'{digest}.zip';archive.parent.mkdir(exist_ok=True)
    if not archive.exists():
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for f in files:z.write(f,str(f.relative_to(root)))
    inputs={name:(workspace/path).resolve() for name,path in profile['inputs'].items()}
    hashes={name:sha(path) for name,path in inputs.items() if path.is_file()}
    for name,path in inputs.items():
        sidecar=Path(str(path)+'.json')
        if sidecar.is_file():hashes[name+'.json']=sha(sidecar)
    # Include every source sidecar consumed by the build, not just the Blend.
    for path in sorted(inputs['source'].rglob('*.json')):hashes['source/'+str(path.relative_to(inputs['source']))]=sha(path)
    manifest={'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source_sha256':digest,'source_files':sources,'profile_sha256':sha(out/'resolved-profile.json'),'input_sha256':hashes,'credit_balance_before':None,'credit_balance_after':None,'credit_note':'Host-only reconstruction; no Tripo request','status':'running'}
    write(out/'manifest.json',manifest)
    try:
        from head_repair.pipeline import run
        run(profile,inputs,out);manifest['status']='candidate_measured'
    except Exception as error:
        manifest['status']='failed';manifest['error']=str(error);(out/'error.txt').write_text(traceback.format_exc());raise
    finally:
        manifest['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());manifest['outputs']={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name not in ('manifest.json','SHA256SUMS.txt')};write(out/'manifest.json',manifest)
        (out/'SHA256SUMS.txt').write_text('\n'.join(sha(f)+'  '+str(f.relative_to(out)) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt')+'\n')

if __name__=='__main__':main()
