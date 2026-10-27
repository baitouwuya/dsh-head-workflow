# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Source-triangle skin bindings and explicit fixed-boundary transition."""
import numpy as np

def nearest_triangle_bindings(points,vertices,triangles):
    """Independent plane/edge projection; returns actual triangle+barycentric binds."""
    points=np.asarray(points,float);v=np.asarray(vertices,float);f=np.asarray(triangles)
    if points.ndim!=2 or points.shape[1]!=3 or not len(points) or not np.isfinite(points).all() or v.ndim!=2 or v.shape[1]!=3 or not np.isfinite(v).all() or f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or f.min()<0 or f.max()>=len(v):raise ValueError('Expected finite points and nonempty valid integer triangles')
    f=f.astype(int);t=v[f]
    a=t[:,0];u=t[:,1]-a;w=t[:,2]-a;uu=np.einsum('ij,ij->i',u,u);uw=np.einsum('ij,ij->i',u,w);ww=np.einsum('ij,ij->i',w,w);det=uu*ww-uw*uw;valid=det>1e-30
    selected=[];coords=[];bary=[];distance=[]
    for q in points:
        d=q-a;du=np.einsum('ij,ij->i',d,u);dw=np.einsum('ij,ij->i',d,w)
        s=np.divide(du*ww-dw*uw,det,out=np.zeros(len(t)),where=valid);r=np.divide(dw*uu-du*uw,det,out=np.zeros(len(t)),where=valid);bc=np.c_[1-s-r,s,r];cp=np.einsum('ni,nij->nj',bc,t);inside=valid&(bc.min(1)>=0);dd=np.sum((cp-q)**2,axis=1);dd[~inside]=np.inf
        for i,j in [(0,1),(1,2),(2,0)]:
            edge=t[:,j]-t[:,i];den=np.einsum('ij,ij->i',edge,edge);frac=np.clip(np.divide(np.einsum('ij,ij->i',q-t[:,i],edge),den,out=np.zeros(len(t)),where=den>0),0,1);p=t[:,i]+frac[:,None]*edge;ed=np.sum((p-q)**2,axis=1);use=ed<dd;dd[use]=ed[use];cp[use]=p[use];bc[use]=0;bc[use,i]=1-frac[use];bc[use,j]=frac[use]
        k=int(np.argmin(dd));selected.append(k);coords.append(cp[k]);bary.append(bc[k]);distance.append(float(np.sqrt(dd[k])))
    return {'triangle_indices':np.array(selected),'barycentric':np.array(bary),'positions':np.array(coords),'distance':np.array(distance)}

def evaluate_bindings(vertices,triangles,triangle_indices,barycentric):
    return np.einsum('ni,nij->nj',np.asarray(barycentric,float),np.asarray(vertices,float)[np.asarray(triangles,int)[triangle_indices]])

