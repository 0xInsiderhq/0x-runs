"""Realistic sky for the shots that see it (Dima 31.10): procedural stars + Mars from a public-domain mosaic.
Stars: generated here with numpy, no outside data (the NASA SVS Deep Star Maps licence could not be confirmed).
  thousands of points, power-law brightness, colours from blue-white to yellow-orange, a faint Milky Way band.
Mars: USGS Astrogeology "Mars Viking Global Color Mosaic 925m" (public domain), 1024 px sample of that product,
  shaded in the material: lit side / night side terminator and a thin bright atmosphere rim. No scene lights needed.
Used by intro_render.py on the stage 1 hook and ident scenes after they are built; their layout is not touched."""
import os, math
import numpy as np
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SKY = os.path.join(HERE, 'sky')
MARS_TEX = os.path.join(SKY, 'mars_viking_clrmosaic_global_1024.jpg')
STAR_COLORS = np.array([(0.62, 0.72, 1.0), (0.78, 0.85, 1.0), (0.95, 0.96, 1.0), (1.0, 0.96, 0.86),
                        (1.0, 0.88, 0.68), (1.0, 0.78, 0.52)])
STAR_P = np.array([0.08, 0.16, 0.26, 0.24, 0.17, 0.09])     # mostly white / pale yellow, a few blue and orange


def _splat(img, xs, ys, cols, sig):
    h, w, _ = img.shape
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            wgt = cols * np.exp(-(dx * dx + dy * dy) / (2 * sig * sig))
            np.add.at(img, ((ys + dy) % h, (xs + dx) % w), wgt)


