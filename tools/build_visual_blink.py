# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Native source-only blink construction; visual motion, not numeric gates, accepts it."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np


def read_encoded_srgb(path):
    try:
        from PIL import Image
        with Image.open(path) as image:return np.asarray(image.convert('RGB')), 'Pillow encoded-sRGB decode'
    except ImportError:
        try:import bpy
        except ImportError as exc:raise RuntimeError('Use available Pillow or the supplied native Blender; do not install a VM runtime') from exc
        image=bpy.data.images.load(str(Path(path).resolve()),check_existing=False)
        try:
            image.colorspace_settings.name='Non-Color';width,height=image.size;pixels=np.empty(width*height*4,np.float32);image.pixels.foreach_get(pixels);return np.flipud(pixels.reshape(height,width,4)[:,:,:3]).copy(),'supplied Blender Non-Color decode'
        finally:bpy.data.images.remove(image)


def main():
    parser=argparse.ArgumentParser()
    for key in ['source','boundaries','probes','roles','configuration','source-image','repository','output']:parser.add_argument('--'+key,required=True)
    args=parser.parse_args();sys.path.insert(0,args.repository)
    from lab_recipes.source_band_margin import fit_source_band_margins
    from lab_recipes.visual_front_surface import build_visual_front_surfaces
    from lab_recipes.source_pigment_cover import add_source_pigment_covers
    from lab_recipes.original_lash_motion import build_original_lash_motion
    out=Path(args.output)
    if out.exists():raise ValueError('Output directory already exists; preserve prior evidence')
    paths={key:Path(getattr(args,key.replace('-','_'))) for key in ['source','boundaries','probes','roles','configuration','source-image']};hashes={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in paths.items()};source=dict(np.load(paths['source']));boundaries=dict(np.load(paths['boundaries']));probes=dict(np.load(paths['probes']));roles=json.loads(paths['roles'].read_text());cfg=json.loads(paths['configuration'].read_text());scale=float(np.ptp(source['vertices'][:,2]));pixels,decoder=read_encoded_srgb(paths['source-image'])
    fitted=fit_source_band_margins(source,boundaries,probes,roles,cfg,scale);surface=build_visual_front_surfaces(source,fitted['arrays'],probes,roles,cfg,scale);covered=add_source_pigment_covers(source,surface['arrays'],probes,roles,cfg,scale,pixels);motion=build_original_lash_motion(source,covered['arrays'],probes,roles,cfg,scale)
    if not all(hashlib.sha256(path.read_bytes()).hexdigest()==hashes[key] for key,path in paths.items()):raise ValueError('A native input file changed during construction')
    out.mkdir(parents=True,exist_ok=False);np.savez(out/'hoods.npz',**covered['arrays']);np.savez(out/'source-motion.npz',**motion['arrays']);specs=surface['patch_specs']+covered['patch_specs'];(out/'patch-specs.json').write_text(json.dumps(specs,indent=2));report={'source_scale':scale,'input_hashes':hashes,'input_files_unchanged':True,'image_decoder':decoder,'margin_fit':fitted['report'],'surface':surface['report'],'pigment_cover':covered['report'],'source_motion':motion['report'],'control_values':cfg['controls']['blink']['samples'],'acceptance':'The native Lab must export/reimport and judge its own front/oblique/profile close/reopen animation. Numerical diagnostics are not acceptance gates.','known_host_limitations':['Prior sampled host motion still showed pale sheet edges and poor profile shape.','The bounded upper-dominant host candidate showed newly source-skin-occluded wing vertices and a severed-wing appearance.','Fixed-boundary triangle-clearance projection produced pathological offsets; it is disabled by default, not silently called successful.'],'host_geometry_uploaded':False};(out/'report.json').write_text(json.dumps(report,indent=2));print('Built native-source blink candidate; exported/reimported native motion review required.')
if __name__=='__main__':main()
