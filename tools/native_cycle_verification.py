# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Native Lab only: reimport its sealed GLB and render its serialized blink clips.

No factory reset, source reconstruction, export or publication. The actual GLB
channel data drives imported morph targets, avoiding Blender Action API version
coupling. Imported Action presence is recorded separately and never substituted
for proof of the serialized channel weights used in rendered frames.
"""
from pathlib import Path
import hashlib,json,math
from native_glb_clips import read_weight_clip,sample_weight_track,unpack_glb


def _hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cycle_sample_schedule(tracks,requested_fps=None,clip_fps=None):
    """Double the real key rate, preserving a fixed final-neutral frame hold.

    A source sequence of N frames at F fps lasts N/F seconds: its last key is at
    (N-1)/F and is displayed for 1/F. At 2F, render 2N actual frames, including
    between-key samples and two frames of the same final-neutral hold. This keeps
    the timebase/duration rather than speeding the clip or stretching key times.
    """
    if not tracks:raise ValueError('Serialized tracks required')
    for value in (requested_fps,clip_fps):
        if value is not None and (isinstance(value,bool) or not isinstance(value,int) or value<=0):raise ValueError('Positive integer frame rates required')
    axes=[track['times'] for track in tracks]
    if any(len(axis)<2 or any(not math.isfinite(t) for t in axis) or any(b<=a for a,b in zip(axis,axis[1:])) for axis in axes):raise ValueError('Strictly increasing serialized track times required')
    start=min(a[0] for a in axes);end=max(a[-1] for a in axes);delta=min(b-a for axis in axes for a,b in zip(axis,axis[1:]));rate=1/delta
    # Float32 accessors introduce tiny reciprocal-rate error (e.g. 24.00002).
    nearest=round(rate);key_rate=nearest if abs(rate-nearest)<=max(1e-4,rate*1e-5) else math.ceil(rate)
    source_rate=clip_fps or key_rate;render_rate=max(requested_fps or 0,2*source_rate,2*key_rate)
    hold=1/source_rate;duration=end-start+hold;exact_count=duration*render_rate
    count=max(3,int(round(exact_count)) if abs(exact_count-round(exact_count))<1e-4 else int(math.ceil(exact_count)))
    clock=[start+i/render_rate for i in range(count)];samples=[min(t,end) for t in clock]
    key_times=axes[0];between=sum(start<t<end and not any(abs(t-k)<1e-6 for k in key_times) for t in samples)
    if between==0:raise ValueError('Native verification must include between-serialized-key samples')
    return {'fps':render_rate,'clip_fps':source_rate,'serialized_start_seconds':start,'serialized_end_seconds':end,'frame_clock_seconds':clock,'sample_times_seconds':samples,'frames':count,'samples_between_serialized_keys':between,'final_neutral_hold_seconds':hold,'video_duration_seconds':count/render_rate,'source_sequence_duration_seconds':duration}


def _encode(bpy,paths,target,fps,resolution,view_transform):
    if target.exists():raise FileExistsError('Preserve native video: '+str(target))
    scene=bpy.data.scenes.new('native-verified-cycle-encoding');editor=scene.sequence_editor_create();strips=getattr(editor,'strips',None)
    if strips is None:strips=editor.sequences
    strip=strips.new_image(name='Native sealed artifact frames',filepath=str(paths[0]),channel=1,frame_start=1)
    for p in paths[1:]:strip.elements.append(p.name)
    strip.frame_final_duration=len(paths);scene.frame_start=1;scene.frame_end=len(paths);scene.render.resolution_x=resolution;scene.render.resolution_y=resolution;scene.render.resolution_percentage=100;scene.render.fps=fps;scene.view_settings.view_transform=view_transform
    if hasattr(scene.render.image_settings,'media_type'):scene.render.image_settings.media_type='VIDEO'
    scene.render.image_settings.file_format='FFMPEG';scene.render.ffmpeg.format='MPEG4';scene.render.ffmpeg.codec='H264';scene.render.ffmpeg.constant_rate_factor='MEDIUM';scene.render.filepath=str(target)
    bpy.ops.render.render(animation=True,scene=scene.name)
    return {'path':str(target),'sha256':_hash(target),'frames':len(paths),'fps':fps,'view_transform':view_transform,'source':'Actual rendered native reimport PNG frames'}


def verify_native_cycles(request_path):
    """Request uses runtime source/candidate paths, views/lights and clip IDs.

    A native_build_provenance object is mandatory. The host_precheck mode is
    rejected before bpy import. Source zero-pose renders share candidate cameras,
    renderer, lights and color transform. Existing scenes/files are retained.
    """
    r=json.loads(Path(request_path).read_text())
    if r.get('mode')!='native_stage_build':raise ValueError('Only the native Lab own sealed build may be verified here')
    if not r.get('native_build_provenance'):raise ValueError('Native build provenance required')
    source_path=Path(r['source']['path']);candidate_path=Path(r['candidate']['path']);out=Path(r['output_directory']);out.mkdir(parents=True,exist_ok=True)
    report_path=out/'native-cycle-verification.json'
    if report_path.exists():raise FileExistsError('Preserve previous verification evidence')
    before={'source':_hash(source_path),'candidate':_hash(candidate_path)};sealed=candidate_path.read_bytes();doc,_,_=unpack_glb(sealed)
    tracks_by_clip={clip:read_weight_clip(sealed,clip) for clip in r['clip_names']}
    fps=r.get('fps',24)
    if isinstance(fps,bool) or not isinstance(fps,int) or fps<=0:raise ValueError('Positive integer video fps required')
    for tracks in tracks_by_clip.values():
        if any(not track['binding'] for track in tracks):raise ValueError('Sealed nodes lack unambiguous native animation binding extras')
    import bpy
    from mathutils import Matrix,Vector
    import sys
    sys.path.insert(0,str(Path(r['repo_root'])/'tools'))
    import native_render_verification as verifier
    verifier.load_native_runtime()
    report={'status':'RENDERED_PENDING_VISUAL_REVIEW','blender_version':bpy.app.version_string,'version_source':'Native Lab provided runtime','native_build_provenance':r['native_build_provenance'],'file_hashes_before':before,'method':'Reimport sealed GLB; decode actual serialized weight clips; apply decoded samples to UUID-bound imported morph targets. This is not Blender Action playback.','target_names':[{'mesh':i,'target_names':m.get('extras',{}).get('targetNames',[])} for i,m in enumerate(doc.get('meshes',[]))],'sealed_animation_names':[a.get('name') for a in doc.get('animations',[])],'models':[]}
    for role,spec in (('source',r['source']),('candidate',r['candidate'])):
        scene=bpy.data.scenes.new('native-reimport-'+role)
        if bpy.context.window:bpy.context.window.scene=scene
        actions_before=set(bpy.data.actions);path=Path(spec['path'])
        with bpy.context.temp_override(scene=scene,view_layer=scene.view_layers[0]):
            if path.suffix.lower()=='.blend':
                with bpy.data.libraries.load(str(path),link=False) as (available,loaded):loaded.scenes=list(available.scenes)
                seen=set()
                for loaded_scene in loaded.scenes:
                    for obj in loaded_scene.objects:
                        if obj not in seen and obj.type not in ('CAMERA','LIGHT'):scene.collection.objects.link(obj);seen.add(obj)
            elif path.suffix.lower()=='.glb':bpy.ops.import_scene.gltf(filepath=str(path))
            elif path.suffix.lower()=='.fbx':bpy.ops.import_scene.fbx(filepath=str(path))
            else:raise ValueError('Unsupported native source/candidate format')
        imported=list(scene.objects);matrix=Matrix(spec['world_to_review']);new_actions=[a for a in bpy.data.actions if a not in actions_before]
        imported_actions=[{'name':a.name,'frame_range':list(a.frame_range),'users':a.users} for a in new_actions]
        for obj in imported:
            if obj.parent is None:obj.matrix_world=matrix@obj.matrix_world
            # Record imported actions before detaching animation evaluation. The
            # sealed clip data supplies complete morph weights for each frame.
            if obj.animation_data:obj.animation_data_clear()
            if obj.type=='MESH' and obj.data.shape_keys and obj.data.shape_keys.animation_data:obj.data.shape_keys.animation_data_clear()
            if obj.type in ('LIGHT','CAMERA'):obj.hide_render=True
        setup_request=dict(r);setup_request['engine']=r.get('engine',scene.render.engine)
        with bpy.context.temp_override(scene=scene,view_layer=scene.view_layers[0]):scene,camera=verifier.setup(setup_request)
        scene.view_settings.view_transform=r.get('view_transform','Standard');scene.render.fps=fps;scene.render.use_stamp=True;scene.render.use_stamp_note=True
        for prop in ('use_stamp_date','use_stamp_time','use_stamp_render_time','use_stamp_frame','use_stamp_filename','use_stamp_scene','use_stamp_camera','use_stamp_memory'):
            if hasattr(scene.render,prop):setattr(scene.render,prop,False)
        record={'role':role,'path':str(path),'scene':scene.name,'renderer':scene.render.engine,'imported_actions':imported_actions,'renders':[],'videos':[]};report['models'].append(record)
        bindings={}
        for obj in imported:
            if obj.type=='MESH' and obj.get('native_animation_binding'):
                key=obj['native_animation_binding']
                if key in bindings:raise ValueError('Duplicate native imported mesh binding')
                bindings[key]=obj
        def render_one(view,frame_path,note):
            if frame_path.exists():raise FileExistsError('Preserve native frame '+str(frame_path))
            frame_path.parent.mkdir(parents=True,exist_ok=True);camera.location=view['position'];camera.rotation_euler=(Vector(view['target'])-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=float(view['ortho_scale']);scene.render.stamp_note_text=note;scene.render.filepath=str(frame_path)
            bpy.context.view_layer.update();bpy.ops.render.render(write_still=True,scene=scene.name)
            return {'path':str(frame_path),'sha256':_hash(frame_path)}
        if role=='source':
            # The source neutral pose is its declared existing rest state. No
            # unrequested source morph, pose or material control is cleared.
            for view in r['views']:
                vid=view.get('id',view.get('label'));record['renders'].append({'view':vid,'state':'source-neutral',**render_one(view,out/'source-neutral'/(vid+'.png'),'Source neutral | '+vid)})
            continue
        record['serialized_clip_binding_audit']=[]
        for clip,tracks in tracks_by_clip.items():
            assigned=[]
            for track in tracks:
                obj=bindings.get(track['binding'])
                if obj is None or not obj.data.shape_keys:raise ValueError('Sealed animation node not found on native reimport')
                keys=obj.data.shape_keys.key_blocks
                if any(name not in keys for name in track['target_names']):raise ValueError('Sealed target name absent on reimport')
                assigned.append((track,keys));record['serialized_clip_binding_audit'].append({'clip':clip,'node':track['node_name'],'imported_object':obj.name,'binding':track['binding'],'target_names':track['target_names']})
            schedule=cycle_sample_schedule(tracks,requested_fps=fps,clip_fps=r.get('clip_fps'));sample_times=schedule['sample_times_seconds'];render_fps=schedule['fps'];scene.render.fps=render_fps
            record.setdefault('clip_sampling',[]).append({'clip':clip,**schedule})
            for view in r['views']:
                vid=view.get('id',view.get('label'));paths=[]
                for index,t in enumerate(sample_times):
                    for track,keys in assigned:
                        for name,value in zip(track['target_names'],sample_weight_track(track,t)):keys[name].value=value
                    frame_path=out/'candidate'/clip/vid/(str(index).zfill(4)+'.png');paths.append(frame_path);record['renders'].append({'clip':clip,'view':vid,'time_seconds':t,**render_one(view,frame_path,'Sealed native '+clip+' | '+vid+' | '+format(t,'.4f')+'s')})
                record['videos'].append({'clip':clip,'view':vid,**_encode(bpy,paths,out/(clip+'-'+vid+'.mp4'),render_fps,int(r.get('resolution',512)),r.get('view_transform','Standard'))})
    after={'source':_hash(source_path),'candidate':_hash(candidate_path)};report['file_hashes_after']=after;report['files_unchanged']=after==before
    if before!=after:raise AssertionError('Native input or sealed candidate file changed during verification')
    report['acceptance']='Native rendered motion must be reviewed before publishing/selecting the sealed GLB.';report_path.write_text(json.dumps(report,indent=2));return {'report':str(report_path),'status':report['status'],'files_unchanged':True}
