# SPDX-License-Identifier: GPL-3.0-or-later
"""Invoked in host Blender by run-pd-reference.ps1; no scene operators."""
def run(addon_dir, packs, verify_fit=False):
    import bpy
    import numpy as np
    from _dsh_pd_reference_task.pd_adapter import PDReference
    from _dsh_pd_reference_task.fit import fit_pd, validate, fit_lid_profile
    before = (bpy.context.scene.as_pointer(), bpy.context.scene.frame_current,
              tuple((s.as_pointer(),len(s.objects)) for s in bpy.data.scenes),
              tuple(o.as_pointer() for o in bpy.context.selected_objects),
              len(bpy.data.meshes),len(bpy.data.materials),len(bpy.data.images))
    profiles, fits, checks = {}, {}, {}
    for label, path in packs.items():
        reference = PDReference(addon_dir,path)
        profiles[label] = validate(reference.extract())
        fits[label] = fit_lid_profile(profiles[label])
        if verify_fit:
            expected = {'Eye Size Y':.25,'Outer Eye Slant (Y)':-.2}
            target = reference.extract(expected)
            result = fit_pd(reference,target,{k:0. for k in expected},
                            {k:(-1.,1.) for k in expected},max_iterations=12,tolerance=2e-6)
            result['expected_parameters'] = expected
            result['parameter_max_error'] = max(abs(result['parameters'][k]-v) for k,v in expected.items())
            result['passed'] = result['accepted'] and result['parameter_max_error'] < .003
            checks[label] = result
    after = (bpy.context.scene.as_pointer(), bpy.context.scene.frame_current,
             tuple((s.as_pointer(),len(s.objects)) for s in bpy.data.scenes),
             tuple(o.as_pointer() for o in bpy.context.selected_objects),
             len(bpy.data.meshes),len(bpy.data.materials),len(bpy.data.images))
    return {'profiles':profiles,'fits':fits,'verification':{
        'blender_version':bpy.app.version_string,'scene_state_unchanged':before==after,
        'pd_parameter_recovery':checks}}
