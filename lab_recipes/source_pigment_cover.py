# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Source-derived temporary skin cover for immovable baked upper-lash pigment.

Original images, source geometry and neutral visibility remain untouched.
The native renderer must inspect the cover throughout closing/reopening.
"""
import numpy as np


def add_source_pigment_covers(source,lids,probes,roles,configuration,source_scale,source_image_rgb):
    s=source;pr=probes;cfg=configuration;settings=cfg.get('pigmentCover',{});g={k:np.asarray(x).copy() for k,x in lids.items()};scale=float(source_scale);v=np.asarray(s['vertices'],float)/scale;f=np.asarray(s['faces']);skin=np.flatnonzero(s['component'][f[:,0]]==roles['skin_component']);uvs=s['uv_0'][s['triangle_loops']];image=np.asarray(source_image_rgb)
    if image.ndim!=3 or image.shape[2]<3 or not np.isfinite(image).all():raise ValueError('Finite source RGB image required')
    image=image[:,:,:3].astype(float)/(255. if image.dtype==np.uint8 else 1.)
    if image.min()<0 or image.max()>1:raise ValueError('Source RGB image must be encoded sRGB in uint8 or unit range')
    tri=v[f];face_norm=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);vn=np.zeros_like(v)
    for corner in range(3):np.add.at(vn,f[skin,corner],face_norm[skin])
    length=np.linalg.norm(vn,axis=1);vn=np.divide(vn,length[:,None],out=np.zeros_like(vn),where=length[:,None]>0);knots=np.array(cfg['controls']['blink']['samples']);report={};specs=[]
    for side in roles['lash_bands']:
     q=pr[side+'_visible']/scale;hh=np.ptp(q[:,2]);lo=np.array([q[:,1].min()-settings.get('lateralMarginOverHeight',.12)*hh,np.quantile(q[:,2],settings.get('lowerRegionQuantile',.5))]);hi=np.array([q[:,1].max()+settings.get('lateralMarginOverHeight',.12)*hh,q[:,2].max()+settings.get('upperMarginOverHeight',.45)*hh]);W,Hh=map(int,settings.get('samplingResolution',[240,144]));depth=np.full((Hh,W),-np.inf);facebuf=np.full((Hh,W),-1,int);barybuf=np.zeros((Hh,W,3));candidate=skin[(tri[skin,:,1].max(1)>=lo[0])&(tri[skin,:,1].min(1)<=hi[0])&(tri[skin,:,2].max(1)>=lo[1])&(tri[skin,:,2].min(1)<=hi[1])]
     for fi in candidate:
      p=(tri[fi,:,1:]-lo)/(hi-lo)*[W-1,Hh-1];mn=np.maximum(np.floor(p.min(0)).astype(int),0);mx=np.minimum(np.ceil(p.max(0)).astype(int),[W-1,Hh-1]);xx,yy=np.meshgrid(np.arange(mn[0],mx[0]+1),np.arange(mn[1],mx[1]+1));d=np.stack([xx,yy],-1)-p[0];a=p[1]-p[0];b=p[2]-p[0];det=a[0]*b[1]-a[1]*b[0]
      if abs(det)<1e-12:continue
      u=(d[...,0]*b[1]-d[...,1]*b[0])/det;w=(a[0]*d[...,1]-a[1]*d[...,0])/det;bc=np.stack([1-u-w,u,w],-1);x=bc@tri[fi,:,0];mask=(bc.min(-1)>=-1e-9)&(x>depth[yy,xx]);depth[yy[mask],xx[mask]]=x[mask];facebuf[yy[mask],xx[mask]]=fi;barybuf[yy[mask],xx[mask]]=bc[mask]
     eye_ids=np.flatnonzero(np.isin(source['component'],roles['eye_components'][side]));minimum_depth=float(settings.get('minimumFrontDepth',np.min(v[eye_ids,0])-settings.get('depthBackoffOverHeight',1.25)*hh));valid=(facebuf>=0)&(depth>minimum_depth);pixels=np.argwhere(valid);fid=facebuf[valid];bc=barybuf[valid];uv=np.einsum('ni,nij->nj',bc,uvs[fid]);rgb=image[np.clip(np.round((1-uv[:,1])*(len(image)-1)).astype(int),0,len(image)-1),np.clip(np.round(uv[:,0]*(image.shape[1]-1)).astype(int),0,image.shape[1]-1)];dark=rgb.max(1)<settings.get('darkSrgbMaximum',.48);selected=np.unique(fid[dark]);
     if not len(selected):
      report[side]={'dark_source_skin_samples':0,'dark_source_faces':0,'cover_faces_with_one_source_ring':0};continue
     used=set(f[selected].ravel().tolist());expanded=skin[np.any(np.isin(f[skin],list(used)),axis=1)&(tri[skin,:,1].max(1)>=lo[0])&(tri[skin,:,1].min(1)<=hi[0])&(tri[skin,:,2].max(1)>=lo[1])&(tri[skin,:,2].min(1)<=hi[1])];vid=np.unique(f[expanded]);mapping=np.full(len(v),-1,int);mapping[vid]=np.arange(len(vid));faces=mapping[f[expanded]];basis=v[vid];norm=vn[vid];z0,z1=np.min(basis[:,2]),np.max(basis[:,2]);phase=settings.get('phaseStart',.12)+settings.get('phaseSpan',.48)*(basis[:,2]-z0)/max(z1-z0,1e-9);eps=settings.get('normalOffsetOverHeight',.008)*hh;poses=[]
     for t in knots:
      offset=eps*np.tanh((t-phase)/settings.get('transitionWidth',.12))
      if t==0:offset=np.full(len(vid),-eps)
      if t==1:offset=np.full(len(vid),eps)
      poses.append(basis+norm*offset[:,None])
     poses=np.array(poses);source_ids=[];bary=[]
     for i in vid:
      at=np.argwhere(f[expanded]==i)[0];source_ids.append(int(expanded[at[0]]));b=np.zeros(3);b[at[1]]=1;bary.append(b)
     name=side+'-pigment-cover';g[name+'_poses']=poses;g[name+'_faces']=faces;g[name+'_face_domains']=np.ones(len(faces),int);g[name+'_source_sample_triangle_ids']=np.array(source_ids);g[name+'_source_sample_barycentric']=np.array(bary);g[name+'_skin_boundary_vertices']=np.arange(len(vid));g[name+'_skin_boundary_edges']=np.empty((0,2),int);specs.append({'id':name,'array_prefix':name,'control':side,'normal_mode':'source_static'});report[side]={'dark_source_skin_samples':int(dark.sum()),'dark_source_faces':len(selected),'cover_faces_with_one_source_ring':len(expanded),'cover_vertices':len(vid),'maximum_normal_offset':float(eps),'neutral_all_subsurface':True,'source_geometry_and_image_unchanged':True,'source_face_ids':expanded.tolist()}
    return {"arrays":g,"report":report,"patch_specs":specs}
