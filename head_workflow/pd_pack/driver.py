# SPDX-License-Identifier: GPL-3.0-or-later
"""Copied to generated pack/py/driver.py; requires the installed PD add-on."""
from parametric_deformation.core.interfaces import TemplateAdapter, MeshResult
from .runtime import Runtime


class VRMAdapter(TemplateAdapter):
    def load(self, pack, pack_dir):
        super().load(pack, pack_dir)
        self.runtime = Runtime(pack_dir)

    def evaluate(self, params, pose):
        return MeshResult(**self.runtime.evaluate(params, pose))

    def export_map(self):
        # Mapping metadata only. PD's export stage contains no exporter.
        return self.runtime.mapping

    def detach_shape_keys(self):
        return [{'name': exp['name'], 'params': {pid: 1.}}
                for pid, exp in self.runtime.expressions.items() if exp['binds']]
