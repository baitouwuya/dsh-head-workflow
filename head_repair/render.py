# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,numpy as np
from mathutils import Vector
from .controls import apply

def render(profile,manifest,out):
    cfg=profile['render'];out.mkdir(exist_ok=True);s=bpy.context.scene
    try:s.render.engine='BLENDER_EEVEE'
    except TypeError:s.render.engine='BLENDER_EEVEE_NEXT'
    s.eevee.taa_render_samples=cfg['samples'];s.render.resolution_x=s.render.resolution_y=cfg['resolution'];s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='Standard'
    s.world=bpy.data.worlds.new('Review World');s.world.use_nodes=True;bg=s.world.node_tree.nodes.get('Background');bg.inputs[0].default_value=(.25,.25,.25,1);bg.inputs[1].default_value=.8
    target=Vector(cfg['target']);bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=cfg['ortho_scale'];s.camera=cam
    for label,loc,power in [('key',(.5,-.3,1.3),5),('fill',(.25,.4,1.0),2)]:
        data=bpy.data.lights.new(label,'AREA');o=bpy.data.objects.new(label,data);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();data.energy=power;data.size=1
    for name,values in cfg['poses']:
        apply(manifest,values)
        for label,loc in cfg['views'].items():
            cam.location=loc;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=str(out/(name+'_'+label+'.png'));bpy.ops.render.render(write_still=True)
    apply(manifest,{})
