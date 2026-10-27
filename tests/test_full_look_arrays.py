# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import unittest
import numpy as np
from full_look_arrays import validate_knots,sample_poses,sample_rotations,world_delta_to_local,rotated_loop_normals_local

class FullLookArrayTests(unittest.TestCase):
    def test_closed_reopened_sampling_is_reversible(self):
        poses=np.array([[[0.,0,0]],[[0,0,.5]],[[0,0,1]]]);knots=[0,.5,1]
        self.assertTrue(np.array_equal(sample_poses(poses,knots,0),poses[0]));self.assertTrue(np.allclose(sample_poses(poses,knots,.25),[[0,0,.25]]));self.assertTrue(np.array_equal(sample_poses(poses,knots,0),poses[0]))
    def test_nonidentity_object_world_delta_transform(self):
        matrix=np.array([[0,-2,0,3],[1,0,0,4],[0,0,.5,5],[0,0,0,1.]])
        delta=np.array([[.2,.4,.1]])
        local=world_delta_to_local(delta,matrix)
        self.assertTrue(np.allclose(local@matrix[:3,:3].T,delta))
    def test_source_zero_corner_normal_is_preserved(self):
        normal=np.array([[0.,0,0],[1,0,0]]);rot=np.broadcast_to(np.eye(3),(2,3,3))
        out=rotated_loop_normals_local(normal,[0,1],rot,np.eye(4));self.assertTrue(np.array_equal(out,normal))
    def test_world_rotation_on_local_normals_with_object_transform(self):
        matrix=np.diag([2.,1.,.5,1]);rot=np.array([[[0.,-1,0],[1,0,0],[0,0,1]]])
        out=rotated_loop_normals_local([[1.,0,0]],[0],rot,matrix)
        self.assertTrue(np.allclose(out,[[0,1,0]]))
    def test_rotation_interpolation_remains_orthogonal(self):
        rz=np.array([[0.,-1,0],[1,0,0],[0,0,1]]);r=sample_rotations(np.array([[np.eye(3)],[rz]]),[0,1],.5)
        self.assertTrue(np.allclose(r@r.transpose(0,2,1),np.eye(3)));self.assertTrue(np.allclose(np.linalg.det(r),1))
    def test_invalid_knots_rejected(self):
        for k in ([0,0,1],[0,.5,float('nan')],[False,True],[.1,1]):
            with self.assertRaises(ValueError):validate_knots(k)

if __name__=='__main__':unittest.main()
