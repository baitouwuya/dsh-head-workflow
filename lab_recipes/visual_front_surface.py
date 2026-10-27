# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Open, fair eye-covering skin grids; the source model is never modified."""
import numpy as np
from .skin_attachment import nearest_triangle_bindings
from .eye_clearance import enforce_eye_clearance
from .surface_routes import SkinTriangleGraph
from .exterior_skin_boundary import exterior_skin_domains
from .aperture_contract import construction_envelope_from_samples
from .fair_disk_patch import fair_disk_patch


def front_depth(points,vertices,triangles):
    q=np.asarray(points,float);t=np.asarray(vertices,float)[np.asarray(triangles,int)];lo=q[:,1:].min(0);hi=q[:,1:].max(0);t=t[(t[:,:,1:].min(1)<=hi).all(1)&(t[:,:,1:].max(1)>=lo).all(1)]
    if not len(t):return np.full(len(q),-np.inf)
    a=t[:,0,1:];u=t[:,1,1:]-a;w=t[:,2,1:]-a;det=u[:,0]*w[:,1]-u[:,1]*w[:,0];valid=abs(det)>1e-16;result=[]
    for start in range(0,len(q),32):
        d=q[start:start+32,None,1:]-a;be=np.divide(d[:,:,0]*w[None,:,1]-d[:,:,1]*w[None,:,0],det[None],out=np.zeros(d.shape[:2]),where=valid[None]);ga=np.divide(u[None,:,0]*d[:,:,1]-u[None,:,1]*d[:,:,0],det[None],out=np.zeros_like(be),where=valid[None]);hit=valid[None]&(be>=-1e-9)&(ga>=-1e-9)&(be+ga<=1+1e-9);x=t[None,:,0,0]+be*(t[None,:,1,0]-t[None,:,0,0])+ga*(t[None,:,2,0]-t[None,:,0,0]);result.extend(np.max(np.where(hit,x,-np.inf),axis=1))
    return np.asarray(result)


def resample_source_boundary(poses,edges,stations):
    p=np.asarray(poses,float);e=np.asarray(edges,int)
    if e.ndim!=2 or e.shape[1]!=2 or not len(e):raise ValueError('Nonempty ordered source-boundary edges required')
    if not np.allclose(p[0,e[:-1,1]],p[0,e[1:,0]],atol=1e-6,rtol=0):raise ValueError('Source boundary is not a continuous ordered path')
    path=p[0,np.r_[e[0,0],e[:,1]]];keep=np.r_[True,np.linalg.norm(np.diff(path,axis=0),axis=1)>1e-10];path=path[keep];arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(path,axis=0),axis=1))]
    if arc[-1]<=0:raise ValueError('Source boundary has zero length')
    arc/=arc[-1];s=np.linspace(0,1,stations);outer=np.stack([np.interp(s,arc,path[:,j]) for j in range(3)],axis=1);return outer,path,arc,s


def _interp_curve(curve,station):
    old=np.linspace(0,1,len(curve));return np.stack([np.interp(station,old,curve[:,j]) for j in range(3)],axis=1)


def _front_strip(poses,faces,path,arc,station,radial_samples):
    p=poses.copy();f=faces.copy();extra=[];added=[];source_edges=[];N=len(station);M=radial_samples
    for j in range(N-1):
        ids=np.flatnonzero((arc>station[j]+1e-12)&(arc<station[j+1]-1e-12));pi=[j*M];qi=[j*M]
        for index in ids:
            t=(arc[index]-station[j])/(station[j+1]-station[j]);pi.append(p.shape[1]+len(extra));extra.append(path[index]);qi.append(p.shape[1]+len(extra));extra.append(p[0,j*M]*(1-t)+p[0,(j+1)*M]*t)
        pi.append((j+1)*M);qi.append((j+1)*M)
        for k in range(len(pi)-1):
            source_edges.append([pi[k],pi[k+1]])
            if ids.size:added.extend([[qi[k],qi[k+1],pi[k+1]],[qi[k],pi[k+1],pi[k]]])
    if extra:p=np.concatenate([p,np.broadcast_to(np.asarray(extra),(len(p),len(extra),3))],axis=1)
    core=len(f)
    if added:
        a=np.asarray(added,int);area=np.linalg.norm(np.cross(p[0,a[:,1]]-p[0,a[:,0]],p[0,a[:,2]]-p[0,a[:,0]]),axis=1);a=a[area>1e-14];f=np.vstack([f,a])
    return p,f,np.r_[np.full(core,2,int),np.ones(len(f)-core,int)],np.asarray(source_edges,int)


