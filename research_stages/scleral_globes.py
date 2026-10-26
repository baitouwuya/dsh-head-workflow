# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,pathlib,json,math,numpy as np
def build(profile,cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);scene=bpy.data.scenes[cfg['scene']];source=bpy.data.objects['INTERNAL_ONLY__SM_000_protected_facial_skin']
    colors=json.loads((root/'eye-baseline-full-scene-color.json').read_text());report={'classification':'INTERNAL_ONLY','profile':cfg,'objects':[]}
    for eye,color_group in zip(profile['character']['eyes'],colors):
        fit=eye['native_fit'];ry,rz,rx=fit['radius_y'],fit['radius_z'],fit['depth_radius'];gy,gz=eye['sphere_center'][1:];co=np.array(fit['front_base_coefficients'])
        n=cfg['longitudes'];rows=cfg['latitudes'];unit=[[0,0,1]];fs=[];prev=None
        for j in range(1,rows):
            th=np.pi*j/rows;curr=[]
            for i in range(n):
                ph=2*np.pi*i/n;curr.append(len(unit));unit.append([np.sin(th)*np.cos(ph),np.sin(th)*np.sin(ph),np.cos(th)])
            if prev is None:
                for i in range(n):fs.append([0,curr[i],curr[(i+1)%n]])
            else:
                for i in range(n):
                    k=(i+1)%n;fs.extend([[prev[i],curr[i],curr[k]],[prev[i],curr[k],prev[k]]])
            prev=curr
        pole=len(unit);unit.append([0,0,-1])
        for i in range(n):fs.append([prev[i],pole,prev[(i+1)%n]])
        unit=np.array(unit);u=unit[:,1];v=unit[:,2];base=co[0]+co[1]*u+co[2]*v+co[3]*u*u+co[4]*u*v+co[5]*v*v
        xyz=np.column_stack((base+rx*unit[:,0]-cfg['iris_clearance_m'],gy+ry*u,gz+rz*v)).astype(np.float32)
        name='INTERNAL_ONLY_'+eye['label']+'_closed_scleral_globe_'+cfg['revision'];mesh=bpy.data.meshes.new(name);mesh.from_pydata(xyz.tolist(),[],fs);mesh.update();ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob)
        for mat in source.data.materials:mesh.materials.append(mat)
        choices=[r for r in color_group['rays'] if 'source_uv' in r and min(r['baseline_rgb_linear'])>.8 and max(r['baseline_rgb_linear'])-min(r['baseline_rgb_linear'])<.15]
        chosen=min(choices,key=lambda r:np.linalg.norm(np.array(r['baseline_rgb_linear'])-[.94,.92,.96]));uv=mesh.uv_layers.new(name='UVMap')
        for loop in uv.data:loop.uv=chosen['source_uv']
        for f in mesh.polygons:f.use_smooth=True
        ob['classification']='INTERNAL_ONLY';ob['role']='scleral_globe';ob['eye']=eye['label'];ob['source_texture_preserved']=True
        a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](xyz,fs,fs,np.arange(len(fs)))
        report['objects'].append({'object':name,'white_sample':chosen,'audit':{k:a[k] for k in ['boundary_edges','nonmanifold_edges','same_direction_edges','degenerate_triangles','adjacent_normal_degrees']}})
    (root/(cfg['revision']+'-scleral-globes.json')).write_text(json.dumps(report,indent=2));return report
