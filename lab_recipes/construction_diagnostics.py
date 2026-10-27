# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Keep numeric construction findings truthful under visual acceptance mode."""
import numbers
import numpy as np

def generated_geometry_diagnostics(poses,faces,source_double_area_floor,interval_audit,*,diagnostics_only=False):
    p=np.asarray(poses,float);f=np.asarray(faces)
    if p.ndim!=3 or p.shape[2]!=3 or not len(p) or not np.isfinite(p).all() or f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or f.min()<0 or f.max()>=p.shape[1]:raise ValueError('Finite renderable geometry with valid indices required')
    if not isinstance(diagnostics_only,bool) or not np.isfinite(source_double_area_floor) or source_double_area_floor<0:raise ValueError('Invalid diagnostic policy or area floor')
    count=interval_audit.get('newly_collapsed_face_count')
    if isinstance(count,bool) or not isinstance(count,numbers.Integral) or count<0:raise ValueError('Actual nonnegative interval collapse count required')
    area=np.linalg.norm(np.cross(p[:,f[:,1]]-p[:,f[:,0]],p[:,f[:,2]]-p[:,f[:,0]]),axis=2)
    observations=int((area<=source_double_area_floor).sum());passed=observations==0 and count==0
    result={'generated_degenerate_observations':observations,'newly_collapsed_face_count':int(count),'numeric_diagnostics_pass':passed,'numeric_results_are_diagnostics':diagnostics_only,'source_double_area_floor':float(source_double_area_floor)}
    if not passed and not diagnostics_only:raise ValueError('Generated geometry numeric checks failed: '+str(result))
    return result