def build_visual_front_surfaces(source,lids,probes,roles,configuration,source_scale):
    v=np.asarray(source['vertices'],float)/source_scale;f=np.asarray(source['faces']);comp=np.asarray(source['component']);skin=np.flatnonzero(comp[f[:,0]]==roles['skin_component']);fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);center=v[f].mean(1);cfg=configuration.get('visualSurface',{});N=int(cfg.get('lateralStations',129));M=int(cfg.get('radialSamples',17));smooth_count=int(cfg.get('smoothingIterations',60));closure_fraction=float(cfg.get('lowerClosureFraction',.2));controls=np.asarray(configuration['controls']['blink']['samples'],float);K=len(controls)
    if not 16<=N<=257 or not 4<=M<=33 or not 0<=closure_fraction<=1 or not 0<=smooth_count<=500:raise ValueError('Invalid explicit front-surface fit parameters')
    out={};report={};specs=[]
    for side,eye_components in roles['eye_components'].items():
        eye_faces=f[np.all(np.isin(comp[f],eye_components),axis=1)];points=np.asarray(probes[side+'_visible'])/source_scale;height=float(np.ptp(points[:,2]));body_depth_limit=float(cfg.get('minimumBodyFrontDepth',np.min(v[eye_faces][:,:,0])-cfg.get('bodyDepthBackoffOverHeight',1.25)*height));clear=float(cfg.get('eyeClearanceOverHeight',.01))*height;station=np.linspace(0,1,N);u0=_interp_curve(lids[side+'-upper_poses'][0,lids[side+'-upper_inner_rail_vertices']],station);l0=_interp_curve(lids[side+'-lower_poses'][0,lids[side+'-lower_inner_rail_vertices']],station);seam=(u0+l0)*.5;blend=np.sin(np.pi*station)**2;seam[:,2]=(1-blend)*seam[:,2]+blend*(l0[:,2]+closure_fraction*(u0[:,2]-l0[:,2]));eye_x=front_depth(seam,v,eye_faces);outer_data={}
        for part in ['upper','lower']:
            name=side+'-'+part;outer_data[part]=resample_source_boundary(lids[name+'_poses'],lids[name+'_skin_boundary_edges'],N)
        ends=[.5*(outer_data['upper'][0][j,0]+outer_data['lower'][0][j,0]) for j in [0,-1]];hit=np.flatnonzero(np.isfinite(eye_x));seam[:,0]=np.interp(station,np.r_[0,station[hit],1],np.r_[ends[0],eye_x[hit]+clear,ends[1]]);body_x=front_depth(seam,v,f[skin]);seam[:,0]=np.maximum(seam[:,0],np.where(body_x>body_depth_limit,body_x+clear*.125,-np.inf));side_report={};inner_curves={}
        for part,neutral in [('upper',u0),('lower',l0)]:
            name=side+'-'+part;outer,path,arc,station=outer_data[part];inner=neutral[None]*(1-controls[:,None,None])+seam[None]*controls[:,None,None];floor_inner=front_depth(inner.reshape(-1,3),v,eye_faces).reshape(K,N);inner[:,:,0]=np.maximum(inner[:,:,0],np.where(np.isfinite(floor_inner),floor_inner+clear,-np.inf));inner[0]=neutral;inner[-1]=seam;r=np.linspace(0,1,M);p=outer[None,:,None]*(1-r[None,None,:,None])+inner[:,:,None]*r[None,None,:,None];bindings=nearest_triangle_bindings(outer,v,f[skin]);normal=fn[skin[bindings['triangle_indices']]];length=np.linalg.norm(normal,axis=1);normal=np.divide(normal,length[:,None],out=np.zeros_like(normal),where=length[:,None]>0)
            for iteration in range(6):normal[1:-1]=(normal[:-2]+2*normal[1:-1]+normal[2:])*.25
            dyz=inner[:,:,1:]-outer[None,:,1:];sec=inner[:,:,0]-outer[None,:,0];slope=np.divide(-np.einsum('ni,kni->kn',normal[:,1:],dyz),normal[None,:,0],out=sec.copy(),where=abs(normal[None,:,0])>.05);slope=np.sign(sec)*np.clip(np.sign(sec)*slope,0,3*abs(sec));p[:,:,:,0]=(2*r**3-3*r**2+1)[None,None]*outer[None,:,0,None]+(r**3-2*r**2+r)[None,None]*slope[:,:,None]+(-2*r**3+3*r**2)[None,None]*inner[:,:,0,None];eye_floor=front_depth(p.reshape(-1,3),v,eye_faces).reshape(K,N,M)+clear;body_floor=front_depth(p.reshape(-1,3),v,f[skin]).reshape(K,N,M)+clear*.125;floor=np.maximum(eye_floor,np.where(body_floor>body_depth_limit,body_floor,-np.inf));p[:,:,:,0]=np.maximum(p[:,:,:,0],floor);p[:,:,0]=outer;p[:,:,-1]=inner;p[:,0]=outer[0][None,None]*(1-r[None,:,None])+inner[:,0,None]*r[None,:,None];p[:,-1]=outer[-1][None,None]*(1-r[None,:,None])+inner[:,-1,None]*r[None,:,None]
            for iteration in range(smooth_count):
                x=p[:,:,:,0];avg=(2*(x[:,:-2,1:-1]+x[:,2:,1:-1])+x[:,1:-1,:-2]+x[:,1:-1,2:])/6;x[:,1:-1,1:-1]=np.maximum(floor[:,1:-1,1:-1],.5*x[:,1:-1,1:-1]+.5*avg)
            p=p.reshape(K,N*M,3);faces=[]
            for j in range(N-1):
                for k in range(M-1):a=j*M+k;b=(j+1)*M+k;faces.extend([[a,b,b+1],[a,b+1,a+1]])
            faces=np.asarray(faces,int);normal_sum=np.cross(p[0,faces[:,1]]-p[0,faces[:,0]],p[0,faces[:,2]]-p[0,faces[:,0]]).sum(0)
            if normal_sum[0]<0:faces=faces[:,[0,2,1]]
            p,faces,domains,edges=_front_strip(p,faces,path,arc,station,M);fixed=np.unique(np.r_[np.arange(N)*M,np.arange(N)*M+M-1,np.arange(M),np.arange((N-1)*M,N*M),np.arange(N*M,p.shape[1])]);before=p[:,:,0].copy();unresolved=[];checks=np.linspace(0,1,int(cfg.get('clearanceSamples',17))) if cfg.get('triangleClearance',False) else []
            for weight in checks:
                interval=min(max(int(np.searchsorted(controls,weight,side='right')-1),0),K-2);t=(weight-controls[interval])/(controls[interval+1]-controls[interval]);sample=p[interval]*(1-t)+p[interval+1]*t;projection=enforce_eye_clearance(sample[None],faces,v,eye_faces,fixed,clear,2*height);shift=projection['x_offsets'];p[interval,:,0]+=shift;p[interval+1,:,0]+=shift;unresolved.extend(projection['unresolved_fixed_constraints'])
            shifts=(p[:,:N*M,0]-before[:,:N*M]).reshape(K,N,M)
            for iteration in range(24):
                avg=(2*(shifts[:,:-2,1:-1]+shifts[:,2:,1:-1])+shifts[:,1:-1,:-2]+shifts[:,1:-1,2:])/6;shifts[:,1:-1,1:-1]=np.maximum(shifts[:,1:-1,1:-1],avg)
            p[:,:N*M,0]=before[:,:N*M]+shifts.reshape(K,N*M);base=p[0].astype(np.float32);deltas=(p-p[0]).astype(np.float32);p=(base[None]+deltas).astype(np.float32).astype(float);sample=nearest_triangle_bindings(p[0],v,f[skin]);inner_ids=np.arange(N)*M+M-1;out.update({name+'_poses':p,name+'_faces':faces,name+'_face_domains':domains,name+'_inner_rail_vertices':inner_ids,name+'_skin_boundary_edges':edges,name+'_skin_boundary_vertices':np.unique(edges),name+'_source_sample_triangle_ids':skin[sample['triangle_indices']],name+'_source_sample_barycentric':sample['barycentric']});inner_curves[part]=p[:,inner_ids];specs.append({'id':name,'array_prefix':name,'control':side});side_report[part]={'vertices':p.shape[1],'triangles':len(faces),'outer_route_reparameterized':True,'maximum_outer_step':float(np.linalg.norm(np.diff(outer,axis=0),axis=1).max()),'clearance_sample_count':len(checks),'unresolved_fixed_clearance_constraints':len(unresolved),'maximum_fixed_clearance_shortfall':max([x['shortfall'] for x in unresolved],default=0.),'maximum_added_clearance_shift':float(np.max(p[:,:,0]-before)),'central_closed_depth':float(p[-1,inner_ids[N//4:3*N//4],0].max()),'lower_closure_fraction':closure_fraction}
        rim=np.asarray(construction_envelope_from_samples(points));lo=points[:,1:].min(0);hi=points[:,1:].max(0);candidate=skin[(center[skin,1]>=lo[0]-.75*height)&(center[skin,1]<=hi[0]+.75*height)&(center[skin,2]>=lo[1]-.9*height)&(center[skin,2]<=hi[1]+.9*height)];routing=exterior_skin_domains(v,f,skin,candidate,rim,visibility_tolerance=1e-6)['routing_triangle_ids'];webs=[]
        for end in [0,1]:
            j=0 if end==0 else -1;a=outer_data['upper'][0][j];b=outer_data['lower'][0][j];subset=routing[center[routing,1]<lo[0]+.4*height] if end==0 else routing[center[routing,1]>hi[0]-.4*height];bind=nearest_triangle_bindings([a,b],v,f[subset]);path=SkinTriangleGraph(v,f[subset],source['canonical_vertex_ids']).route(a,b,*map(int,bind['triangle_indices']),padding=height)['positions'];path=path[np.r_[True,np.linalg.norm(np.diff(path,axis=0),axis=1)>1e-9]];boundary=np.concatenate([np.broadcast_to(path,(K,len(path),3)),inner_curves['lower'][:,j,None],inner_curves['upper'][:,j,None]],axis=1);poses=np.concatenate([boundary.mean(1)[:,None],boundary],axis=1);count=boundary.shape[1];wf=np.array([[0,1+k,1+(k+1)%count] for k in range(count)],int);ref=fn[subset[bind['triangle_indices']]].mean(0);actual=np.cross(poses[0,wf[:,1]]-poses[0,wf[:,0]],poses[0,wf[:,2]]-poses[0,wf[:,0]]).sum(0)
            if actual@ref<0:wf=wf[:,[0,2,1]]
            source_edges=np.array([[1+k,2+k] for k in range(len(path)-1)],int);patch=fair_disk_patch(poses,wf,source_edges,subdivisions=int(cfg.get('canthusSubdivisions',2)));name=side+'-canthus-'+str(end);sample=nearest_triangle_bindings(patch['poses'][0],v,f[skin]);out.update({name+'_'+key:patch[key] for key in ['poses','faces','skin_boundary_edges','skin_boundary_vertices']});out[name+'_face_domains']=np.full(len(patch['faces']),2,int);out[name+'_source_sample_triangle_ids']=skin[sample['triangle_indices']];out[name+'_source_sample_barycentric']=sample['barycentric'];specs.append({'id':name,'array_prefix':name,'control':side,'normal_mode':'posed'});webs.append({'part':name,'fixed_source_arc_length':float(np.linalg.norm(np.diff(path,axis=0),axis=1).sum()),'designed_inner_edge_closes_to_a_point':True})
        side_report['canthi']=webs;report[side]=side_report
    return {'arrays':out,'report':report,'patch_specs':specs}
