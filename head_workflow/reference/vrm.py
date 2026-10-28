# SPDX-License-Identifier: GPL-3.0-or-later
"""Private VRM 1.0 geometry reader; exports only the normalized profile contract.

Intentionally bounded: embedded GLB, triangle primitives sharing positions and
morph streams, one expression mesh node at an identity world transform. Reject
unsupported layouts rather than silently interpreting them as this export.
"""
from pathlib import Path
import numpy as np
from .pd_adapter import PDReference


from ..pd_pack.gltf import GLB


class VRMReference(PDReference):
    def __init__(self,path,expression='blink'):
        self.glb=GLB(Path(path).read_bytes())
        g=self.glb.g
        presets=g.get('extensions',{}).get('VRMC_vrm',{}).get('expressions',{}).get('preset',{})
        if expression not in presets:raise ValueError('missing VRM 1.0 expression preset')
        self.expression=expression
        exp=presets[expression]
        if exp.get('isBinary',False):raise ValueError('binary expression cannot provide five continuous weights')
        if exp.get('materialColorBinds') or exp.get('textureTransformBinds'):
            raise ValueError('expression includes unsupported non-geometric bindings')
        binds=exp.get('morphTargetBinds',[])
        nodes={b['node'] for b in binds}
        if len(nodes)!=1:raise ValueError('one expression mesh node required')
        self.node=nodes.pop()
        if not isinstance(self.node,int) or not 0 <= self.node < len(g['nodes']):
            raise ValueError('invalid expression node')
        parents={}
        for i,n in enumerate(g['nodes']):
            for child in n.get('children',[]):
                if child in parents:raise ValueError('ambiguous node parent')
                parents[child]=i
        i=self.node;seen=set()
        while True:
            if i in seen:raise ValueError('node cycle')
            seen.add(i);n=g['nodes'][i]
            for key,identity in [('translation',[0,0,0]),('rotation',[0,0,0,1]),('scale',[1,1,1]),('matrix',np.eye(4).ravel().tolist())]:
                if key in n and not np.allclose(n[key],identity,atol=1e-8):
                    raise ValueError('nonidentity mesh world transform requires a dedicated adapter')
            if i not in parents:break
            i=parents[i]
        self.mesh_index=g['nodes'][self.node]['mesh']
        if not isinstance(self.mesh_index,int) or not 0 <= self.mesh_index < len(g['meshes']):
            raise ValueError('invalid expression mesh')
        mesh=g['meshes'][self.mesh_index]
        prims=mesh['primitives'];first=prims[0]
        if any(p['attributes']['POSITION']!=first['attributes']['POSITION'] or p.get('targets',[])!=first.get('targets',[]) for p in prims):
            raise ValueError('primitives must share positions and morph targets')
        if any(p.get('mode',4)!=4 for p in prims):raise ValueError('triangles required')
        if any(mesh.get('weights',[])) or any(g['nodes'][self.node].get('weights',[])):
            raise ValueError('nonzero default morph weights require explicit neutral evaluation')
        self.base=self.glb.accessor(first['attributes']['POSITION']).astype(float)
        if self.base.shape[1]!=3:raise ValueError('POSITION must be VEC3')
        self.delta=np.zeros_like(self.base)
        self.binding_names=[]
        names=mesh.get('extras',{}).get('targetNames',[])
        for bind in binds:
            weight=bind['weight'];idx=bind['index']
            if not np.isfinite(weight) or not 0 <= weight <= 1:raise ValueError('invalid VRM morph weight')
            if not isinstance(idx,int) or not 0 <= idx < len(first['targets']):raise ValueError('invalid morph target index')
            target=first['targets'][idx]
            delta=self.glb.accessor(target['POSITION'])
            if delta.shape!=self.base.shape:raise ValueError('morph count mismatch')
            self.delta+=weight*delta
            self.binding_names.append(names[idx] if idx<len(names) else f'target_{idx}')
        faces=[];slots=[];start=0
        for p in prims:
            index=self.glb.accessor(p['indices'])
            if index.dtype.kind not in 'ui' or index.shape[1]!=1 or len(index)%3 or np.any(index>=len(self.base)):
                raise ValueError('invalid triangle indices')
            f=index.reshape(-1,3).astype(int);faces.append(f)
            slots.append({'material':g['materials'][p['material']]['name'],'tri_start':start,'tri_count':len(f)})
            start+=len(f)
        self.faces=np.concatenate(faces)
        self.desc={'slots':slots}
        self.lash_region='FaceEyelash' if any('FaceEyelash' in s['material'] for s in slots) else 'FaceEyeline'
        if not any(self.lash_region in s['material'] for s in slots):raise ValueError('missing lash/eyeline band')
        self.axis=np.array([[1.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])

    def evaluate(self,params,blink):
        if params:raise ValueError('exported VRM has no PD identity-parameter adapter')
        if not np.isfinite(blink) or not 0 <= blink <= 1:raise ValueError('blink out of range')
        return (self.base+blink*self.delta)@self.axis.T,self.faces.copy()

    def provenance(self,params):
        return {'pack':'operator-base-vrm','pack_version':'VRM-1.0',
                'private_input_sha256':self.glb.sha256,
                'expression':self.expression,'morph_targets':self.binding_names,
                'expression_note':'Native VRM preset binding, not the PD Eye.Joy surrogate',
                'band_source':self.lash_region,
                'band_note':'Geometric eyeline sheet used as lash-band anchor proxy' if self.lash_region=='FaceEyeline' else 'Geometric lash sheet',
                'identity_parameters':{},'evaluation':'VRM morphTargetBinds; glTF +Y up to Blender +Z up'}
