# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,math,json,collections,numpy as np
    from lab_recipes.aperture_contract import weighted_clearance_projection
    
    def edge_distance(y,z,poly):
        pt=np.array([y,z]);best=1e9
        for a,b in zip(poly,np.roll(poly,-1,axis=0)):
            u=b-a;t=np.clip(np.dot(pt-a,u)/np.dot(u,u),0,1);best=min(best,float(np.linalg.norm(pt-(a+t*u))))
        return best
    
    def vertical_limits(e,y):
        zz=[]
        for a,b in zip(e['polygon'],np.roll(e['polygon'],-1,axis=0)):
            if min(a[0],b[0])-1e-10<=y<=max(a[0],b[0])+1e-10 and abs(a[0]-b[0])>1e-10:
                t=(y-a[0])/(b[0]-a[0]);zz.append(float(a[1]+t*(b[1]-a[1])))
        return (min(zz),max(zz)) if zz else None
    h.vertical_limits=vertical_limits
    
    def is_foreground_hair(obj,e,p,index=None):
        if obj==h.hair and index is not None and hasattr(h,'hair_editable_mask'):return not h.hair_editable_mask[index]
        return obj==h.hair and p[0]>max(q[0] for q in e['rim_xyz'])+.0015
    
    def blink_coords(obj,base,e,weight):
        out=base.copy();moved=0
        for i,p in enumerate(base):
            if p[0]<.004 or is_foreground_hair(obj,e,p,i):continue
            limits=vertical_limits(e,p[1])
            if not limits:continue
            low,up=limits;gap=up-low
            if gap<.00005:continue
            middle=(low+up)/2;upper=p[2]>=middle
            lash=obj==h.hair and hasattr(h,'work_hair_components') and h.work_hair_components[i] in h.config['lash_components']
            if lash:upper=True
            bound=up if upper else low
            dist=max(0,p[2]-up) if upper else max(0,low-p[2]);falloff=h.config['lid_falloff_upper'] if upper else h.config['lid_falloff_lower']
            if dist>falloff*2.5:continue
            w=1.0 if lash else math.exp(-(dist/falloff)**2);close=low+gap*h.config['lid_close_fraction']
            znew=p[2]+(close-bound+(-.00030 if upper else .00030))*w*weight
            go=h.globe_x(e,p[1],p[2]);gn=h.globe_x(e,p[1],znew)
            out[i,2]=znew;out[i,0]=p[0]+(gn-go)*w*weight
            if dist<.00015:out[i,0]=weighted_clearance_projection(out[i,0],gn+.00045,weight)
            moved+=1
        return out,moved
    h.blink_coords=blink_coords
    
    h.lid_audit=[]
    for obj in [h.body,h.hair]:
        base=np.empty((len(obj.data.vertices),3),np.float32);obj.data.shape_keys.key_blocks['Basis'].data.foreach_get('co',base.ravel());fit=base.copy()
        for e in h.eyes:
            cy,cz=e['center_yz'];r=e['sphere_radius'];adjusted=0
            for i,p in enumerate(base):
                if p[0]<.004 or is_foreground_hair(obj,e,p,i) or abs(p[1]-cy)>r*1.1 or abs(p[2]-cz)>r:continue
                d=edge_distance(p[1],p[2],e['polygon'])
                if d>.004:continue
                w=math.exp(-(d/.0017)**2)
                target=h.globe_x(e,p[1],p[2])+.00055
                fit[i,0]=p[0]+(target-p[0])*w;adjusted+=1
            h.lid_audit.append({'mesh':obj.name,'eye':e['label'],'neutral_rim_fit_vertices':adjusted})
        delta=fit-base
        for key in obj.data.shape_keys.key_blocks:
            a=np.empty_like(base);key.data.foreach_get('co',a.ravel());key.data.foreach_set('co',(a+delta).ravel());key.value=0
        obj.data.vertices.foreach_set('co',fit.ravel());obj.data.update()
        for e in h.eyes:
            label=e['label'].capitalize()
            for weight in [.25,.5,.75,1]:
                coords,moved=blink_coords(obj,fit,e,weight);key=obj.shape_key_add(name='blink'+label+'_'+str(int(weight*100)),from_mix=False);key.data.foreach_set('co',coords.ravel());key.value=0
            h.lid_audit.append({'mesh':obj.name,'eye':e['label'],'blink_vertices':moved})
    
    def set_blink(left=0,right=0):
        for obj in [h.body,h.hair]+getattr(h,'socket_rims',[]):
            if not obj.data.shape_keys:continue
            for key in obj.data.shape_keys.key_blocks:
                if key.name.startswith('blink'):key.value=0
            for label,w in [('Left',left),('Right',right)]:
                w=np.clip(w,0,1);step=int(math.floor(w*4));t=w*4-step
                if step>0:
                    k=obj.data.shape_keys.key_blocks.get('blink'+label+'_'+str(step*25))
                    if k:k.value=1-t
                if step<4 and t>0:
                    k=obj.data.shape_keys.key_blocks.get('blink'+label+'_'+str((step+1)*25))
                    if k:k.value=t
        bpy.context.view_layer.update()
    h.set_blink=set_blink
    (h.root/'lid-construction.json').write_text(json.dumps(h.lid_audit,indent=2))
    h.render('fitted-neutral')
    h.set_blink(1,1);h.render('blink-full',views={'front':h.views['front'],'left45':h.views['left45']})
    h.set_blink(.5,0);h.render('blink-half',views={'front':h.views['front']});h.set_blink(0,0)
    print('LIDS',json.dumps(h.lid_audit))
