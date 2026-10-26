# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Acceptance is entirely profile-driven. Missing evidence never passes."""
import math

def _number(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def _index(rows,key):
    indexed={};duplicates=[]
    for row in rows if isinstance(rows,list) else []:
        if not isinstance(row,dict):continue
        try:label=key(row)
        except (KeyError,TypeError,ValueError):continue
        if label in indexed:duplicates.append(label)
        indexed[label]=row
    return indexed,duplicates

def aggregate_geometry(profile,rows):
    expected=['jaw_'+str(v) for v in profile['sampling']['jaw_degrees']]+['blink_'+str(v) for v in profile['sampling']['blink_weights']]
    indexed,duplicates=_index(rows,lambda r:r['pose']);missing=[p for p in expected if p not in indexed];coverage={'expected_poses':expected,'observed_poses':list(indexed),'missing_poses':missing,'duplicate_poses':duplicates,'observations':{}};metrics={}
    for metric,count_name,operation in [('projected_flips','projected_triangle_observations',sum),('quad_normal_max_degrees','quad_normal_observations',max),('adjacent_triangle_max_degrees','adjacent_triangle_observations',max)]:
        counts={p:indexed.get(p,{}).get(count_name) for p in expected};coverage['observations'][metric]=counts;values=[indexed.get(p,{}).get(metric) for p in expected]
        observed=bool(expected) and not missing and not duplicates and all(_number(n) and n>0 for n in counts.values()) and all(_number(v) and v>=0 for v in values)
        metrics[metric]=operation(values) if observed else None
    return {'metrics':metrics,'coverage':coverage}

def aggregate_semantic(profile,report):
    report=report if isinstance(report,dict) else {};expected_eyes=[e['label'] for e in profile['character']['eyes']];expected_mouth=[(float(d),float(v)) for d in profile['sampling']['jaw_degrees'] for v in profile['sampling']['mouth_views']]
    eyes,eye_duplicates=_index(report.get('eyes'),lambda r:r['side']);mouth,mouth_duplicates=_index(report.get('mouth'),lambda r:(float(r['degrees']),float(r['view_degrees'])))
    eye_missing=[e for e in expected_eyes if e not in eyes];mouth_missing=[list(k) for k in expected_mouth if k not in mouth]
    eye_counts={e:eyes.get(e,{}).get('rays') for e in expected_eyes};mouth_counts={str(k):mouth.get(k,{}).get('rays') for k in expected_mouth}
    coverage={'eyes':{'expected':expected_eyes,'rays':eye_counts,'missing':eye_missing,'duplicates':eye_duplicates},'mouth':{'expected':[list(k) for k in expected_mouth],'rays':mouth_counts,'missing':mouth_missing,'duplicates':[list(k) for k in mouth_duplicates]}}
    metrics={}
    for metric,indexed,expected,counts,missing,duplicates,field in [
        ('eye_exposed_or_empty',eyes,expected_eyes,eye_counts,eye_missing,eye_duplicates,'exposed_or_empty'),
        ('mouth_empty_or_posterior',mouth,expected_mouth,mouth_counts,mouth_missing,mouth_duplicates,'empty_or_posterior_hits'),
        ('mouth_unwanted_occluders',mouth,expected_mouth,mouth_counts,mouth_missing,mouth_duplicates,'unwanted_corridor_occluders')]:
        values=[indexed.get(k,{}).get(field) for k in expected];observed=bool(expected) and not missing and not duplicates and all(_number(n) and n>0 for n in counts.values()) and all(_number(v) and v>=0 for v in values)
        metrics[metric]=sum(values) if observed else None
    return {'metrics':metrics,'coverage':coverage}

def evaluate(profile,measurements,visual=None):
    rows=[]
    for name,rule in profile['audit']['rules'].items():
        value=measurements.get(name);valid=_number(value)
        passed=valid and {'max':lambda:value<=rule['value'],'min':lambda:value>=rule['value'],'eq':lambda:value==rule['value']}[rule['op']]()
        rows.append({'metric':name,'observed':value,'rule':rule,'passed':bool(passed),'missing':value is None})
    visual=visual or {};gates=[{'gate':name,'passed':visual.get(name) is True} for name in profile['audit']['visual_required']]
    return {'accepted':all(r['passed'] for r in rows+gates),'numeric_pass':all(r['passed'] for r in rows),'numeric':rows,'visual':gates}
