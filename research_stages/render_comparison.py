# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,pathlib,json,contextlib,io
from mathutils import Vector
def render(scene_name,label,jaw=0,blink=0,azimuth_degrees=0):
 r=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);saved=bpy.context.window.scene;s=bpy.data.scenes[scene_name]
 try:
  bpy.context.window.scene=s
  for o in s.objects:
   if o.type=='ARMATURE':
    for b in o.pose.bones:
     if b.custom_shape:b.custom_shape.hide_render=True
   if o.type=='MESH' and o.data.shape_keys:
    for k in o.data.shape_keys.key_blocks:
     if k.name!='Basis':k.value=0
  if 'patch006' in scene_name:
   ns={};exec((r/'scripts/contract_probes.py').read_text(),ns);ns['apply']([o for o in s.objects if o.type=='MESH'],jaw,blink,blink)
  cam=s.camera
  if cam is None:
   c=bpy.data.cameras.new('INTERNAL_ONLY_camera_'+scene_name);cam=bpy.data.objects.new(c.name,c);s.collection.objects.link(cam);s.camera=cam
  import math
  angle=math.radians(azimuth_degrees);cam.location=(.5*math.cos(angle),.5*math.sin(angle),.915);cam.rotation_euler=(Vector((0,0,.915))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.195
  if not any(o.type=='LIGHT' for o in s.objects):
   for suffix,pos,power,size in [('key',(.25,-.18,1.12),35,.3),('fill',(.2,.2,.98),15,.3)]:
    l=bpy.data.lights.new('INTERNAL_ONLY_'+scene_name+suffix,'AREA');l.energy=power;l.shape='DISK';l.size=size;o=bpy.data.objects.new(l.name,l);s.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector((0,0,.91))-o.location).to_track_quat('-Z','Y').to_euler()
  if not s.world:
   w=bpy.data.worlds.new('INTERNAL_ONLY_world_'+scene_name);w.use_nodes=True;bg=w.node_tree.nodes.new('ShaderNodeBackground');bg.inputs[0].default_value=(.12,.12,.12,1);bg.inputs[1].default_value=.5;out=w.node_tree.nodes.new('ShaderNodeOutputWorld');w.node_tree.links.new(bg.outputs[0],out.inputs[0]);s.world=w
  s.render.engine='CYCLES';s.cycles.samples=24;s.render.resolution_x=700;s.render.resolution_y=700;s.render.resolution_percentage=100;s.view_settings.view_transform='Standard';s.render.image_settings.file_format='PNG';s.render.filepath=str(r/(label+'.png'));s.render.film_transparent=False
  log=io.StringIO()
  with contextlib.redirect_stdout(log):bpy.ops.render.render(write_still=True)
  (r/(label+'-render.log')).write_text(log.getvalue());return str(r/(label+'.png'))
 finally:bpy.context.window.scene=saved
