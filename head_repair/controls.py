# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,math,numpy as np
from mathutils import Vector,Quaternion

def apply(manifest,values):
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    for b in rig.pose.bones:b.rotation_mode='QUATERNION';b.rotation_quaternion=(1,0,0,0)
    degree=values.get('degrees',values.get('jawOpen',0)*manifest['jaw']['maximum_degrees'])
    for o in bpy.context.scene.objects:
        if o.type!='MESH' or not o.data.shape_keys:continue
        ks=o.data.shape_keys.key_blocks
        for k in ks:k.value=values.get(k.name,0)
        for name,spec in manifest.get('automatic_correctives',{}).items():
            if name in ks:ks[name].value=float(np.interp(degree,*zip(*spec['points']))) if 'points' in spec else min(1,degree/spec['angle_degrees'])
        for side in ['Left','Right']:
            w=max(values.get('blink',0),values.get('blink'+side,0));q=w*4;i=int(q)
            for step in [25,50,75,100]:
                name='blink'+side+'_'+str(step)
                if name in ks:ks[name].value=0
            for step,v in [(i*25,1-(q-i)),((i+1)*25,q-i)]:
                name='blink'+side+'_'+str(step)
                if name in ks:ks[name].value=v
    jaw=rig.pose.bones[manifest['jaw']['bone']];axis=rig.data.bones[jaw.name].matrix_local.to_3x3().inverted()@Vector(manifest['jaw']['axis_blender_rig']);axis.normalize();jaw.rotation_quaternion=Quaternion(axis,math.radians(degree));bpy.context.view_layer.update()

def positions():
    result={};dg=bpy.context.evaluated_depsgraph_get()
    for o in bpy.context.scene.objects:
        if o.type!='MESH' or o.get('refinement_excluded_reference') or 'Icosphere' in o.name:continue
        ev=o.evaluated_get(dg);m=ev.to_mesh();result[o.name]=np.array([o.matrix_world@v.co for v in m.vertices]);ev.to_mesh_clear()
    return result
