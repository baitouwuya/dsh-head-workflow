# SPDX-License-Identifier: GPL-3.0-or-later
"""Embedded GLB accessor decoding shared by the reference and pack adapters."""
import hashlib
import json
import struct
import numpy as np

class GLB:
    def __init__(self, raw):
        self.sha256 = hashlib.sha256(raw).hexdigest()
        if len(raw) < 20:
            raise ValueError('truncated GLB')
        magic, version, length = struct.unpack_from('<III',raw)
        if magic != 0x46546c67 or version != 2 or length != len(raw):
            raise ValueError('invalid GLB header')
        chunks, offset = {}, 12
        while offset < len(raw):
            if offset+8 > len(raw):raise ValueError('truncated chunk')
            size, kind = struct.unpack_from('<II',raw,offset)
            offset += 8
            if size % 4 or offset+size > len(raw) or kind in chunks:
                raise ValueError('invalid chunk')
            chunks[kind] = raw[offset:offset+size]
            offset += size
        if 0x4e4f534a not in chunks or 0x004e4942 not in chunks:
            raise ValueError('JSON and BIN chunks required')
        self.g = json.loads(chunks[0x4e4f534a])
        self.buffer = chunks[0x004e4942]
        buffers = self.g.get('buffers',[])
        if len(buffers)!=1 or 'uri' in buffers[0] or buffers[0]['byteLength'] > len(self.buffer):
            raise ValueError('one embedded buffer required')

    def _view(self, index, offset, count, components, dtype):
        if not isinstance(index,int) or not 0 <= index < len(self.g['bufferViews']):
            raise ValueError('invalid buffer view index')
        view = self.g['bufferViews'][index]
        if view.get('buffer',0) != 0:raise ValueError('external buffer')
        dtype = np.dtype(dtype)
        row = dtype.itemsize*components
        stride = view.get('byteStride',row)
        end = offset + (count-1)*stride+row if count else offset
        start = view.get('byteOffset',0)
        if count < 0 or offset < 0 or stride < row or end > view['byteLength'] or start < 0 or start+view['byteLength'] > len(self.buffer):
            raise ValueError('accessor outside buffer view')
        return np.ndarray((count,components),dtype=dtype,buffer=self.buffer,
                          offset=start+offset,strides=(stride,dtype.itemsize)).copy()

    def accessor(self,index):
        if not isinstance(index,int) or not 0 <= index < len(self.g['accessors']):
            raise ValueError('invalid accessor index')
        a = self.g['accessors'][index]
        dtypes = {5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}
        components = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        dtype = dtypes[a['componentType']]
        if 'bufferView' in a:
            out = self._view(a['bufferView'],a.get('byteOffset',0),a['count'],components,dtype)
        else:
            out = np.zeros((a['count'],components),dtype=dtype)
        sparse = a.get('sparse')
        if sparse:
            ids, values = sparse['indices'],sparse['values']
            if ids['componentType'] not in (5121,5123,5125):raise ValueError('invalid sparse indices')
            ix=self._view(ids['bufferView'],ids.get('byteOffset',0),sparse['count'],1,dtypes[ids['componentType']]).ravel()
            if np.any(ix >= a['count']) or np.any(ix[1:] <= ix[:-1]):raise ValueError('invalid sparse index range/order')
            out[ix]=self._view(values['bufferView'],values.get('byteOffset',0),sparse['count'],components,dtype)
        if a.get('normalized',False):
            if a['componentType'] == 5126:raise ValueError('normalized float accessor')
            info=np.iinfo(dtype)
            out=np.maximum(out.astype(float)/info.max,-1.)
        if not np.isfinite(out).all():raise ValueError('nonfinite accessor')
        return out
