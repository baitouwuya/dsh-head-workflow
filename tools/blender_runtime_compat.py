# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Resolve only Blender's renamed EEVEE identifier against live RNA choices."""

def resolve_render_engine(requested,available):
    available=set(available)
    if requested is None:requested='BLENDER_EEVEE_NEXT'
    if not isinstance(requested,str) or not requested:raise ValueError('A render engine identifier is required')
    if requested in available:return requested
    aliases={'BLENDER_EEVEE_NEXT':'BLENDER_EEVEE','BLENDER_EEVEE':'BLENDER_EEVEE_NEXT'}
    alias=aliases.get(requested)
    if alias in available:return alias
    raise ValueError('Requested render engine unavailable in this Blender runtime: '+requested+'; available='+str(sorted(available)))

def set_render_engine(scene,requested=None):
    choices=[item.identifier for item in scene.render.bl_rna.properties['engine'].enum_items]
    actual=resolve_render_engine(requested,choices);scene.render.engine=actual;return actual
