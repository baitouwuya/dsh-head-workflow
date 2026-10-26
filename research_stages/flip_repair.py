# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import numpy as np,collections
def flip_repair(points,faces,uvs,allowed,passes=12):
    p=np.array(points,float);f=np.array(faces,int).copy();uv=np.array(uvs,float).copy();log=[]
    def evaluate(ff):
        edges=collections.defaultdict(list)
        for i,tri in enumerate(ff):
            for a,b in zip(tri,np.roll(tri,-1)):edges[tuple(sorted((int(a),int(b))))].append(i)
        q=p[ff];n=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);ar=np.linalg.norm(n,axis=1);n/=np.maximum(ar[:,None],1e-30)
        pairs={e:u for e,u in edges.items() if len(u)==2}
        dots={e:float(n[u[0]]@n[u[1]]) for e,u in pairs.items()}
        return edges,pairs,dots,ar
    edges,pairs,dots,ar=evaluate(f);floor=np.cos(np.radians(85))
    for step in range(passes):
        changed=0
        for edge in sorted(dots,key=dots.get):
            if edge not in dots or dots[edge]>=0:continue
            ia,ib=pairs[edge]
            if not ({ia,ib}&allowed):continue
            old0=f[ia].copy();old1=f[ib].copy();a,b=edge
            if not any(old0[i]==a and old0[(i+1)%3]==b for i in range(3)):a,b=b,a
            c=next(int(x) for x in old0 if x not in (a,b));d=next(int(x) for x in old1 if x not in (a,b))
            if c==d or tuple(sorted((c,d))) in edges:continue
            tex={};valid=True
            for fi in [ia,ib]:
                for k,t in zip(f[fi],uv[fi]):
                    if int(k) in tex and np.max(np.abs(tex[int(k)]-t))>1e-5:valid=False
                    tex[int(k)]=t.copy()
            if not valid:continue
            candidate=f.copy();candidate[ia]=[c,d,b];candidate[ib]=[d,c,a]
            ee,pp,dd,aa=evaluate(candidate)
            if min(aa[ia],aa[ib])<1e-13:continue
            oldcost=sum(max(floor-v,0)**2 for v in dots.values())
            newcost=sum(max(floor-v,0)**2 for v in dd.values())
            if newcost>=oldcost-1e-8:continue
            f=candidate;uv[ia]=[tex[k] for k in f[ia]];uv[ib]=[tex[k] for k in f[ib]]
            log.append({'pass':step,'faces':[int(ia),int(ib)],'old_edge':[a,b],'new_edge':[c,d],'energy_before':oldcost,'energy_after':newcost})
            edges,pairs,dots,ar=ee,pp,dd,aa;changed+=1
            allowed.update([ia,ib])
        if not changed:break
    return f,uv,{'flips':log,'remaining_above_90':sum(v<0 for v in dots.values()),'max_angle':float(np.degrees(np.arccos(np.clip(min(dots.values()),-1,1))))}
