# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,pathlib,json,math,numpy as np
def shell_unit(longitudes,latitudes,rim_steps,eps,upper):
    pts=[[0.,0.,1+eps]];faces=[];prev=None
    rings=[]
    for j in range(1,latitudes+1):
        th=np.pi*j/(2*latitudes);rr=1+eps
        rings.append([(rr*np.sin(th)*np.cos(ph),rr*np.sin(th)*np.sin(ph),rr*np.cos(th)) for ph in np.linspace(0,2*np.pi,longitudes,endpoint=False)])
    for j in range(1,rim_steps+1):
        alpha=np.pi*j/rim_steps;rr=1+eps*np.cos(alpha);z=-eps*np.sin(alpha)
        rings.append([(rr*np.cos(ph),rr*np.sin(ph),z) for ph in np.linspace(0,2*np.pi,longitudes,endpoint=False)])
    for j in range(1,latitudes):
        th=np.pi/2-np.pi*j/(2*latitudes);rr=1-eps
        rings.append([(rr*np.sin(th)*np.cos(ph),rr*np.sin(th)*np.sin(ph),rr*np.cos(th)) for ph in np.linspace(0,2*np.pi,longitudes,endpoint=False)])
    for row in rings:
        curr=list(range(len(pts),len(pts)+len(row)));pts.extend(row)
        if prev is None:
            for i in range(longitudes):faces.append([0,curr[i],curr[(i+1)%longitudes]])
        else:
            for i in range(longitudes):
                j=(i+1)%longitudes;faces.extend([[prev[i],curr[i],curr[j]],[prev[i],curr[j],prev[j]]])
        prev=curr
    pole=len(pts);pts.append([0,0,1-eps])
    for i in range(longitudes):faces.append([prev[i],pole,prev[(i+1)%longitudes]])
    pts=np.array(pts)
    if not upper:pts[:,2]*=-1;faces=[f[::-1] for f in faces]
    return pts,faces
def build(profile,cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);scene=bpy.data.scenes[cfg['scene']]
    col=bpy.data.collections.new('INTERNAL_ONLY_rounded_lids_'+cfg['revision']);scene.collection.children.link(col)
    helper={};exec((root/'scripts'/'sm_eye_integration.py').read_text(),helper)
    skin=bpy.data.objects['INTERNAL_ONLY__SM_000_protected_facial_skin']
    report={'classification':'INTERNAL_ONLY','status':'UNACCEPTED','profile':cfg,'objects':[]}
    for eye in profile['character']['eyes']:
        fit=eye['native_fit'];gy,gz=eye['sphere_center'][1:];ry=fit['radius_y'];rz=fit['radius_z'];rx=fit['depth_radius'];co=np.array(fit['front_base_coefficients'])
        rim=np.array(eye['rim_xyz']);ymin,ymax=rim[:,1].min(),rim[:,1].max()
        for upper in [True,False]:
            unit,faces=shell_unit(cfg['longitudes'],cfg['latitudes'],cfg['rim_steps'],cfg['shell_fraction'],upper)
            states={};checks=[]
            for blink in cfg['samples']:
                opening=cfg['open_angles_degrees'][eye['label']]['upper' if upper else 'lower']
                angle=(-1 if upper else 1)*(1-blink)*np.radians(opening);ct,st=np.cos(angle),np.sin(angle)
                rot=unit.copy();rot[:,0]=ct*unit[:,0]+st*unit[:,2];rot[:,2]=-st*unit[:,0]+ct*unit[:,2]
                u=rot[:,1];v=rot[:,2];base=co[0]+co[1]*u+co[2]*v+co[3]*u*u+co[4]*u*v+co[5]*v*v
                xyz=np.column_stack((base+rx*rot[:,0]+cfg['clearance_m']+cfg.get('closing_lift_m',0)*blink+(cfg['seam_lap_m'] if upper else 0),gy+ry*u,gz+rz*v)).astype(np.float32).astype(float)
                states[str(blink)]=xyz
                a=helper['_topology'](xyz,faces);checks.append({'blink':blink,**a})
            name='INTERNAL_ONLY_'+eye['label']+('_upper' if upper else '_lower')+'_rounded_lid_'+cfg['revision']
            mesh=bpy.data.meshes.new(name);mesh.from_pydata(states['0'].tolist(),[],faces);mesh.update();ob=bpy.data.objects.new(name,mesh);col.objects.link(ob)
            if cfg.get('material_mode')=='source_palette':
                mat=bpy.data.materials.get('INTERNAL_ONLY_source_palette_'+cfg['revision'])
                if mat is None:
                    mat=bpy.data.materials.new('INTERNAL_ONLY_source_palette_'+cfg['revision']);mat.use_nodes=True
                    rgb=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in cfg['source_palette_srgb']]
                    mat.diffuse_color=(*rgb,1);bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(*rgb,1);bs.inputs['Roughness'].default_value=.9
                mesh.materials.append(mat)
            else:
                for mat in skin.data.materials:mesh.materials.append(mat)
            uvrows=[]
            for p in states['0']:
                y=float(np.clip(p[1],ymin+1e-8,ymax-1e-8));lo,hi=helper['_bounds'](rim,y);support=(hi if upper else lo).copy();support[2]+=(1 if upper else -1)*cfg['skin_uv_margin_m']
                uv,evidence=helper['_skin_uv'](skin,support,.02);uvrows.append(uv)
            uv=mesh.uv_layers.new(name='UVMap')
            for l in mesh.loops:uv.data[l.index].uv=uvrows[l.vertex_index]
            for f in mesh.polygons:f.use_smooth=True
            ob.shape_key_add(name='Basis')
            for b in cfg['samples']:
                if b==0:continue
                k=ob.shape_key_add(name='blink_'+str(int(b*100)));k.value=0;k.data.foreach_set('co',states[str(b)].astype(np.float32).ravel())
            ob['classification']='INTERNAL_ONLY';ob['role']='eyelid';ob['eye']=eye['label'];ob['acceptance']='UNACCEPTED'
            report['objects'].append({'name':name,'eye':eye['label'],'upper':upper,'checks':checks})
    (root/(cfg['revision']+'-rounded-lids.json')).write_text(json.dumps(report,indent=2));return report
