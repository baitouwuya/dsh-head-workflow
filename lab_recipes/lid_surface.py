# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Measured-aperture closed hood surface. Actual export auditing is separate."""
import numpy as np,math
def curve(eye):
 rim=np.array(eye['rim_xyz']);smooth=[]
 for j in range(len(rim)):
  p0,p1,p2,p3=[rim[k%len(rim)] for k in (j-1,j,j+1,j+2)]
  for u in np.linspace(0,1,48,endpoint=False):smooth.append(.5*(2*p1+(-p0+p2)*u+(2*p0-5*p1+4*p2-p3)*u*u+(-p0+3*p1-3*p2+p3)*u*u*u))
 return np.array(smooth)

def build(eye,upper,d):
 sm=curve(eye);alo=sm[:,1].min();ahi=sm[:,1].max();lo=alo-d['corner_extension_m'];hi=ahi+d['corner_extension_m'];N=d['length_segments'];M=d['cross_section_samples'];center=np.array(eye['sphere_center']);a=eye['affine_globe'];rad=eye['sphere_radius'];sign=1 if upper else -1
 next_sm=np.roll(sm,-1,axis=0)
 def raw_pair(y):
  y=np.clip(y,alo,ahi);diff=next_sm-sm;valid=(np.minimum(sm[:,1],next_sm[:,1])-1e-12<=y)&(y<=np.maximum(sm[:,1],next_sm[:,1])+1e-12)&(np.abs(diff[:,1])>1e-14)
  hit=sm[valid]+diff[valid]*np.clip((y-sm[valid,1])/diff[valid,1],0,1)[:,None]
  if not len(hit):
   pt=sm[np.argmin(abs(sm[:,1]-y))];return pt,pt
  return hit[np.argmin(hit[:,2])],hit[np.argmax(hit[:,2])]
 grid=np.linspace(lo,hi,1025);values=np.array([raw_pair(y) for y in grid]);sigma=d.get('envelope_smoothing_m',.0008)/(grid[1]-grid[0]);half=int(math.ceil(4*sigma));k=np.exp(-.5*(np.arange(-half,half+1)/sigma)**2);k/=k.sum()
 for i in range(2):
  for j in [0,2]:values[:,i,j]=np.convolve(np.pad(values[:,i,j],half,mode='edge'),k,mode='valid')
 maxgap=np.max(values[:,1,2]-values[:,0,2])
 def rim_pair(y):return tuple(np.array([np.interp(y,grid,values[:,i,0]),y,np.interp(y,grid,values[:,i,2])]) for i in range(2))
 params=[]
 for j in range(1,N):
  theta=np.pi*j/N;y=(lo+hi)/2-(hi-lo)/2*np.cos(theta);fac=np.sin(theta);bottom,top=rim_pair(y);rim=top if upper else bottom;seam=bottom[2]+(1+d['closure_height_fraction'])/2*(top[2]-bottom[2])
  for k in range(M):params.append((y,rim[2],rim[0],fac,2*np.pi*k/M,seam))
 par=np.array(params);y,z0,rx,fac,phi,seam=par.T
 def gx(y,z):
  dy=y-center[1];dz=z-center[2];q=rad*rad-dy*dy-dz*dz;epsilon=d['globe_softplus_epsilon_m2']
  return center[0]+a['depth_scale']*np.sqrt(.5*(q+np.sqrt(q*q+epsilon*epsilon)))+a['shear_y']*dy+a['shear_z']*dz
 def smoothmax(x,y):
  eps=d['smoothmax_epsilon_m'];return .5*(x+y+np.sqrt((x-y)**2+eps*eps))
 def positions(v):
  outer=z0+sign*d['collar_width_m']*fac
  aperture_factor=np.array([(rim_pair(yy)[1][2]-rim_pair(yy)[0][2])/maxgap for yy in y])**2
  inner=z0+v*(seam-sign*d['closure_overlap_m']*aperture_factor/2-z0)
  aa=d['shell_thickness_m']*.5*fac;bb=np.abs(outer-inner)/2
  norm=np.sqrt((aa*np.cos(phi))**2+(bb*np.sin(phi))**2)
  cp=aa*np.cos(phi)/norm;sp=bb*np.sin(phi)/norm
  z=(outer+inner)/2+(outer-inner)/2*sp;w=(1-sp)/2
  front=smoothmax(gx(y,z)+d['clearance_m']+d['shell_thickness_m'],rx)
  x=front+d['shell_thickness_m']*.5*fac*(cp-1)+(d['upper_closure_depth_offset_m']*v*w*aperture_factor if upper else 0)
  pts=list(np.column_stack([x,y,z]))
  for yy in (lo,hi):
   b,t=rim_pair(yy);p=t if upper else b;pts.append([smoothmax(gx(yy,p[2])+d['clearance_m']+d['shell_thickness_m'],p[0]),yy,p[2]])
  origin=np.array([center[0],(lo+hi)/2,center[2]])
  return (np.array(pts)-origin).astype(np.float32).astype(float)+origin
 faces=[]
 for j in range(N-2):
  for k in range(M):
   aa=j*M+k;b=j*M+(k+1)%M;c=(j+1)*M+(k+1)%M;dd=(j+1)*M+k;faces.extend([(aa,b,c),(aa,c,dd)])
 start=(N-1)*M;end=start+1
 for k in range(M):faces.extend([(start,(k+1)%M,k),(end,(N-2)*M+k,(N-2)*M+(k+1)%M)])
 return positions,np.array(faces)

