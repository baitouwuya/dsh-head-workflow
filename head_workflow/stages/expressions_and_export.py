# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,math,json,numpy as np
    from mathutils import Vector
    
    h.set_jaw(0);h.set_blink(0,0)
    cy=sum(h.lip['y_range'])/2;cz=float(np.polyval(h.lip['fit_z_of_y_coefficients'],cy))
    for obj in [h.body,h.hair,h.oral]:
        base=np.empty((len(obj.data.vertices),3),np.float32);obj.data.shape_keys.key_blocks['Basis'].data.foreach_get('co',base.ravel())
        for name,kind in [('mouthWide','wide'),('mouthNarrow','narrow'),('mouthFrown','frown')]:
            coords=base.copy()
            for i,p in enumerate(base):
                if obj==h.hair and h.work_hair_components[i] not in h.mouth_hair_components:continue
                x,y,z=p
                if x<.002 or abs(y-cy)>.016 or abs(z-cz)>.018:continue
                w=math.exp(-((y-cy)/.010)**4-((z-cz)/.010)**4)
                if kind=='wide':coords[i,1]+=(y-cy)*.65*w
                elif kind=='narrow':coords[i,1]-=(y-cy)*.30*w
                else:coords[i,2]-=.0014*(1-math.exp(-((y-cy)/.0018)**2))*w
            key=obj.shape_key_add(name=name,from_mix=False);key.data.foreach_set('co',coords.ravel());key.value=0
    h.recipes={
     'neutral':{},
     'aa':{'jawOpen':.85,'mouthWide':.55},
     'ih':{'jawOpen':.18,'mouthWide':.75,'smileLeft':.45,'smileRight':.45},
     'ou':{'jawOpen':.45,'mouthNarrow':.75,'mouthPucker':.75},
     'ee':{'jawOpen':.40,'mouthWide':.85,'smileLeft':.35,'smileRight':.35},
     'oh':{'jawOpen':.85,'mouthNarrow':.35,'mouthPucker':.25},
     'happy':{'jawOpen':.3,'mouthWide':.55,'smileLeft':.85,'smileRight':.85,'browRaiseLeft':.2,'browRaiseRight':.2,'blinkLeft':.3,'blinkRight':.3},
     'angry':{'browFrownLeft':.9,'browFrownRight':.9,'mouthPucker':.25,'mouthFrown':.25},
     'sad':{'browRaiseLeft':.35,'browRaiseRight':.35,'mouthFrown':.8},
     'relaxed':{'smileLeft':.3,'smileRight':.3,'blinkLeft':.2,'blinkRight':.2},
     'surprised':{'browRaiseLeft':1,'browRaiseRight':1,'jawOpen':.9,'mouthNarrow':.15},
    }
    h.recipes=h.config.get('recipes',h.recipes)
    
    def controls(values):
        for obj in [h.body,h.hair,h.oral]:
            for key in obj.data.shape_keys.key_blocks:key.value=0
            for name,value in values.items():
                key=obj.data.shape_keys.key_blocks.get(name)
                if key:key.value=max(0,min(1,value))
        h.set_blink(values.get('blinkLeft',values.get('blink',0)),values.get('blinkRight',values.get('blink',0)));h.set_jaw(values.get('jawOpen',0))
    h.controls=controls
    for name in ['aa','oh','happy','angry','sad','relaxed','surprised']:
        controls(h.recipes[name]);h.render('expression-'+name,views={'front':h.views['front']})
    controls({})
    # Actual engine export: select only the candidate rig, model meshes and new mouth/eye parts.
    h.model_objects=[h.rig,h.body,h.hair]+h.eyeballs+h.mouth_parts+h.socket_rims+[o for o in h.scene.objects if o.type=='MESH' and any(token in o.name for token in h.config['garment_name_tokens'])]
    h.out.mkdir(exist_ok=False)
    for obj in h.scene.objects:obj.select_set(False)
    for obj in h.model_objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=h.rig
    print('EXPORT_INTEGRATED',bpy.ops.export_scene.gltf(filepath=str(h.out/'character-head-integrated.glb'),export_format='GLB',use_selection=True,use_active_scene=True,export_morph=True,export_skins=True,export_animations=False,export_apply=False))
    (h.out/'control_manifest.json').write_text(json.dumps({'jaw':{'bone':'dsh_Jaw','maximum_degrees':h.jaw_range,'axis_blender_rig':[0,1,0],'axis_gltf_model':[0,0,-1],'method':'Apply a local-axis quaternion on top of the exported rest local quaternion; convert model-space axis into bone rest local space.'},'eye_bones':{e['label']:e['bone_name'] for e in h.eyes},'blink':{'left':['blinkLeft_25','blinkLeft_50','blinkLeft_75','blinkLeft_100'],'right':['blinkRight_25','blinkRight_50','blinkRight_75','blinkRight_100'],'method':'Adjacent sample interpolation, never sum all samples'},'original_controls':h.old_controls,'added_morphs':['mouthWide','mouthNarrow','mouthFrown'],'recipes':h.recipes,'limits':'Declared control range 0..1; 8-degree jaw. Arbitrary simultaneous maximum mixtures are not certified.'},indent=2))
    (h.root/'checkpoint-state.json').write_text(json.dumps({'phase':'integrated export ready for browser test','out':str(h.out),'original_scene':h.original_scene.name,'working_scene':h.scene.name,'rig':h.rig.name},indent=2))
    bpy.data.libraries.write(str(h.out/'character-head-integrated.blend'),{h.scene},fake_user=True,compress=True)
    print('OUT',str(h.out))

