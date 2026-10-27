# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Pure GLB morph-cycle serialization; no Blender, network or asset upload."""
import copy,hashlib,json,math,struct


def unpack_glb(data):
    if len(data)<20 or struct.unpack_from('<4sII',data)!= (b'glTF',2,len(data)):
        raise ValueError('A complete GLB version 2 buffer is required')
    chunks=[];offset=12
    while offset<len(data):
        if offset+8>len(data):raise ValueError('Truncated GLB chunk header')
        size,kind=struct.unpack_from('<I4s',data,offset);offset+=8
        if size%4 or offset+size>len(data):raise ValueError('Invalid GLB chunk length')
        chunks.append((kind,data[offset:offset+size]));offset+=size
    if not chunks or chunks[0][0]!=b'JSON' or sum(t==b'JSON' for t,_ in chunks)!=1 or sum(t==b'BIN\0' for t,_ in chunks)>1:
        raise ValueError('Expected exactly one first JSON chunk and at most one BIN chunk')
    document=json.loads(chunks[0][1].rstrip(b' \x00'))
    binary=next((payload for kind,payload in chunks if kind==b'BIN\0'),b'')
    return document,binary,[(kind,payload) for kind,payload in chunks if kind not in (b'JSON',b'BIN\0')]


def pack_glb(document,binary,other_chunks=()):
    j=json.dumps(document,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode();j+=b' '*((-len(j))%4)
    b=bytes(binary);b+=b'\0'*((-len(b))%4);chunks=[(b'JSON',j)]
    if b:chunks.append((b'BIN\0',b))
    chunks.extend(other_chunks);body=b''.join(struct.pack('<I4s',len(p),k)+p for k,p in chunks)
    return struct.pack('<4sII',b'glTF',2,12+len(body))+body


def embedded_image_hashes(document,binary):
    result=[]
    for index,image in enumerate(document.get('images',[])):
        if 'bufferView' not in image:raise ValueError('Sealed GLB images must be embedded bufferViews')
        view=document['bufferViews'][image['bufferView']]
        if view.get('buffer',0)!=0:raise ValueError('Embedded image must use the GLB binary buffer')
        start=view.get('byteOffset',0);end=start+view['byteLength']
        if start<0 or end>len(binary):raise ValueError('Embedded image bufferView is out of range')
        result.append({'image_index':index,'sha256':hashlib.sha256(binary[start:end]).hexdigest(),'bytes':end-start,'mimeType':image.get('mimeType')})
    return result


def _mapping(mapping):
    result={};owned=set()
    if not isinstance(mapping,dict) or not mapping:raise ValueError('Runtime morph mapping required')
    for control,knots in mapping.items():
        if not isinstance(control,str) or not control or not isinstance(knots,list) or not knots:raise ValueError('Invalid controller')
        normalized=[];seen=set()
        for item in knots:
            w=item.get('value');name=item.get('name')
            if isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or not 0<w<=1 or w in seen:raise ValueError('Invalid raw morph knot')
            if not isinstance(name,str) or not name or name in owned:raise ValueError('Duplicate or invalid target name')
            seen.add(w);owned.add(name);normalized.append((float(w),name))
        normalized.sort()
        if normalized[-1][0]!=1:raise ValueError('Every controller must end at one')
        result[control]=normalized
    return result


def append_blink_cycles(glb_bytes,mapping,scenarios,cycle_values,times):
    """Append independent/bilateral clips using actual exported mesh targetNames.

    Each channel starts from its node/mesh rest weights, clears only configured
    blink targets, then interpolates the named knots. Unrelated animations and
    target rest values remain intact. Original BIN bytes are an unchanged prefix.
    """
    controls=_mapping(mapping);values=list(cycle_values);times=list(times)
    if len(times)!=len(values) or len(times)<3 or any(isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) or t<0 for t in times) or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Strictly increasing finite nonnegative cycle times required')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in values) or values[0]!=0 or values[-1]!=0 or 1 not in values:raise ValueError('Cycle must start neutral, close fully and reopen')
    doc,original,extra=unpack_glb(glb_bytes);doc=copy.deepcopy(doc)
    buffers=doc.setdefault('buffers',[{'byteLength':len(original)}])
    if len(buffers)!=1 or 'uri' in buffers[0] or buffers[0].get('byteLength',0)>len(original):raise ValueError('One embedded GLB buffer required')
    images_before=embedded_image_hashes(doc,original);binary=bytearray(original);views=doc.setdefault('bufferViews',[]);accessors=doc.setdefault('accessors',[]);animations=doc.setdefault('animations',[])
    configured={name for knots in controls.values() for _,name in knots};participants={c:0 for c in controls};nodes=[]
    for index,node in enumerate(doc.get('nodes',[])):
        if 'mesh' not in node:continue
        mesh=doc['meshes'][node['mesh']];names=mesh.get('extras',{}).get('targetNames',[])
        if not configured.intersection(names):continue
        if len(names)!=len(set(names)) or any(len(p.get('targets',[]))!=len(names) for p in mesh['primitives']):raise ValueError('Morph target names/topology are ambiguous')
        rest=list(node.get('weights',mesh.get('weights',[0.]*len(names))))
        if len(rest)!=len(names) or any(isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) for w in rest):raise ValueError('Invalid exported rest weights')
        applicable=[]
        for control,knots in controls.items():
            present={name for _,name in knots}.intersection(names)
            if present and len(present)!=len(knots):raise ValueError('Incomplete controller on exported mesh')
            if present:applicable.append(control);participants[control]+=1
        nodes.append((index,names,rest,applicable))
    if not nodes or any(n==0 for n in participants.values()):raise ValueError('An exported controller has no participating mesh')
    def accessor(data):
        padding=(-len(binary))%4;binary.extend(b'\0'*padding);offset=len(binary);binary.extend(struct.pack('<'+'f'*len(data),*data))
        view_id=len(views);views.append({'buffer':0,'byteOffset':offset,'byteLength':len(data)*4});accessor_id=len(accessors);accessors.append({'bufferView':view_id,'componentType':5126,'count':len(data),'type':'SCALAR','min':[min(data)],'max':[max(data)]});return accessor_id
    time_id=accessor(times);existing={a.get('name') for a in animations};records=[]
    if not isinstance(scenarios,list) or not scenarios:raise ValueError('Runtime scenarios required')
    for scenario in scenarios:
        name=scenario.get('id');active=scenario.get('controls')
        if not isinstance(name,str) or not name or name in existing or not isinstance(active,list) or not active or len(active)!=len(set(active)) or any(c not in controls for c in active):raise ValueError('Invalid or duplicate clip scenario')
        existing.add(name);animation={'name':name,'samplers':[],'channels':[]}
        for node_index,names,rest,applicable in nodes:
            samples=[]
            for value in values:
                weights=rest.copy()
                for i,target in enumerate(names):
                    if target in configured:weights[i]=0.
                for control in applicable:
                    v=value if control in active else 0.;points=[(0.,None)]+controls[control]
                    for (lo,ln),(hi,hn) in zip(points,points[1:]):
                        if lo<=v<=hi:
                            t=(v-lo)/(hi-lo)
                            if ln is not None:weights[names.index(ln)]=1-t
                            weights[names.index(hn)]=t;break
                samples.extend(weights)
            output=accessor(samples);sampler=len(animation['samplers']);animation['samplers'].append({'input':time_id,'output':output,'interpolation':'LINEAR'});animation['channels'].append({'sampler':sampler,'target':{'node':node_index,'path':'weights'}})
        animations.append(animation);records.append({'name':name,'frames':len(values),'channels':len(animation['channels']),'controls':active})
    buffers[0]['byteLength']=len(binary);result=pack_glb(doc,binary,extra);after_doc,after_bin,_=unpack_glb(result);images_after=embedded_image_hashes(after_doc,after_bin)
    if images_before!=images_after or bytes(binary[:len(original)])!=original:raise AssertionError('Original binary/image bytes changed')
    return result,{'clips':records,'controller_participants':participants,'embedded_images':images_after,'original_binary_prefix_preserved':True,'unrelated_rest_weights_preserved':True,'input_sha256':hashlib.sha256(glb_bytes).hexdigest(),'output_sha256':hashlib.sha256(result).hexdigest()}