def star_image(name, w, h, n, band, seed, equirect, mw=0.035):
    """float RGBA image: n stars + Milky Way. band(u, v) -> distance of a pixel from the galactic plane (0..1 units)."""
    path = os.path.join(SKY, f'{name}.exr')
    if os.path.exists(path):
        return bpy.data.images.load(path)
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.float32)
    # Milky Way: soft band, broken up by noise, with darker dust lanes
    v, u = np.mgrid[0:h, 0:w].astype(np.float32)
    d = band(u / w, v / h)
    glow = np.exp(-(d / 0.07) ** 2) * 0.55 + np.exp(-(d / 0.18) ** 2) * 0.25
    nz = np.zeros((h, w), np.float32)
    for k, amp in ((8, 0.5), (24, 0.3), (64, 0.2)):
        g = rng.standard_normal((k // 2 + 2, k + 2)).astype(np.float32)
        yi = np.linspace(0, k // 2, h); xi = np.linspace(0, k, w)
        y0 = yi.astype(int); x0 = xi.astype(int); fy = (yi - y0)[:, None]; fx = (xi - x0)[None, :]
        nz += amp * (g[y0][:, x0] * (1 - fy) * (1 - fx) + g[y0 + 1][:, x0] * fy * (1 - fx)
                     + g[y0][:, x0 + 1] * (1 - fy) * fx + g[y0 + 1][:, x0 + 1] * fy * fx)
    lanes = np.clip(1.0 - 0.8 * np.exp(-(d / 0.025) ** 2) * (nz > 0.1), 0.15, 1.0)
    img += (glow * np.clip(0.6 + 0.5 * nz, 0, 1.5) * lanes * mw)[..., None] * np.array([1.0, 0.94, 0.84], np.float32)
    # stars: uniform + extra ones packed along the band
    m = int(n * 0.65)
    if equirect:
        z = rng.uniform(-1, 1, m); phi = rng.uniform(0, 2 * np.pi, m)
        xs = (phi / (2 * np.pi) * w).astype(int); ys = ((np.arcsin(z) / np.pi + 0.5) * h).astype(int)
    else:
        xs = rng.integers(0, w, m); ys = rng.integers(0, h, m)
    cand_x = rng.integers(0, w, n * 4); cand_y = rng.integers(0, h, n * 4)
    keep = rng.uniform(0, 1, n * 4) < np.exp(-(band(cand_x / w, cand_y / h) / 0.08) ** 2)
    xs = np.concatenate([xs, cand_x[keep][:n - m]]); ys = np.concatenate([ys, cand_y[keep][:n - m]])
    k = len(xs)
    bright = np.clip((rng.pareto(1.4, k) + 1) * 0.02, 0, 6.0).astype(np.float32)     # few bright, very many faint
    cols = STAR_COLORS[rng.choice(len(STAR_COLORS), k, p=STAR_P)].astype(np.float32) * bright[:, None]
    small = bright < 0.15
    _splat(img, xs[small], ys[small], cols[small], 0.55)
    _splat(img, xs[~small], ys[~small], cols[~small], 0.95)
    rgba = np.concatenate([img, np.ones((h, w, 1), np.float32)], 2)[::-1]          # Blender rows go bottom-up
    im = bpy.data.images.new(name, w, h, float_buffer=True)
    im.pixels.foreach_set(rgba.ravel()); im.filepath_raw = path; im.file_format = 'OPEN_EXR'
    os.makedirs(SKY, exist_ok=True); im.save()
    print('SKY', name, k, 'stars', flush=True)
    return im


def sky_equirect():
    # galactic plane = a tilted great circle through the texture centre
    return star_image('stars_equirect_4k', 4096, 2048, 26000,
                      lambda u, v: np.abs((v - 0.5) - 0.18 * np.sin((u - 0.75) * 2 * np.pi)), 7, True, mw=0.3)


def sky_tile():
    return star_image('stars_tile_2k', 2048, 2048, 7000, lambda u, v: np.abs((v - 0.5) * 0.8 - (u - 0.5) * 0.45), 11, False)


def _n(nt, kind, **kw):
    node = nt.nodes.new(kind)
    for k, v in kw.items():
        setattr(node, k, v)
    return node


def mixc(nt, blend):
    """colour Mix node; Blender's Mix has same-named float/vector/colour sockets, so colour A/B/Result go by index"""
    m = nt.nodes.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = blend; m.inputs[0].default_value = 1.0
    return m


A_, B_, OUT_ = 6, 7, 2


def mars_material(name, view_dir, sun_dir, strength=3.0, face_lon=-70.0):
    """emission-only Mars: texture by object direction, lit side by sun_dir (object space), thin pale limb.
    face_lon: longitude turned toward the viewer (-70 = Valles Marineris)."""
    m = bpy.data.materials.new(name); nt = m.node_tree
    for nd in list(nt.nodes):
        if nd.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(nd)
    out = [nd for nd in nt.nodes if nd.type == 'OUTPUT_MATERIAL'][0]; L = nt.links.new
    tc = _n(nt, 'ShaderNodeTexCoord')
    nrm = _n(nt, 'ShaderNodeVectorMath', operation='NORMALIZE'); L(tc.outputs['Object'], nrm.inputs[0])
    sep = _n(nt, 'ShaderNodeSeparateXYZ'); L(nrm.outputs['Vector'], sep.inputs[0])
    at = _n(nt, 'ShaderNodeMath', operation='ARCTAN2'); L(sep.outputs['Y'], at.inputs[0]); L(sep.outputs['X'], at.inputs[1])
    vd = Vector(view_dir).normalized()
    off = (math.radians(face_lon) - math.atan2(vd.y, vd.x)) / (2 * math.pi) + 0.5
    u = _n(nt, 'ShaderNodeMath', operation='MULTIPLY_ADD'); L(at.outputs[0], u.inputs[0])
    u.inputs[1].default_value = 1 / (2 * math.pi); u.inputs[2].default_value = off
    asn = _n(nt, 'ShaderNodeMath', operation='ARCSINE'); L(sep.outputs['Z'], asn.inputs[0])
    v = _n(nt, 'ShaderNodeMath', operation='MULTIPLY_ADD'); L(asn.outputs[0], v.inputs[0])
    v.inputs[1].default_value = 1 / math.pi; v.inputs[2].default_value = 0.5
    uw = _n(nt, 'ShaderNodeMath', operation='FRACT'); L(u.outputs[0], uw.inputs[0])
    uv = _n(nt, 'ShaderNodeCombineXYZ'); L(uw.outputs[0], uv.inputs['X']); L(v.outputs[0], uv.inputs['Y'])
    tex = _n(nt, 'ShaderNodeTexImage', extension='EXTEND'); tex.image = bpy.data.images.load(MARS_TEX)
    L(uv.outputs['Vector'], tex.inputs['Vector'])
    # day side: smooth terminator
    dot = _n(nt, 'ShaderNodeVectorMath', operation='DOT_PRODUCT'); L(nrm.outputs['Vector'], dot.inputs[0])
    dot.inputs[1].default_value = tuple(Vector(sun_dir).normalized())
    day = _n(nt, 'ShaderNodeMapRange'); day.inputs['From Min'].default_value = -0.08; day.inputs['From Max'].default_value = 0.35
    L(dot.outputs['Value'], day.inputs['Value'])
    lit = mixc(nt, 'MULTIPLY')
    L(tex.outputs['Color'], lit.inputs[A_]); L(day.outputs['Result'], lit.inputs[B_])
    # thin pale limb on the lit side
    lw = _n(nt, 'ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    rim = _n(nt, 'ShaderNodeMath', operation='POWER'); L(lw.outputs['Facing'], rim.inputs[0]); rim.inputs[1].default_value = 7.0
    rimlit = _n(nt, 'ShaderNodeMath', operation='MULTIPLY'); L(rim.outputs[0], rimlit.inputs[0])
    dayr = _n(nt, 'ShaderNodeMapRange'); dayr.inputs['From Min'].default_value = -0.3; dayr.inputs['From Max'].default_value = 0.6
    L(dot.outputs['Value'], dayr.inputs['Value']); L(dayr.outputs['Result'], rimlit.inputs[1])
    haze = mixc(nt, 'ADD')
    L(lit.outputs[OUT_], haze.inputs[A_])
    rimc = mixc(nt, 'MULTIPLY')
    L(rimlit.outputs[0], rimc.inputs[A_]); rimc.inputs[B_].default_value = (0.6, 0.5, 0.42, 1)
    L(rimc.outputs[OUT_], haze.inputs[B_])
    em = _n(nt, 'ShaderNodeEmission'); em.inputs['Strength'].default_value = strength
    L(haze.outputs[OUT_], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    return m


def smooth_sphere(ob):
    for p in ob.data.polygons:
        p.use_smooth = True


# ------------------------------------------------------------------ per scene
def upgrade_hook():
    """shaft-bottom hook (shots.s1_hook + intro.hook): star spheres -> star map seen by camera rays only,
    so the shaft keeps its approved blue fill light; Mars gets the real surface."""
    for ob in [o for o in bpy.data.objects if o.name.startswith('star')]:
        bpy.data.objects.remove(ob, do_unlink=True)
    w = bpy.context.scene.world; nt = w.node_tree; L = nt.links.new
    bg = [nd for nd in nt.nodes if nd.type == 'BACKGROUND'][0]
    out = [nd for nd in nt.nodes if nd.type == 'OUTPUT_WORLD'][0]
    tc = _n(nt, 'ShaderNodeTexCoord')
    mp = _n(nt, 'ShaderNodeMapping'); mp.inputs['Rotation'].default_value = (math.radians(-90), 0, math.radians(20))  # zenith -> texture equator
    L(tc.outputs['Generated'], mp.inputs['Vector'])
    env = _n(nt, 'ShaderNodeTexEnvironment'); env.image = sky_equirect(); L(mp.outputs['Vector'], env.inputs['Vector'])
    stars = _n(nt, 'ShaderNodeBackground'); stars.inputs['Strength'].default_value = 1.0
    add = mixc(nt, 'ADD')
    gsc = mixc(nt, 'MULTIPLY')
    L(bg.inputs['Color'].links[0].from_socket, gsc.inputs[A_]) if bg.inputs['Color'].is_linked else None
    gsc.inputs[B_].default_value = (bg.inputs['Strength'].default_value,) * 3 + (1,)
    L(gsc.outputs[OUT_], add.inputs[A_]); L(env.outputs['Color'], add.inputs[B_])
    L(add.outputs[OUT_], stars.inputs['Color'])
    lp = _n(nt, 'ShaderNodeLightPath'); mix = _n(nt, 'ShaderNodeMixShader')
    L(lp.outputs['Is Camera Ray'], mix.inputs['Fac']); L(bg.outputs[0], mix.inputs[1]); L(stars.outputs[0], mix.inputs[2])
    L(mix.outputs[0], out.inputs['Surface'])
    mars = bpy.data.objects['mars']; cam = bpy.context.scene.camera
    vd = cam.location - mars.location
    sun = (vd.normalized() * 0.5 + Vector((0.9, 0.3, 0.0))).normalized()     # about half lit: a clear terminator
    smooth_sphere(mars)
    mars.data.materials.clear(); mars.data.materials.append(mars_material('mars_real', vd, sun, strength=1.5))


def upgrade_ident():
    """crown-cap ident (intro.ident2): the 80 star dots -> a star tile with a Milky Way on the portal,
    Mars sphere -> real surface, terminator and rim; its red halo dimmed. Positions and sizes unchanged."""
    import re
    for ob in [o for o in bpy.data.objects if re.fullmatch(r'st\d+', o.name)]:
        bpy.data.objects.remove(ob, do_unlink=True)
    sm = bpy.data.materials['sky_m']; nt = sm.node_tree; L = nt.links.new
    em = [nd for nd in nt.nodes if nd.type == 'EMISSION'][0]
    ramp_out = em.inputs['Color'].links[0].from_socket
    tc = [nd for nd in nt.nodes if nd.type == 'TEX_COORD'][0]
    sep = _n(nt, 'ShaderNodeSeparateXYZ'); L(tc.outputs['Object'], sep.inputs[0])
    uu = _n(nt, 'ShaderNodeMapRange'); uu.inputs['From Min'].default_value = -1.7; uu.inputs['From Max'].default_value = 1.7
    vv = _n(nt, 'ShaderNodeMapRange'); vv.inputs['From Min'].default_value = 0.9 - 1.7; vv.inputs['From Max'].default_value = 0.9 + 1.7
    L(sep.outputs['X'], uu.inputs['Value']); L(sep.outputs['Z'], vv.inputs['Value'])
    uv = _n(nt, 'ShaderNodeCombineXYZ'); L(uu.outputs['Result'], uv.inputs['X']); L(vv.outputs['Result'], uv.inputs['Y'])
    tex = _n(nt, 'ShaderNodeTexImage'); tex.image = sky_tile(); L(uv.outputs['Vector'], tex.inputs['Vector'])
    k = mixc(nt, 'MULTIPLY')
    L(tex.outputs['Color'], k.inputs[A_]); k.inputs[B_].default_value = (3.0, 3.0, 3.0, 1)
    add = mixc(nt, 'ADD')
    L(ramp_out, add.inputs[A_]); L(k.outputs[OUT_], add.inputs[B_]); L(add.outputs[OUT_], em.inputs['Color'])
    mars = bpy.data.objects['mars']; cam = bpy.context.scene.camera
    vd = cam.location - mars.location
    sun = (vd.normalized() + Vector((-1.1, 0.0, 0.5))).normalized()     # lit from the upper left, shadow on the right
    smooth_sphere(mars)
    mars.data.materials.clear(); mars.data.materials.append(mars_material('mars_real', vd, sun, strength=3.5))
    # the approved logo's visible Mars disc is its red halo sphere (r 0.30, same centre); the real Mars takes
    # its place at that size, so the layout stays as it was
    halo = bpy.data.objects.get('mars_halo')
    if halo:
        halo.hide_render = True
        s = halo.dimensions.x / mars.dimensions.x
        mars.scale = (s, s, s); mars.location.x, mars.location.z = halo.location.x, halo.location.z
