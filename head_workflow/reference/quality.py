# SPDX-License-Identifier: GPL-3.0-or-later
"""Dimensionless closure measurements; no point arrays in returned reports."""
import numpy as np
from .geometry import boundary_loops,split_lids,frame_for,normalize


def closure_metrics(upper,lower,trim=.02,count=129):
    """Vertical cross-sections of labeled polylines, excluding trimmed canthi.

    If a path folds laterally, use the upper/lower envelope and report it.
    Negative height gap is overlap; depth offset is measured separately.
    """
    upper,lower=np.asarray(upper),np.asarray(lower)
    lo=max(upper[:,0].min(),lower[:,0].min())+trim
    hi=min(upper[:,0].max(),lower[:,0].max())-trim
    if hi<=lo:raise ValueError('no shared lateral interval')
    gaps=[];depth=[];folded=0
    for x in np.linspace(lo,hi,count):
        pair=[]
        for path,take_max in ((upper,True),(lower,False)):
            hits=[]
            for a,b in zip(path,path[1:]):
                if min(a[0],b[0])-1e-10<=x<=max(a[0],b[0])+1e-10 and abs(b[0]-a[0])>1e-12:
                    hits.append(a+(x-a[0])/(b[0]-a[0])*(b-a))
            if not hits:raise ValueError('missing cross-section')
            hits=np.unique(np.round(hits,10),axis=0)
            folded+=len(hits)>1
            pair.append(hits[np.argmax(hits[:,1]) if take_max else np.argmin(hits[:,1])])
        gaps.append(pair[0][1]-pair[1][1]);depth.append(pair[0][2]-pair[1][2])
    return {'max_positive_gap':float(max(0.,max(gaps))),
            'max_overlap':float(max(0.,-min(gaps))),
            'rms_height_gap':float(np.sqrt(np.mean(np.square(gaps)))),
            'max_absolute_depth_difference':float(max(abs(np.asarray(depth)))),
            'folded_cross_sections':int(folded),'section_count':count,
            'canthus_trim_eye_widths':trim}


def source_quality(reference):
    """Measure original private contours in memory, before curve reduction."""
    neutral,faces=reference.evaluate({},0.)
    slot=next(s for s in reference.desc['slots'] if 'EyeWhite' in s['material'])
    loops=boundary_loops(faces[slot['tri_start']:slot['tri_start']+slot['tri_count']])
    result={}
    for side,label in ((1,'positive_x'),(-1,'negative_x')):
        candidates=[p for p in loops if np.all(neutral[p,0]*side>0)]
        if len(candidates)!=1:raise ValueError('ambiguous eye')
        upper,lower=split_lids(neutral,candidates[0],side)
        frame=frame_for(neutral,upper)
        result[label]=[]
        for w in (0.,.25,.5,.75,1.):
            v,_=reference.evaluate({},w)
            result[label].append({'weight':w,**closure_metrics(normalize(v[upper],frame),normalize(v[lower],frame))})
    return {'units':'neutral canthus distance = 1','measurement':'source polyline before coefficient reduction',
            'eyes':result}