def read_weight_clip(glb_bytes,clip_name):
    """Decode actual sealed weight channels, not a reconstructed controller curve."""
    doc,binary,_=unpack_glb(glb_bytes);matches=[a for a in doc.get('animations',[]) if a.get('name')==clip_name]
    if len(matches)!=1:raise ValueError('One exact sealed animation clip must match')
    def floats(index):
        accessor=doc['accessors'][index]
        if accessor['componentType']!=5126 or accessor['type']!='SCALAR' or 'sparse' in accessor:raise ValueError('Expected sealed scalar float animation accessor')
        view=doc['bufferViews'][accessor['bufferView']]
        if view.get('buffer',0)!=0 or view.get('byteStride',4)!=4:raise ValueError('Expected tightly packed GLB animation buffer')
        offset=view.get('byteOffset',0)+accessor.get('byteOffset',0);count=accessor['count']
        if offset<0 or offset+count*4>len(binary):raise ValueError('Animation accessor out of range')
        return list(struct.unpack_from('<'+'f'*count,binary,offset))
    tracks=[];seen=set()
    for channel in matches[0]['channels']:
        if channel['target']['path']!='weights':continue
        node_index=channel['target']['node']
        if node_index in seen:raise ValueError('Multiple weight channels target the same node')
        seen.add(node_index);node=doc['nodes'][node_index];mesh=doc['meshes'][node['mesh']];names=mesh.get('extras',{}).get('targetNames',[]);sampler=matches[0]['samplers'][channel['sampler']]
        if sampler.get('interpolation','LINEAR')!='LINEAR':raise ValueError('Native cycle verifier expects LINEAR sealed weight interpolation')
        times=floats(sampler['input']);weights=floats(sampler['output'])
        if not names or len(weights)!=len(times)*len(names) or len(times)<2 or any(not math.isfinite(x) for x in times+weights) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Invalid sealed animation channel samples')
        tracks.append({'node_index':node_index,'node_name':node.get('name'),'binding':node.get('extras',{}).get('native_animation_binding'),'target_names':names,'times':times,'weights':[weights[i:i+len(names)] for i in range(0,len(weights),len(names))]})
    if not tracks:raise ValueError('No sealed weight channels')
    return tracks


def sample_weight_track(track,time):
    if isinstance(time,bool) or not isinstance(time,(int,float)) or not math.isfinite(time):raise ValueError('Finite sample time required')
    times=track['times'];weights=track['weights']
    if time<=times[0]:return weights[0].copy()
    if time>=times[-1]:return weights[-1].copy()
    import bisect
    i=bisect.bisect_right(times,time)-1;w=(time-times[i])/(times[i+1]-times[i]);return [a*(1-w)+b*w for a,b in zip(weights[i],weights[i+1])]
