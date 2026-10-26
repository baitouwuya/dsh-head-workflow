# SPDX-License-Identifier: GPL-3.0-or-later
import bpy,json,math
import numpy as np
from mathutils import Vector,Quaternion

def build(src, body_color, cfg):
    scene=bpy.context.scene
    body=next(o for o in scene.objects if o.type=='MESH' and 'BodyFace' in o.name)
    rig=next(o for o in scene.objects if o.type=='ARMATURE');jaw=rig.pose.bones['dsh_Jaw'];jaw.rotation_mode='QUATERNION'
    axis=rig.data.bones[jaw.name].matrix_local.to_3x3().inverted()@Vector((0,1,0));axis.normalize()
    c=json.loads((src/'evidence/head/construction.json').read_text());m=c['regions']['mouth']
    manifest=json.loads((src/'control_manifest.json').read_text());keys=body.data.shape_keys.key_blocks
    outer=m['outer_source_loop'];lip=m['new_lip_vertices'];rim=m['rim_indices'];inside=m['interior_indices']
    N=len(outer);R=len(lip)//N;C=(len(inside)-1)//N
    outer_set=set(outer);mouth_set=set(lip+inside);neighbors=set(outer);frontier=set(outer);levels={}
    for level in [1,2]:
        found=set()
        for edge in body.data.edges:
            a,b=edge.vertices
            if a in frontier and b not in mouth_set and b not in neighbors:found.add(b)
            if b in frontier and a not in mouth_set and a not in neighbors:found.add(a)
        for i in found:levels[i]=level
        neighbors|=found;frontier=found
    affected=sorted(set(lip+inside)|neighbors);basis=np.array([v.co[:] for v in keys['Basis'].data]);cy,cz=m['local_center']
    report={'method':'Radial noncrossing planar rings, smooth depth fit, per-angle inverse-skin corrective fields','rows':[]}

    def reset():
        for o in scene.objects:
            if o.type=='MESH' and o.data.shape_keys:
                for k in o.data.shape_keys.key_blocks:k.value=0
        for bone in rig.pose.bones:bone.rotation_mode='QUATERNION';bone.rotation_quaternion=(1,0,0,0)

    def eval_positions():
        ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();p=np.array([v.co[:] for v in me.vertices]);ev.to_mesh_clear();return p

    def skin_transforms():
        offset=np.array(body.matrix_world.inverted()@rig.matrix_world);pre=np.array(rig.matrix_world.inverted()@body.matrix_world)
        ts={g.index:np.array(rig.pose.bones[g.name].matrix@rig.data.bones[g.name].matrix_local.inverted()) for g in body.vertex_groups if g.name in rig.pose.bones}
        return {i:offset@sum(ts[g.group]*g.weight for g in body.data.vertices[i].groups if g.group in ts)@pre for i in affected}

    def design(yz,center,scale):
        uv=(yz-center)/scale;u=uv[:,0];v=uv[:,1];return np.column_stack((u*0+1,u,v,u*u,u*v,v*v))

    def visible_center(points,desired):
        lo=points.min(0)-.01;hi=points.max(0)+.01
        kernel=[np.array([lo[0],lo[1]]),np.array([hi[0],lo[1]]),np.array([hi[0],hi[1]]),np.array([lo[0],hi[1]])]
        cross=lambda a,b:a[0]*b[1]-a[1]*b[0]
        for a,b in zip(points,np.roll(points,-1,axis=0)):
            edge=b-a;clipped=[]
            for start,end in zip(kernel,kernel[1:]+kernel[:1]):
                ds=cross(edge,start-a);de=cross(edge,end-a)
                if ds>=-1e-12:clipped.append(start)
                if (ds>=0)!=(de>=0):clipped.append(start+(end-start)*(ds/(ds-de)))
            kernel=clipped
            if not kernel:raise RuntimeError('Posed skin boundary has an empty visibility kernel')
        if all(cross(b-a,desired-a)>=1e-12 for a,b in zip(points,np.roll(points,-1,axis=0))):return desired,kernel
        best=None;distance=1e9
        for a,b in zip(kernel,kernel[1:]+kernel[:1]):
            e=b-a;t=float(np.clip(np.dot(desired-a,e)/max(np.dot(e,e),1e-30),0,1));q=a+t*e;d=np.linalg.norm(q-desired)
            if d<distance:best=q;distance=d
        return best*.999+np.mean(kernel,axis=0)*.001,kernel

    targets={};rest_targets={}
    for degree in cfg['poses']:
        reset();keys['jawSpread15'].value=degree/cfg['poses'][-1];jaw.rotation_quaternion=Quaternion(axis,math.radians(degree));bpy.context.view_layer.update()
        raw=eval_positions();target=raw.copy();op=raw[outer];rp=raw[rim]
        center=np.array([cy,(rp[:,2].max()+rp[:,2].min())/2])
        radii=np.array([(rp[:,1].max()-rp[:,1].min())/2,max(cfg['minimum_pose_half_height'],(rp[:,2].max()-rp[:,2].min())/2)])
        if degree==0:center[1]=cz;radii[1]=cfg['neutral_half_height']
        requested_center=center.copy();original_outer=op.copy();smoothing_steps=0
        while True:
            try: center,kernel=visible_center(op[:,1:3],requested_center);break
            except RuntimeError:
                smoothing_steps+=1
                if smoothing_steps>cfg['relax_steps']:raise RuntimeError('Outer local relaxation failed at '+str(degree))
                op[:,1:3]+=cfg['relax_rate']*((np.roll(op[:,1:3],1,axis=0)+np.roll(op[:,1:3],-1,axis=0))/2-op[:,1:3])
        outer_delta=op-original_outer;target[outer]=op
        for i,level in levels.items():
            distances=np.linalg.norm(basis[outer]-basis[i],axis=1);ids=np.argsort(distances)[:3];w=1/np.maximum(distances[ids],1e-5)**2;w/=w.sum()
            target[i]+=np.sum(outer_delta[ids]*w[:,None],axis=0)*(3-level)/3
        print('POSE_BOUNDARY',degree,smoothing_steps,float(np.linalg.norm(outer_delta,axis=1).max()),flush=True)
        direction=op[:,1:3]-center;distance=np.linalg.norm(direction,axis=1);unit=direction/distance[:,None]
        theta=np.unwrap(np.arctan2(unit[:,1],unit[:,0]));steps=np.diff(np.r_[theta,theta[0]+2*math.pi])
        if np.any(steps<=0):raise RuntimeError('Posed outer loop is not star-shaped at degree '+str(degree))
        entrance_distance=1/np.sqrt(np.sum((unit/radii)**2,axis=1))
        entrance_distance=np.minimum(entrance_distance,distance*cfg['entrance_fraction'])
        scale=np.maximum(np.ptp(op[:,1:3],axis=0)/2,.001)
        coefficients=np.linalg.lstsq(design(op[:,1:3],center,scale),op[:,0],rcond=None)[0]
        inner_yz=center+unit*entrance_distance[:,None]
        inner_x=design(inner_yz,center,scale)@coefficients
        gradients=[]
        for oi in outer:
            normal=np.zeros(3)
            for f in body.data.polygons:
                ids=list(f.vertices)
                if oi in ids and not any(i in mouth_set for i in ids):
                    q=raw[ids]
                    for k in range(1,len(ids)-1):normal+=np.cross(q[k]-q[0],q[k+1]-q[0])
            if abs(normal[0])>1e-12:gradients.append(np.clip(-normal[1:]/normal[0],-1.5,1.5))
            else:gradients.append(np.zeros(2))
        gradients=np.array(gradients)
        gradients=(np.roll(gradients,1,axis=0)+2*gradients+np.roll(gradients,-1,axis=0))/4
        d0=np.sum(gradients*(inner_yz-op[:,1:3]),axis=1)
        uv=(inner_yz-center)/scale
        inner_gradient=np.column_stack(((coefficients[1]+2*coefficients[3]*uv[:,0]+coefficients[4]*uv[:,1])/scale[0],(coefficients[2]+coefficients[4]*uv[:,0]+2*coefficients[5]*uv[:,1])/scale[1]))
        d1=np.sum(inner_gradient*(inner_yz-op[:,1:3]),axis=1)
        for row in range(R):
            t=(row+1)/R;rad=distance*(1-t)+entrance_distance*t;yz=center+unit*rad[:,None]
            x=(2*t**3-3*t*t+1)*op[:,0]+(t**3-2*t*t+t)*d0+(-2*t**3+3*t*t)*inner_x+(t**3-t*t)*d1
            target[lip[row*N:(row+1)*N]]=np.column_stack((x,yz))
        rp=target[rim];phase=np.arctan2((rp[:,2]-center[1])/radii[1],(rp[:,1]-center[0])/radii[0])
        for row in range(C):
            t=(row+1)/C;q=rp.copy();q[:,0]-=cfg['depth']*t
            q[:,1]=center[0]+(rp[:,1]-center[0])*(1+cfg['cavity_width_bulge']*math.sin(math.pi*t)-cfg['cavity_width_taper']*t)
            q[:,2]=center[1]+(rp[:,2]-center[1])*(1+cfg['cavity_height_bulge']*math.sin(math.pi*t))+cfg['cavity_height']*np.sin(phase)*math.sin(math.pi*t/2)
            target[inside[row*N:(row+1)*N]]=q
        target[inside[-1]]=target[inside[-N-1:-1]].mean(0)
        transforms=skin_transforms();rest=target.copy()
        for i in affected:rest[i]=(np.linalg.inv(transforms[i])@np.r_[target[i],1])[:3]
        targets[degree]=target;rest_targets[degree]=rest
        report['rows'].append({'degree':degree,'center':center.tolist(),'requestedCenter':requested_center.tolist(),'kernel':np.array(kernel).tolist(),'entranceRadii':radii.tolist(),'outerSmoothingSteps':smoothing_steps,'outerMaximumShift':float(np.linalg.norm(outer_delta,axis=1).max()),'minimumAngularStep':float(steps.min()),'maximumChange':float(np.linalg.norm(target[affected]-raw[affected],axis=1).max())})

    reset();delta=rest_targets[0]-basis
    for key in keys:
        arr=np.array([v.co[:] for v in key.data]);arr[affected]+=delta[affected];key.data.foreach_set('co',arr.astype(np.float32).ravel());key.value=0
    newbasis=np.array([v.co[:] for v in keys['Basis'].data]);body.data.vertices.foreach_set('co',newbasis.astype(np.float32).ravel())
    manifest['automatic_correctives']={}
    degrees=cfg['poses']
    for j,degree in enumerate(degrees[1:],1):
        name='dshLipPose'+str(degree);arr=newbasis.copy();arr[affected]=rest_targets[degree][affected]
        key=body.shape_key_add(name=name);key.data.foreach_set('co',arr.astype(np.float32).ravel());key.value=0
        manifest['automatic_correctives'][name]={'points':[[d,1 if d==degree else 0] for d in degrees],'method':'piecewise_linear_angle'}
    manifest['status']='EXPERIMENTAL_PENDING_VISUAL_ACCEPTANCE';manifest['jaw']['supported_maximum_degrees']=None
    manifest['limits']='Candidate awaiting profile audit and rendered review.'
    normals=[tuple(n.vector) for n in body.data.corner_normals]
    for face in body.data.polygons:
        if 'SEM_new_lip' in body.data.materials[face.material_index].name:
            for li in face.loop_indices:
                normals[li]=(0,0,0)
                vi=body.data.loops[li].vertex_index
                if vi in lip:
                    idx=lip.index(vi);row=idx//N;j=idx%N;t=(row+1)/R;po=basis[outer[j]]
                    theta=math.atan2((po[2]-cz)/m['local_radii'][1],(po[1]-cy)/m['local_radii'][0]);sn=math.sin(theta)
                    trace=np.array(json.loads((src/'refinement_source/source_lip_trace.json').read_text())['samples_y_lower_upper'])
                    yr=(trace[-1,0]-trace[0,0])/2;yi=cy+yr*math.cos(theta)
                    zi=float(np.interp(yi,trace[:,0],trace[:,2] if sn>=0 else trace[:,1]))+(1 if sn>=0 else -1)*cfg['lip_trace_offset']
                    y=po[1]*(1-t)+yi*t;z=po[2]*(1-t)+zi*t
                    body.data.uv_layers.active.data[li].uv=(.5-(y-cy)/cfg['uv_scale'],.5+(z-cz)/cfg['uv_scale'])
                else:
                    p=newbasis[vi];body.data.uv_layers.active.data[li].uv=(.5-(p[1]-cy)/cfg['uv_scale'],.5+(p[2]-cz)/cfg['uv_scale'])
    body.data.normals_split_custom_set(normals);body.data.update()
    if body_color:
        image=bpy.data.images.load(body_color,check_existing=False);image.name='dsh-perioral-body-source';image.pack()
        for material in body.data.materials:
            if material and material.name.startswith('SEM_new_lip'):
                bs=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED');socket=bs.inputs['Base Color']
                if not socket.is_linked or socket.links[0].from_node.type!='TEX_IMAGE':raise RuntimeError('Unexpected lip color shader')
                socket.links[0].from_node.image=image
        report['colorSource']=body_color

    reset();bpy.context.view_layer.update()
    return manifest,c,report