class SkinSurfaceIndex:
    """Certify every point of a segment against actual triangle interiors."""
    def __init__(self,vertices,triangles):
        vertices=np.asarray(vertices,float);faces=np.asarray(triangles,int);self.tri=vertices[faces];self.a=self.tri[:,0];self.u=self.tri[:,1]-self.a;self.v=self.tri[:,2]-self.a
        self.uu=np.einsum('ij,ij->i',self.u,self.u);self.uv=np.einsum('ij,ij->i',self.u,self.v);self.vv=np.einsum('ij,ij->i',self.v,self.v);self.det=self.uu*self.vv-self.uv*self.uv
        normal=np.cross(self.u,self.v);length=np.linalg.norm(normal,axis=1);self.valid=(length>0)&(self.det>0);self.normal=np.divide(normal,length[:,None],out=np.zeros_like(normal),where=length[:,None]>0)
        edges=np.sort(np.stack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]],axis=1).reshape(-1,2),axis=1);unique,first=np.unique(edges,axis=0,return_index=True);self.edges=vertices[unique];self.edge_owners=first//3
        vertex_ids,first=np.unique(faces.ravel(),return_index=True);self.vertices=vertices[vertex_ids];self.vertex_owners=first//3
    def segment_coverage(self,start,end,tolerance):
        a=np.asarray(start,float);b=np.asarray(end,float)
        if a.shape!=(3,) or b.shape!=(3,) or not np.isfinite([*a,*b,tolerance]).all() or tolerance<0:raise ValueError('Invalid segment or tolerance')
        def values(p):
            d=p-self.a;distance=np.einsum('ij,ij->i',d,self.normal);projected=d-distance[:,None]*self.normal;pu=np.einsum('ij,ij->i',projected,self.u);pv=np.einsum('ij,ij->i',projected,self.v);u=np.divide(pu*self.vv-pv*self.uv,self.det,out=np.zeros(len(self.det)),where=self.valid);v=np.divide(pv*self.uu-pu*self.uv,self.det,out=np.zeros(len(self.det)),where=self.valid)
            return distance,np.c_[1-u-v,u,v]
        da,ba=values(a);db,bb=values(b);lo=np.zeros(len(self.tri));hi=np.ones(len(self.tri));valid=self.valid.copy()
        constraints=[(tolerance-da,-(db-da)),(tolerance+da,db-da)]+[(ba[:,k]+1e-12,bb[:,k]-ba[:,k]) for k in range(3)]
        for c,d in constraints:
            positive=d>0;negative=d<0;zero=~(positive|negative);valid&=~(zero&(c<0));lo[positive]=np.maximum(lo[positive],-c[positive]/d[positive]);hi[negative]=np.minimum(hi[negative],-c[negative]/d[negative])
        intervals=[(max(0,float(l)),min(1,float(h)),int(i)) for i,(l,h,ok) in enumerate(zip(lo,hi,valid)) if ok and l<=h and h>=0 and l<=1]
        # Exact edge-cylinder and vertex-sphere intervals complete the triangle
        # distance neighborhood, including points just beyond a face boundary.
        direction=b-a
        def quadratic_intervals(w,d):
            aa=np.einsum('ij,ij->i',d,d);bb=2*np.einsum('ij,ij->i',w,d);cc=np.einsum('ij,ij->i',w,w)-tolerance*tolerance;disc=bb*bb-4*aa*cc;ok=((aa>0)&(disc>=0))|((aa==0)&(cc<=0));root=np.sqrt(np.maximum(disc,0));low=np.divide(-bb-root,2*aa,out=np.zeros(len(aa)),where=aa>0);high=np.divide(-bb+root,2*aa,out=np.ones(len(aa)),where=aa>0);return np.maximum(0,low),np.minimum(1,high),ok
        lo,hi,ok=quadratic_intervals(a-self.vertices,np.broadcast_to(direction,self.vertices.shape))
        intervals.extend((float(l),float(h),int(owner)) for l,h,v,owner in zip(lo,hi,ok,self.vertex_owners) if v and l<=h)
        edge=self.edges[:,1]-self.edges[:,0];den=np.einsum('ij,ij->i',edge,edge);w=a-self.edges[:,0];u0=np.divide(np.einsum('ij,ij->i',w,edge),den,out=np.zeros(len(den)),where=den>0);ud=np.divide(edge@direction,den,out=np.zeros(len(den)),where=den>0);lo,hi,ok=quadratic_intervals(w-u0[:,None]*edge,direction-ud[:,None]*edge);ok&=den>0
        for c,d in [(u0,ud),(1-u0,-ud)]:
            positive=d>0;negative=d<0;zero=~(positive|negative);ok&=~(zero&(c<0));lo[positive]=np.maximum(lo[positive],-c[positive]/d[positive]);hi[negative]=np.minimum(hi[negative],-c[negative]/d[negative])
        intervals.extend((float(l),float(h),int(owner)) for l,h,v,owner in zip(lo,hi,ok,self.edge_owners) if v and l<=h)
        intervals.sort()
        cursor=0.;gaps=[];support=[]
        for l,h,i in intervals:
            if l>cursor+1e-10:gaps.append([cursor,l])
            if h>cursor:support.append(i);cursor=h
        if cursor<1-1e-10:gaps.append([cursor,1.])
        return {'covered':not gaps,'uncovered_parameter_intervals':gaps,'supporting_triangle_indices':support,'tolerance':float(tolerance)}

def transition_outer_boundary(poses,anchor_indices,anchor_positions,cross_section_samples,exponent=1):
    p=np.asarray(poses,float);idx=np.asarray(anchor_indices,int);attached=np.asarray(anchor_positions,float)
    if p.ndim!=3 or p.shape[2]!=3 or not len(p) or isinstance(cross_section_samples,bool) or not isinstance(cross_section_samples,(int,np.integer)) or cross_section_samples<4 or cross_section_samples%4:raise ValueError('Expected poses and a cross-section sample count divisible by four')
    m=int(cross_section_samples);rings=(p.shape[1]-2)//m
    if p.ndim!=3 or p.shape[2]!=3 or p.shape[1]!=rings*m+2 or len(idx)!=rings+2 or attached.shape!=(len(idx),3):raise ValueError('Hood/anchor topology mismatch')
    if not np.isfinite(p).all() or not np.isfinite(attached).all() or not np.isfinite(exponent) or exponent<=0:raise ValueError('Invalid finite positions or exponent')
    expected=np.r_[np.arange(rings)*m+m//4,p.shape[1]-2,p.shape[1]-1]
    if not np.array_equal(idx,expected):raise ValueError('Anchor indices must identify each outer pole and both caps in order')
    if not np.array_equal(p[:,idx],np.broadcast_to(p[0,idx],p[:,idx].shape)):raise ValueError('Input outer boundary must already be fixed')
    delta=attached-p[0,idx];phi=2*np.pi*np.arange(m)/m;weight=((1+np.sin(phi))/2)**exponent;offset=np.concatenate([(delta[:-2,None,:]*weight[None,:,None]).reshape(-1,3),delta[-2:]])
    result=p+offset[None,:,:];result[:,idx]=attached
    return result

def weld_identical_generated_trajectories(poses,faces):
    """Only merge vertices identical at every exported knot; source mesh excluded."""
    p=np.asarray(poses);f=np.asarray(faces,int)
    trajectories=np.transpose(p,(1,0,2)).reshape(p.shape[1],-1)
    unique,keep,remap=np.unique(trajectories,axis=0,return_index=True,return_inverse=True)
    mapped=remap[f];valid=(mapped[:,0]!=mapped[:,1])&(mapped[:,1]!=mapped[:,2])&(mapped[:,2]!=mapped[:,0]);out=mapped[valid]
    return {'poses':p[:,keep],'faces':out,'kept_vertex_indices':keep,'old_to_new':remap,'removed_zero_edge_faces':int((~valid).sum()),'merged_vertices':int(p.shape[1]-len(keep))}
