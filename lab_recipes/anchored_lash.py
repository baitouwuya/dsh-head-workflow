# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Canonical-mesh ARAP refinement for original lash bands with measured roots.

Fit a smooth moving-rail target while keeping measured carrier contacts exact.
Run only on a whole classified canonical component, never a cropped rectangle.
The dense solve is intentionally bounded by an explicit runtime vertex limit;
it is not a whole-head deformer. All geometry thresholds/iteration limits are
runtime inputs. Native export and continuous-morph audits remain mandatory.
"""
import numpy as np

class AnchoredLashBinding:
    def __init__(self,points,triangles,fixed_indices,*,target_strength,max_iterations,
                 convergence_tolerance,maximum_vertices,edge_weight_power=2.):
        self.points=np.asarray(points,float).copy();f=np.asarray(triangles);fixed=np.asarray(fixed_indices)
        if self.points.ndim!=2 or self.points.shape[1]!=3 or not len(self.points) or not np.isfinite(self.points).all():raise ValueError('Finite nonempty canonical positions required')
        if not isinstance(maximum_vertices,int) or isinstance(maximum_vertices,bool) or maximum_vertices<3 or len(self.points)>maximum_vertices:raise ValueError('Canonical component exceeds runtime dense-solve vertex limit')
        if f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or f.min()<0 or f.max()>=len(self.points):raise ValueError('Invalid triangle indices')
        if fixed.ndim!=1 or not len(fixed) or not np.issubdtype(fixed.dtype,np.integer) or fixed.min()<0 or fixed.max()>=len(self.points):raise ValueError('Measured fixed root indices required')
        if not np.isfinite([target_strength,convergence_tolerance,edge_weight_power]).all() or target_strength<=0 or convergence_tolerance<0 or edge_weight_power<0 or not isinstance(max_iterations,int) or isinstance(max_iterations,bool) or max_iterations<1:raise ValueError('Invalid runtime solver parameters')
        self.fixed=np.unique(fixed);self.free=np.setdiff1d(np.arange(len(self.points)),self.fixed);self.max_iterations=max_iterations;self.tolerance=float(convergence_tolerance)
        edges=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0);rest=self.points[edges[:,0]]-self.points[edges[:,1]];valid=np.linalg.norm(rest,axis=1)>0;edges=edges[valid];self.i,self.j=edges.T;self.rest=rest[valid]
        lengths=np.linalg.norm(self.rest,axis=1);self.weights=(np.median(lengths)/lengths)**float(edge_weight_power)
        if not np.isfinite(self.weights).all():raise ValueError('Source edges are numerically ill-conditioned')
        degree=np.bincount(np.r_[self.i,self.j],weights=np.r_[self.weights,self.weights],minlength=len(self.points))
        if np.any(degree==0):raise ValueError('Every canonical point must belong to a nonzero source edge')
        laplacian=np.diag(degree.astype(float));np.add.at(laplacian,(self.i,self.j),-self.weights);np.add.at(laplacian,(self.j,self.i),-self.weights)
        self.regularization=float(target_strength)*degree;matrix=laplacian+np.diag(self.regularization)
        self.inverse=np.linalg.inv(matrix[np.ix_(self.free,self.free)]) if len(self.free) else np.empty((0,0))
        self.fixed_matrix=matrix[np.ix_(self.free,self.fixed)]
        self.last_report=None

    def _rotations(self,posed):
        difference=posed[self.i]-posed[self.j];outer=self.weights[:,None,None]*difference[:,:,None]*self.rest[:,None,:];covariance=np.zeros((len(posed),3,3));np.add.at(covariance,self.i,outer);np.add.at(covariance,self.j,outer)
        u,_,vt=np.linalg.svd(covariance);rotation=u@vt;reflected=np.linalg.det(rotation)<0;u[reflected,:,-1]*=-1
        return u@vt

    def evaluate(self,target,*,carrier_points=None):
        t=np.asarray(target,float);carrier=self.points[self.fixed] if carrier_points is None else np.asarray(carrier_points,float)
        if t.shape!=self.points.shape or carrier.shape!=(len(self.fixed),3) or not np.isfinite(t).all() or not np.isfinite(carrier).all():raise ValueError('Target or carrier correspondence mismatch')
        if np.array_equal(t,self.points) and np.array_equal(carrier,self.points[self.fixed]):
            self.last_report={'iterations':0,'last_step_maximum':0.,'converged':True,'fixed_root_maximum_error':0.,'target_rms':0.}
            return self.points.copy(),np.repeat(np.eye(3)[None],len(t),axis=0)
        p=t.copy();p[self.fixed]=carrier;fixed_term=self.fixed_matrix@carrier;last_step=0.
        for iteration in range(self.max_iterations):
            rotation=self._rotations(p);term=self.weights[:,None]*np.einsum('nij,nj->ni',(rotation[self.i]+rotation[self.j])*.5,self.rest);rhs=np.zeros_like(p);np.add.at(rhs,self.i,term);np.add.at(rhs,self.j,-term)
            q=p.copy();q[self.free]=self.inverse@(rhs[self.free]+self.regularization[self.free,None]*t[self.free]-fixed_term);q[self.fixed]=carrier
            last_step=float(np.linalg.norm(q-p,axis=1).max());p=q
            if last_step<=self.tolerance:break
        if not np.isfinite(p).all():raise ValueError('Non-finite ARAP result')
        rotation=self._rotations(p);self.last_report={'iterations':iteration+1,'last_step_maximum':last_step,'converged':last_step<=self.tolerance,'fixed_root_maximum_error':float(np.linalg.norm(p[self.fixed]-carrier,axis=1).max()),'target_rms':float(np.sqrt(np.mean((p-t)**2)))}
        return p,rotation

def rigid_contact_transfer(points,source_contact_points,posed_contact_points,source_support,posed_support):
    """Move an accessory island rigidly using a local parent-band frame.

    Frame fitting uses a measured parent neighborhood. Translation is anchored
    at the frozen parent contact centroid; evaluate all individual contact gaps
    separately so a rigid fit cannot silently detach from a nonrigid parent.
    """
    arrays=[np.asarray(x,float) for x in [points,source_contact_points,posed_contact_points,source_support,posed_support]]
    if any(x.ndim!=2 or x.shape[1]!=3 or not len(x) or not np.isfinite(x).all() for x in arrays):raise ValueError('Finite nonempty XYZ arrays required')
    p,contact,posed_contact,support,posed_support=arrays
    if contact.shape!=posed_contact.shape or support.shape!=posed_support.shape or len(support)<3:raise ValueError('Contact/support correspondence mismatch')
    if np.array_equal(contact,posed_contact) and np.array_equal(support,posed_support):return p.copy(),np.eye(3)
    u,_,vt=np.linalg.svd((support-support.mean(0)).T@(posed_support-posed_support.mean(0)));rotation=vt.T@u.T
    if np.linalg.det(rotation)<0:vt[-1]*=-1;rotation=vt.T@u.T
    return (p-contact.mean(0))@rotation.T+posed_contact.mean(0),rotation
