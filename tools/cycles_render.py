"""Path-traced studio renders of the maze-car model with Blender Cycles.

Usage:
  /Applications/Blender.app/Contents/MacOS/Blender -b -P tools/cycles_render.py -- \
      --glb out/model/maze-car.glb --out out/renders --views hero,p02,p03,pcb --samples 160
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def get_args():
    p = argparse.ArgumentParser()
    p.add_argument('--glb', default='out/model/maze-car.glb')
    p.add_argument('--out', default='out/renders')
    p.add_argument('--views', default='hero,p02,p03,pcb')
    p.add_argument('--samples', type=int, default=160)
    p.add_argument('--res', default='1600x1200')
    return p.parse_args(argv())


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_car(path):
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    # world bounding box
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector((min(lo[i], w[i]) for i in range(3)))
            hi = Vector((max(hi[i], w[i]) for i in range(3)))
    return meshes, lo, hi


def material_cleanup():
    """Give the imported PBR materials a little more bite (roughness variation)."""
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        if not bsdf:
            continue
        # slightly lower specular on plastics, keep metals as-is
        try:
            if bsdf.inputs['Metallic'].default_value < 0.2:
                bsdf.inputs['Specular IOR Level'].default_value = 0.38
        except KeyError:
            pass


def studio(lo, hi):
    scn = bpy.context.scene
    center = (lo + hi) / 2
    size = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
    floor_z = lo.z

    # ---- floor (matte, catches shadows) ----
    bpy.ops.mesh.primitive_plane_add(size=size * 40, location=(center.x, center.y, floor_z))
    floor = bpy.context.object
    floor.name = 'StudioFloor'
    fm = bpy.data.materials.new('FloorMat')
    fm.use_nodes = True
    b = fm.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.012, 0.015, 0.018, 1)
    b.inputs['Roughness'].default_value = 0.5
    b.inputs['Specular IOR Level'].default_value = 0.35
    floor.data.materials.append(fm)

    # ---- curved backdrop (cyclorama) for soft gradients ----
    bpy.ops.mesh.primitive_plane_add(size=size * 60, location=(center.x, center.y - size * 8, floor_z))
    back = bpy.context.object
    back.name = 'Backdrop'
    back.rotation_euler = (math.radians(90), 0, 0)
    bm = bpy.data.materials.new('BackdropMat')
    bm.use_nodes = True
    nt = bm.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emit = nt.nodes.new('ShaderNodeEmission')
    tex = nt.nodes.new('ShaderNodeTexGradient')
    tex.gradient_type = 'SPHERICAL'
    mapn = nt.nodes.new('ShaderNodeMapping')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.15
    ramp.color_ramp.elements[0].color = (0.004, 0.006, 0.009, 1)
    ramp.color_ramp.elements[1].position = 0.62
    ramp.color_ramp.elements[1].color = (0.030, 0.040, 0.048, 1)
    mapn.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
    nt.links.new(coord.outputs['Generated'], mapn.inputs['Vector'])
    nt.links.new(mapn.outputs['Vector'], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], emit.inputs['Color'])
    emit.inputs['Strength'].default_value = 1.0
    nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])
    back.data.materials.append(bm)

    # ---- lights: big soft key, cool fill, rim ----
    def area(name, loc, rot, size_, energy, color=(1, 1, 1)):
        bpy.ops.object.light_add(type='AREA', location=loc)
        L = bpy.context.object
        L.name = name
        L.data.shape = 'RECTANGLE'
        L.data.size = size_
        L.data.size_y = size_ * 0.6
        L.data.energy = energy
        L.data.color = color
        L.rotation_euler = rot
        return L

    s = size
    # key: high, camera-left, warm
    k = area('Key', (center.x - s * 1.6, center.y - s * 1.1, floor_z + s * 1.5),
             (math.radians(52), 0, math.radians(-52)), s * 2.6, 900, (1.0, 0.94, 0.86))
    k.data.energy = 5.5
    # fill: cool, camera-right, low
    f = area('Fill', (center.x + s * 1.8, center.y - s * 0.9, floor_z + s * 0.7),
             (math.radians(74), 0, math.radians(58)), s * 2.2, 260, (0.80, 0.88, 1.0))
    f.data.energy = 3.2
    # rim: behind, cyan-ish
    r = area('Rim', (center.x + s * 0.6, center.y + s * 1.9, floor_z + s * 1.2),
             (math.radians(120), 0, math.radians(18)), s * 1.6, 700, (0.72, 0.92, 1.0))
    r.data.energy = 9

    # ---- world: very dark blue-grey ----
    world = bpy.data.worlds.new('StudioWorld')
    scn.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.020, 0.026, 0.032, 1)
    bg.inputs['Strength'].default_value = 0.12
    return center, size, floor_z


def camera_for(center, size, floor_z, az_deg, el_deg, dist_mul=2.05, target_z=0.45):
    scn = bpy.context.scene
    cam_data = bpy.data.cameras.new('Cam')
    cam = bpy.data.objects.new('Cam', cam_data)
    scn.collection.objects.link(cam)
    scn.camera = cam
    cam_data.lens = 74
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    d = size * dist_mul
    tgt = Vector((center.x, center.y, floor_z + size * target_z))
    cam.location = (
        tgt.x + d * math.cos(el) * math.cos(az),
        tgt.y + d * math.cos(el) * math.sin(az),
        tgt.z + d * math.sin(el),
    )
    direction = tgt - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return cam


def main():
    a = get_args()
    clear()
    car, lo, hi = import_car(a.glb)
    print(f'IMPORTED {len(car)} meshes  bbox {tuple(round(v,4) for v in lo)} .. {tuple(round(v,4) for v in hi)}')
    material_cleanup()
    center, size, floor_z = studio(lo, hi)

    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.cycles.device = 'GPU'
    scn.cycles.samples = a.samples
    scn.cycles.use_denoising = True
    try:
        scn.cycles.denoiser = 'OPENIMAGEDENOISE'
    except TypeError:
        pass
    scn.cycles.max_bounces = 10
    scn.cycles.transmission_bounces = 6
    scn.render.film_transparent = False
    scn.view_settings.exposure = -0.25
    try:
        scn.view_settings.view_transform = 'AgX'
        scn.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        scn.view_settings.view_transform = 'Filmic'
    w, h = (int(x) for x in a.res.lower().split('x'))
    scn.render.resolution_x = w
    scn.render.resolution_y = h
    scn.render.image_settings.file_format = 'PNG'
    scn.render.image_settings.color_mode = 'RGB'

    os.makedirs(a.out, exist_ok=True)
    views = {
        'hero': (148, 27, 2.95, 0.43),
        'p02': (58, 24, 2.7, 0.42),
        'p03': (34, 18, 2.6, 0.44),
        'pcb': (18, 62, 2.0, 0.50),
        'front': (0, 8, 3.2, 0.40),
    }
    for name in [v.strip() for v in a.views.split(',') if v.strip()]:
        az, el, dm, tz = views.get(name, views['hero'])
        camera_for(center, size, floor_z, az, el, dm, tz)
        scn.render.filepath = os.path.join(a.out, f'{name}.png')
        bpy.ops.render.render(write_still=True)
        print('RENDERED', scn.render.filepath)


if __name__ == '__main__':
    main()
