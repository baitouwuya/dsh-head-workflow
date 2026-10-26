# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Bounded background jobs, called only through the official Blender tool."""
import json,re,subprocess,time,threading,os
from pathlib import Path
from types import SimpleNamespace
from head_repair.config import write,sha

def launch(workspace,profile,name,overrides=()):
    import bpy
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*',name):raise ValueError('Use a simple iteration name')
    root=Path(workspace);out=root/'workflow/iterations'/name
    if out.exists():raise FileExistsError('Iteration already exists: '+str(out))
    log_path=root/'workflow/logs'/(name+'.log');log_path.parent.mkdir(parents=True,exist_ok=True)
    if log_path.exists():raise FileExistsError('Iteration log already exists')
    args=[bpy.app.binary_path,'--background','--factory-startup','--disable-autoexec','--threads','2','--python-exit-code','1','--python',str(Path(__file__).with_name('repair.py')),'--','--profile',str(profile),'--workspace',str(root),'--output',str(out)]
    for value in overrides:args+=['--set',value]
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    log=log_path.open('w',encoding='utf-8');started=time.perf_counter();process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000,env=env)
    job=SimpleNamespace(process=process,log=log,log_path=log_path,out=out,args=args,started=started,finished=None,finalized=False)
    def monitor():process.wait();job.finished=time.perf_counter()
    threading.Thread(target=monitor,daemon=True).start();return job

def poll(job):
    code=job.process.poll();result={'pid':job.process.pid,'exit_code':code,'execution_seconds':round(job.finished-job.started,3) if job.finished is not None else None,'completion_observed_after_seconds':round(time.perf_counter()-job.started,3),'output':str(job.out),'log':str(job.log_path)}
    if code is None or job.finalized:return result
    job.log.close();job.finalized=True
    if job.out.exists():
        (job.out/'engine.log').write_bytes(job.log_path.read_bytes());path=job.out/'manifest.json';m=json.loads(path.read_text()) if path.exists() else {};m['native_exit_code']=code;m['execution_seconds']=result['execution_seconds'];m['completion_observed_after_seconds']=result['completion_observed_after_seconds']
        if code!=0:m['status']='failed';m.setdefault('error','Background Blender exited with code '+str(code))
        m['outputs']={str(f.relative_to(job.out)):sha(f) for f in sorted(job.out.rglob('*')) if f.is_file() and f.name not in ('manifest.json','SHA256SUMS.txt')};write(path,m)
        (job.out/'SHA256SUMS.txt').write_text('\n'.join(sha(f)+'  '+str(f.relative_to(job.out)) for f in sorted(job.out.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt')+'\n')
    return result

def stop(job):
    if job.process.poll() is None:job.process.terminate()
    return {'pid':job.process.pid,'stop_requested':True,'note':'Only this workflow-owned background process was targeted; poll to confirm exit.'}
