# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,pathlib,json,numpy as np
def build(cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);src=bpy.data.objects[cfg['source']];body=src.copy();body.data=src.data.copy();body.name='INTERNAL_ONLY_SM_mouth_corrective_'+cfg['revision'];scene=bpy.data.scenes.new('INTERNAL_ONLY_integrated_'+cfg['revision'])
    for o in bpy.data.scenes[cfg['source_scene']].objects:
        if o!=src:scene.collection.objects.link(o)
    scene.collection.objects.link(body)
    m=body.data;base=np.array([list(v.co) for v in m.shape_keys.key_blocks['Basis'].data]);old=np.array([list(v.co) for v in m.shape_keys.key_blocks['jawOpen'].data]);new=old.copy();cy,cz=cfg['center_yz'];s=lambda x:np.clip(x,0,1)**2*(3-2*np.clip(x,0,1))
    y=abs(base[:,1]-cy);weight=s((y-.002)/.001)*(1-s((y-.006)/.004))*np.exp(-((base[:,2]-cz)/.003)**2)*s((.0175-base[:,0])/.002)*(1-s((.012-base[:,0])/.004))
    rim=set(json.loads((root/cfg['entrance_report']).read_text())['rim_vertices'])
    for i in rim:weight[i]=0
    native_vertices={v for f in m.polygons if f.material_index==0 for v in f.vertices};weight=np.array([w if i in native_vertices else 0 for i,w in enumerate(weight)])
    new[:,0]-=cfg['retreat_m']*weight;new[:,1]+=cfg['widen_m']*np.sign(base[:,1]-cy)*weight
    m.shape_keys.key_blocks['jawOpen'].data.foreach_set('co',new.astype(np.float32).ravel());m.shape_keys.key_blocks['jawOpen'].value=0
    fs=[list(f.vertices) for f in m.polygons];audit=[]
    for deg in cfg['degrees']:
        v=base+(new-base)*(deg/15);a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](v,fs,fs,np.arange(len(fs)),reference_local_vertices=base,local_vertices=v);audit.append({'degrees':deg,**{k:a[k] for k in ['boundary_edges','nonmanifold_edges','degenerate_triangles','adjacent_normal_degrees','reference_normal_reversals']}})
    report={'classification':'INTERNAL_ONLY','profile':cfg,'object':body.name,'scene':scene.name,'affected_vertices':int((weight>1e-8).sum()),'maximum_extra_full_jaw_displacement_m':float(np.linalg.norm(new-old,axis=1).max()),'neutral_changed':False,'entrance_vertices_pinned':len(rim),'audit':audit};(root/(cfg['revision']+'-mouth-corrective.json')).write_text(json.dumps(report,indent=2));return report
