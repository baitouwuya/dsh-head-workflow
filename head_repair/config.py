# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Resolved inputs and immutable per-run settings; no Blender dependency."""
import copy,hashlib,json,math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path,overrides=()):
    base=json.loads(Path(path).read_text());p=copy.deepcopy(base);changes=[]
    for item in overrides:
        key,raw=item.split('=',1);value=json.loads(raw);parts=key.split('.');obj=p
        for part in parts[:-1]:obj=obj[part]
        if parts[-1] not in obj:raise ValueError('Unknown profile parameter: '+key)
        old=obj[parts[-1]];obj[parts[-1]]=value;changes.append({'parameter':key,'before':old,'after':value})
    if p['schema']!=1:raise ValueError('Unsupported profile schema')
    if p['geometry']['eyes']['rows']<2 or p['geometry']['eyes']['columns']<3:raise ValueError('Eye grid is too small')
    eye=p['geometry']['eyes']
    if eye['depth_mode'] not in ('thin_plate','linear_globe','shell_blend'):raise ValueError('Unknown eyelid depth method')
    if eye['row_sampling'] not in ('fraction','uniform_z'):raise ValueError('Unknown eyelid row method')
    if not math.isfinite(eye['z_step']) or eye['z_step']<=0:raise ValueError('z_step must be finite and positive')
    angles=p['geometry']['mouth']['poses']
    if sorted(set(angles))!=angles or angles[0]!=0:raise ValueError('Pose angles must increase from zero')
    if max(p['sampling']['jaw_degrees'])>angles[-1]:raise ValueError('Audit requests an unconstructed jaw pose')
    for rule in p['audit']['rules'].values():
        if rule['op'] not in ('min','max','eq') or not math.isfinite(rule['value']):raise ValueError('Invalid audit rule')
    return p,changes

def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
