# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Internal-only structural stage; controlled by assembly-profile.json."""
import bpy,bmesh,json,pathlib,math
import numpy as np
from mathutils import Vector,Matrix

def build():
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root'])
    cfg=json.loads((root/'assembly-profile.json').read_text())
    opts=cfg['oral']; gates=cfg['audit']
    scene=bpy.data.scenes['INTERNAL_ONLY__SM_Assembly']
    saved=bpy.context.window.scene
    report={'classification':'INTERNAL_ONLY','profile':cfg,'components':[]}
    col=bpy.data.collections.new('INTERNAL_ONLY__ORAL_'+cfg['revision'])
    scene.collection.children.link(col)
    try:
        bpy.context.window.scene=scene
        for role in ['lower_teeth','upper_teeth','oral_lining_candidate','tongue_candidate']:
            src=bpy.data.objects['INTERNAL_ONLY__'+role]
            verts=[tuple(src.matrix_world@v.co) for v in src.data.vertices]
            faces=[tuple(p.vertices) for p in src.data.polygons]
            mesh=bpy.data.meshes.new('INTERNAL_ONLY_'+role+'_closed')
            mesh.from_pydata(verts,[],faces);mesh.update()
            bm=bmesh.new();bm.from_mesh(mesh)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=opts['merge_distance_m'])
            boundary=[e for e in bm.edges if e.is_boundary]
            cap=bmesh.ops.holes_fill(bm,edges=boundary,sides=0) if role!='oral_lining_candidate' else {'faces':[]}
            bmesh.ops.triangulate(bm,faces=list(bm.faces))
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
            bm.to_mesh(mesh);bm.free()
            ob=bpy.data.objects.new('INTERNAL_ONLY__closed_'+role,mesh);col.objects.link(ob)
            ob['classification']='INTERNAL_ONLY';ob['structural_role']=role
            ob['derived_from']=src.name;ob['export_status']='UNACCEPTED'
            for mat in src.data.materials:mesh.materials.append(mat)
            bpy.context.view_layer.objects.active=ob
            bpy.ops.object.select_all(action='DESELECT');ob.select_set(True)
            if role=='oral_lining_candidate':
                solid=ob.modifiers.new('Cavity return wall','SOLIDIFY');solid.thickness=opts['cavity_wall_m'];solid.offset=0.0;solid.use_even_offset=True
                bpy.ops.object.modifier_apply(modifier=solid.name)
            mod=ob.modifiers.new('Interior refinement','SUBSURF')
            mod.subdivision_type='CATMULL_CLARK';mod.levels=opts['levels_by_role'].get(role,opts['subdivision_levels']);mod.render_levels=mod.levels
            bpy.ops.object.modifier_apply(modifier=mod.name)
            mesh=ob.data
            bm=bmesh.new();bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm,faces=list(bm.faces))
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
            bm.to_mesh(mesh);bm.free()
            if role in opts.get('fold_relax_roles',[]):
                relax_ns={};exec((root/'scripts'/'fold_relax.py').read_text(),relax_ns)
                pv=np.array([list(v.co) for v in mesh.vertices]);pt=np.array([list(f.vertices) for f in mesh.polygons])
                revised,relax_report=relax_ns['relax_folds'](pv,pt,opts['fold_relax'])
                for v,co in zip(mesh.vertices,revised):v.co=co
                mesh.update()
                (root/(cfg['revision']+'-'+role+'-relax.json')).write_text(json.dumps(relax_report,indent=2))
            for f in mesh.polygons:f.use_smooth=True
            ob.shape_key_add(name='Basis')
            key=ob.shape_key_add(name='jawOpen');key.value=0
            pivot=Vector(opts['jaw_pivot']);rot=Matrix.Rotation(math.radians(opts['jaw_degrees']),3,'Y')
            for i,v in enumerate(mesh.vertices):
                if role=='upper_teeth':w=0.0
                elif role in ('lower_teeth','tongue_candidate'):w=1.0
                else:
                    w=max(0,min(1,(cfg['oral']['jaw_pivot'][2]-v.co.z)/opts['oral_transition_m']))
                    w=w*w*(3-2*w)
                key.data[i].co=v.co+(rot@(v.co-pivot)+pivot-v.co)*w
            rows=[]
            f=[list(p.vertices) for p in mesh.polygons];t=np.array(f,int);base=np.array([list(v.co) for v in mesh.vertices]);target=np.array([list(v.co) for v in key.data])
            for a in gates['pose_samples']:
                v=base+(target-base)*a
                x=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](v,f,t,list(range(len(f))),reference_local_vertices=base,local_vertices=v)
                rows.append({'jaw':a,'boundary':x['boundary_edges'],'nonmanifold':x['nonmanifold_edges'],'winding':x['same_direction_edges'],'degenerate':x['degenerate_triangles'],'adjacent':x['adjacent_normal_degrees'],'quad':x['quad_discrepancy_degrees'],'reversals':x['reference_normal_reversals'],'volumes':[s['signed_volume_m3'] for s in x['shells']]})
            report['components'].append({'object':ob.name,'source':src.name,'closed_root_faces_added':len(cap['faces']),'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'poses':rows})
        report['status']='STRUCTURAL_STAGE_ONLY_EYES_MOUTH_RAY_GATES_PENDING'
        (root/(cfg['revision']+'-oral-stage.json')).write_text(json.dumps(report,indent=2))
    finally:
        bpy.context.window.scene=saved
    return report
