import os
"""Worm Space Program, shared asset library (Blender 5.2, bpy).
Units: 1 BU = 3 cm. Worm length ~3.3 BU, radius ~0.13 BU.
All geometry is procedural so every shot rebuilds from code.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise

# ---------------------------------------------------------------- scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = 'CYCLES'
    s.cycles.device = 'CPU'
    s.cycles.use_denoising = True
    s.cycles.denoiser = 'OPENIMAGEDENOISE'
    s.view_settings.view_transform = 'AgX'
    try:
        s.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    s.render.fps = 24
    return s

def render_settings(w=960, h=540, samples=48, bounces=6):
    s = bpy.context.scene
    s.render.resolution_x, s.render.resolution_y = w, h
    s.render.resolution_percentage = 100
    s.cycles.samples = samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.03
    s.cycles.max_bounces = bounces
    s.cycles.diffuse_bounces = 3
    s.cycles.glossy_bounces = 3
    s.cycles.transmission_bounces = 4
    s.cycles.blur_glossy = 1.0
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.render.image_settings.file_format = 'PNG'

def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj

def mesh_obj(name, verts, faces, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    return link(ob)

def subsurf(ob, lv=1, rlv=2):
    m = ob.modifiers.new('sub', 'SUBSURF')
    m.levels, m.render_levels = lv, rlv
    return m

# ---------------------------------------------------------------- materials
def _bsdf(mat):
    nt = mat.node_tree
    return nt, nt.nodes.get('Principled BSDF')

def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m

def set_inp(node, key, val):
    if key in node.inputs:
        node.inputs[key].default_value = val

def mat_worm(name='worm', body=(0.30, 0.085, 0.06), band=(0.62, 0.30, 0.26), pale=0.0):
    m = new_mat(name)
    nt, b = _bsdf(m)
    nodes, links = nt.nodes, nt.links
    attr = nodes.new('ShaderNodeAttribute'); attr.attribute_name = 'band'
    mix = nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    c_body = tuple(c + (0.55 - c) * pale for c in body)
    c_band = tuple(c + (0.75 - c) * pale for c in band)
    mix.inputs[6].default_value = (*c_body, 1)
    mix.inputs[7].default_value = (*c_band, 1)
    links.new(attr.outputs['Fac'], mix.inputs[0])
    # subtle mottling
    nz = nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 18.0
    mix2 = nodes.new('ShaderNodeMix'); mix2.data_type = 'RGBA'; mix2.blend_type = 'MULTIPLY'
    mix2.inputs[0].default_value = 0.35
    links.new(mix.outputs[2], mix2.inputs[6])
    links.new(nz.outputs['Color'], mix2.inputs[7])
    links.new(mix2.outputs[2], b.inputs['Base Color'])
    set_inp(b, 'Subsurface Weight', 0.55)
    set_inp(b, 'Subsurface Radius', (1.0, 0.35, 0.22))
    set_inp(b, 'Subsurface Scale', 0.06)
    set_inp(b, 'Roughness', 0.32)
    set_inp(b, 'Coat Weight', 0.65)
    set_inp(b, 'Coat Roughness', 0.06)
    set_inp(b, 'Specular IOR Level', 0.55)
    # fine ring grooves already in geometry; add micro bump for wetness
    bump = nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08
    nz2 = nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 90.0
    links.new(nz2.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def mat_metal(name, color=(0.78, 0.78, 0.76), rough=0.28, scratch=0.25):
    m = new_mat(name)
    nt, b = _bsdf(m)
    nodes, links = nt.nodes, nt.links
    set_inp(b, 'Base Color', (*color, 1))
    set_inp(b, 'Metallic', 1.0)
    nz = nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 40.0
    nz.inputs['Detail'].default_value = 8.0
    ramp = nodes.new('ShaderNodeMapRange')
    ramp.inputs['From Min'].default_value = 0.35; ramp.inputs['From Max'].default_value = 0.75
    ramp.inputs['To Min'].default_value = rough * 0.85; ramp.inputs['To Max'].default_value = rough + scratch * 0.4
    links.new(nz.outputs['Fac'], ramp.inputs['Value'])
    links.new(ramp.outputs['Result'], b.inputs['Roughness'])
    # scratches: stretched noise as bump
    tc = nodes.new('ShaderNodeTexCoord'); mp = nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1.0, 1.0, 30.0)
    links.new(tc.outputs['Object'], mp.inputs['Vector'])
    nz2 = nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 25.0
    links.new(mp.outputs['Vector'], nz2.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.025
    links.new(nz2.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def mat_dimpled(name='thimble', color=(0.80, 0.62, 0.35)):
    m = new_mat(name)
    nt, b = _bsdf(m)
    nodes, links = nt.nodes, nt.links
    set_inp(b, 'Base Color', (*color, 1))
    set_inp(b, 'Metallic', 1.0)
    set_inp(b, 'Roughness', 0.3)
    vor = nodes.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 34.0
    vor.feature = 'F1'
    tc = nodes.new('ShaderNodeTexCoord')
    links.new(tc.outputs['Object'], vor.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.45
    links.new(vor.outputs['Distance'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def mat_simple(name, color, rough=0.5, metal=0.0, sss=0.0, emit=None, emit_strength=0.0, coat=0.0):
    m = new_mat(name)
    nt, b = _bsdf(m)
    set_inp(b, 'Base Color', (*color, 1))
    set_inp(b, 'Roughness', rough)
    set_inp(b, 'Metallic', metal)
    set_inp(b, 'Subsurface Weight', sss)
    set_inp(b, 'Coat Weight', coat)
    if emit:
        set_inp(b, 'Emission Color', (*emit, 1))
        set_inp(b, 'Emission Strength', emit_strength)
    return m

def mat_emit(name, color, strength):
    m = new_mat(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type == 'BSDF_PRINCIPLED':
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color, 1)
    em.inputs['Strength'].default_value = strength
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m

def mat_soil(name='soil', base=(0.11, 0.065, 0.04), layered=True, scale=1.0):
    m = new_mat(name)
    nt, b = _bsdf(m)
    nodes, links = nt.nodes, nt.links
    tc = nodes.new('ShaderNodeTexCoord')
    # layered strata along Z with wobble
    nz = nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.5 / scale
    nz.inputs['Detail'].default_value = 6
    links.new(tc.outputs['Object'], nz.inputs['Vector'])
    sep = nodes.new('ShaderNodeSeparateXYZ'); links.new(tc.outputs['Object'], sep.inputs[0])
    add = nodes.new('ShaderNodeMath'); add.operation = 'MULTIPLY_ADD'
    add.inputs[1].default_value = 0.6
    links.new(nz.outputs['Fac'], add.inputs[0]); links.new(sep.outputs['Z'], add.inputs[2])
    wave = nodes.new('ShaderNodeMath'); wave.operation = 'SINE'
    mul = nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 2.2 / scale
    links.new(add.outputs[0], mul.inputs[0]); links.new(mul.outputs[0], wave.inputs[0])
    ramp = nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (*base, 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (base[0] * 2.6, base[1] * 2.2, base[2] * 1.9, 1) if layered else (base[0] * 1.5, base[1] * 1.4, base[2] * 1.3, 1)
    e = cr.elements.new(0.55); e.color = (base[0] * 0.65, base[1] * 0.6, base[2] * 0.6, 1)
    mr = nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -1; mr.inputs['From Max'].default_value = 1
    links.new(wave.outputs[0], mr.inputs['Value'])
    # grain
    nz2 = nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 60.0 / scale
    nz2.inputs['Detail'].default_value = 10
    links.new(tc.outputs['Object'], nz2.inputs['Vector'])
    mixf = nodes.new('ShaderNodeMath'); mixf.operation = 'MULTIPLY_ADD'
    mixf.inputs[1].default_value = 0.25
    links.new(nz2.outputs['Fac'], mixf.inputs[0]); links.new(mr.outputs['Result'], mixf.inputs[2])
    links.new(mixf.outputs[0], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    set_inp(b, 'Roughness', 0.92)
    bump = nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.6
    links.new(nz2.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def mat_paper(name, img_path):
    m = new_mat(name)
    nt, b = _bsdf(m)
    nodes, links = nt.nodes, nt.links
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(img_path)
    links.new(tex.outputs['Color'], b.inputs['Base Color'])
    links.new(tex.outputs['Alpha'], b.inputs['Alpha'])
    set_inp(b, 'Roughness', 0.85)
    set_inp(b, 'Subsurface Weight', 0.15)
    return m

def world_night(strength=0.35, stars=True):
    w = bpy.data.worlds.new('night')
    bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree; nodes, links = nt.nodes, nt.links
    bg = nodes.get('Background') or nodes.new('ShaderNodeBackground')
    out = [n for n in nodes if n.type == 'OUTPUT_WORLD'][0]
    tc = nodes.new('ShaderNodeTexCoord')
    grad = nodes.new('ShaderNodeSeparateXYZ'); links.new(tc.outputs['Generated'], grad.inputs[0])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.010, 0.016, 0.045, 1)
    ramp.color_ramp.elements[1].color = (0.002, 0.004, 0.014, 1)
    links.new(grad.outputs['Z'], ramp.inputs['Fac'])
    col = ramp.outputs['Color']
    if stars:
        vor = nodes.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 420.0
        links.new(tc.outputs['Generated'], vor.inputs['Vector'])
        mr = nodes.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = 0.06; mr.inputs['From Max'].default_value = 0.0
        mr.inputs['To Min'].default_value = 0.0; mr.inputs['To Max'].default_value = 3.0
        links.new(vor.outputs['Distance'], mr.inputs['Value'])
        pw = nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 6.0
        links.new(mr.outputs['Result'], pw.inputs[0])
        add = nodes.new('ShaderNodeMix'); add.data_type = 'RGBA'; add.blend_type = 'ADD'
        add.inputs[0].default_value = 1.0
        links.new(col, add.inputs[6])
        cr = nodes.new('ShaderNodeCombineColor')
        links.new(pw.outputs[0], cr.inputs[0]); links.new(pw.outputs[0], cr.inputs[1]); links.new(pw.outputs[0], cr.inputs[2])
        links.new(cr.outputs[0], add.inputs[7])
        col = add.outputs[2]
    links.new(col, bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    links.new(bg.outputs[0], out.inputs['Surface'])
    return w

# ---------------------------------------------------------------- curves / tubes
def catmull(pts, n):
    pts = [Vector(p) for p in pts]
    P = [pts[0] + (pts[0] - pts[1])] + pts + [pts[-1] + (pts[-1] - pts[-2])]
    out = []
    segs = len(pts) - 1
    for i in range(segs):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1].copy())
    return out

def resample(pts, n):
    d = [0.0]
    for i in range(1, len(pts)):
        d.append(d[-1] + (pts[i] - pts[i - 1]).length)
    L = d[-1]
    out, j = [], 0
    for k in range(n):
        s = L * k / (n - 1)
        while j < len(d) - 2 and d[j + 1] < s:
            j += 1
        seg = d[j + 1] - d[j]
        t = 0 if seg == 0 else (s - d[j]) / seg
        out.append(pts[j].lerp(pts[j + 1], t))
    return out, L

def frames(pts, up=Vector((0, 0, 1))):
    T = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, len(pts) - 1)]
        T.append((b - a).normalized())
    N = []
    n0 = up - up.dot(T[0]) * T[0]
    if n0.length < 1e-4:
        n0 = Vector((1, 0, 0)) - T[0].x * T[0]
    n0.normalize(); N.append(n0)
    for i in range(1, len(pts)):
        v = T[i - 1].cross(T[i])
        if v.length < 1e-8:
            N.append(N[-1].copy()); continue
        ang = math.acos(max(-1, min(1, T[i - 1].dot(T[i]))))
        N.append((Matrix.Rotation(ang, 3, v.normalized()) @ N[-1]).normalized())
    B = [T[i].cross(N[i]) for i in range(len(pts))]
    return T, N, B

def tube(name, ctrl, radius_fn, ring=28, samples=220, attr_fn=None, flatten=0.0):
    raw = catmull(ctrl, 12)
    pts, L = resample(raw, samples)
    T, N, B = frames(pts)
    verts, faces, attr = [], [], []
    for i, p in enumerate(pts):
        u = i / (samples - 1)
        r = radius_fn(u, L)
        for k in range(ring):
            a = 2 * math.pi * k / ring
            ca, sa = math.cos(a), math.sin(a)
            # slight belly flattening (N points 'up' at start)
            fl = 1.0 - flatten * max(0.0, -ca)
            verts.append(p + (N[i] * ca * fl + B[i] * sa) * r)
            if attr_fn:
                attr.append(attr_fn(u))
    for i in range(samples - 1):
        for k in range(ring):
            a = i * ring + k; b = i * ring + (k + 1) % ring
            faces.append((a, b, b + ring, a + ring))
    # caps
    c0 = len(verts); verts.append(pts[0] - T[0] * 0.0)
    c1 = len(verts); verts.append(pts[-1])
    if attr_fn:
        attr += [attr_fn(0.0), attr_fn(1.0)]
    for k in range(ring):
        faces.append((c0, (k + 1) % ring, k))
        base = (samples - 1) * ring
        faces.append((c1, base + k, base + (k + 1) % ring))
    ob = mesh_obj(name, verts, faces)
    if attr_fn:
        me = ob.data
        ca_ = me.color_attributes.new('band', 'FLOAT_COLOR', 'POINT')
        for i, v in enumerate(attr):
            ca_.data[i].color = (v, v, v, 1)
    return ob, pts, T

# ---------------------------------------------------------------- worm
def worm(name, ctrl, R=0.11, segs=96, band=(0.70, 0.79), mat=None, head_taper=0.42, flatten=0.12, groove=0.045):
    def radius(u, L):
        # u: 0 tail .. 1 head
        r = R
        r *= 0.35 + 0.65 * min(1.0, u / 0.10) ** 0.6          # tail taper
        if u > 0.80:
            r *= 1.0 - (1 - head_taper) * ((u - 0.80) / 0.20) ** 1.4
        # rounded tips
        e = min(u, 1 - u)
        if e < 0.018:
            r *= math.sqrt(max(0.0, 1 - ((0.018 - e) / 0.018) ** 2))
        # clitellum swelling
        b0, b1 = band
        if b0 < u < b1:
            r *= 1.0 + 0.10 * math.sin(math.pi * (u - b0) / (b1 - b0))
        # annulation grooves
        f = (u * segs) % 1.0
        d = min(f, 1 - f)
        r *= 1.0 - groove * math.exp(-(d / 0.12) ** 2)
        return r
    def bandf(u):
        b0, b1 = band
        if b0 < u < b1:
            return math.sin(math.pi * (u - b0) / (b1 - b0)) ** 0.5
        return 0.0
    ob, pts, T = tube(name, ctrl, radius, ring=30, samples=260, attr_fn=bandf, flatten=flatten)
    ob.data.materials.append(mat or mat_worm())
    subsurf(ob, 1, 1)
    return ob, pts, T

# ---------------------------------------------------------------- lathe props
def lathe(name, profile, seg=48, ang_fn=None, cap_top=False, cap_bottom=False):
    verts, faces = [], []
    nr = len(profile)
    for j in range(seg):
        a = 2 * math.pi * j / seg
        for i, (r, z) in enumerate(profile):
            rr = r * (ang_fn(a, i / max(1, nr - 1)) if ang_fn else 1.0)
            verts.append((rr * math.cos(a), rr * math.sin(a), z))
    for j in range(seg):
        j2 = (j + 1) % seg
        for i in range(nr - 1):
            faces.append((j * nr + i, j2 * nr + i, j2 * nr + i + 1, j * nr + i + 1))
    if cap_bottom:
        c = len(verts); verts.append((0, 0, profile[0][1]))
        for j in range(seg):
            faces.append((c, ((j + 1) % seg) * nr, j * nr))
    if cap_top:
        c = len(verts); verts.append((0, 0, profile[-1][1]))
        for j in range(seg):
            faces.append((c, j * nr + nr - 1, ((j + 1) % seg) * nr + nr - 1))
    return mesh_obj(name, verts, faces)

def thimble(name='thimble', h=0.30, r=0.145):
    prof = [(r * 1.08, 0.0), (r * 1.10, 0.02), (r * 1.08, 0.045), (r * 1.0, 0.06)]
    for k in range(1, 9):
        z = 0.06 + (h * 0.78 - 0.06) * k / 8
        prof.append((r * (1.0 - 0.06 * k / 8), z))
    for k in range(1, 8):
        a = (math.pi / 2) * k / 7
        prof.append((r * 0.94 * math.cos(a), h * 0.78 + h * 0.22 * math.sin(a)))
    ob = lathe(name, prof, seg=56)
    sol = ob.modifiers.new('solid', 'SOLIDIFY'); sol.thickness = 0.012
    subsurf(ob, 1, 2)
    ob.data.materials.append(mat_dimpled())
    return ob

def tin_can(name='can', h=3.1, r=1.0, mat=None):
    prof = [(r * 1.02, 0.0), (r * 1.04, 0.03), (r * 1.0, 0.07)]
    n = 60
    for i in range(1, n):
        z = 0.07 + (h - 0.14) * i / n
        rib = 0.012 * math.sin(i / n * math.pi * 26) if 0.12 < i / n < 0.88 else 0.0
        prof.append((r * (1.0 + rib), z))
    prof += [(r * 1.0, h - 0.07), (r * 1.04, h - 0.03), (r * 1.02, h)]
    ob = lathe(name, prof, seg=72, cap_bottom=True)
    sol = ob.modifiers.new('solid', 'SOLIDIFY'); sol.thickness = 0.02
    ob.data.materials.append(mat or mat_metal('tin', (0.80, 0.80, 0.78), 0.22))
    return ob

def bottle_cap(name='cap', color=(0.75, 0.08, 0.06), r=0.48, h=0.2):
    prof = [(r * 0.98, 0.0), (r, 0.02), (r, h * 0.9), (r * 0.96, h), (r * 0.5, h * 1.02), (0.0, h * 1.02)]
    def crimp(a, t):
        return 1.0 + (0.035 * math.cos(21 * a) if t < 0.5 else 0.0)
    ob = lathe(name, prof, seg=126, ang_fn=crimp)
    sol = ob.modifiers.new('solid', 'SOLIDIFY'); sol.thickness = 0.015
    mat = new_mat(name + '_m')
    nt, b = _bsdf(mat)
    set_inp(b, 'Base Color', (*color, 1)); set_inp(b, 'Metallic', 0.85); set_inp(b, 'Roughness', 0.3)
    set_inp(b, 'Coat Weight', 0.6)
    ob.data.materials.append(mat)
    return ob

def matchstick(name='match', L=1.45, t=0.09, burnt=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= t; v.co.y *= t; v.co.z = (v.co.z + 0.5) * L
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    stick = link(bpy.data.objects.new(name, me))
    bev = stick.modifiers.new('bev', 'BEVEL'); bev.width = 0.008; bev.segments = 2
    wood = mat_simple(name + '_wood', (0.72, 0.52, 0.30) if not burnt else (0.06, 0.04, 0.03), 0.7)
    stick.data.materials.append(wood)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0)
    for v in bm.verts:
        v.co.x *= t * 0.85; v.co.y *= t * 0.85; v.co.z = v.co.z * t * 1.6 + L
    me2 = bpy.data.meshes.new(name + '_head'); bm.to_mesh(me2); bm.free()
    head = link(bpy.data.objects.new(name + '_head', me2))
    for p in head.data.polygons:
        p.use_smooth = True
    head.data.materials.append(mat_simple(name + '_hm', (0.55, 0.05, 0.03) if not burnt else (0.03, 0.03, 0.03), 0.6))
    head.parent = stick
    return stick

def foil_cone(name='foil', r=1.02, h=1.5, seed=3):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=48, radius1=r, radius2=0.03, depth=h)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    random.seed(seed)
    for v in bm.verts:
        n = noise.noise(v.co * 3.1 + Vector((seed, 0, 0)))
        n2 = noise.noise(v.co * 9.0)
        rad = Vector((v.co.x, v.co.y, 0))
        if rad.length > 1e-4:
            v.co += rad.normalized() * (0.06 * n + 0.025 * n2)
        v.co.z += h / 2 + 0.02 * n2
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me))
    for p in ob.data.polygons:
        p.use_smooth = False
    ob.data.materials.append(mat_metal('foil_m', (0.86, 0.86, 0.88), 0.12, 0.2))
    return ob

def paperclip(name='clip', s=0.6):
    pts = [(-0.3, 0, 0), (0.9, 0, 0), (1.0, 0.08, 0), (0.9, 0.16, 0), (-0.15, 0.16, 0), (-0.22, 0.10, 0), (-0.15, 0.04, 0), (0.75, 0.04, 0)]
    pts = [Vector(p) * s for p in pts]
    ob, _, _ = tube(name, pts, lambda u, L: 0.018, ring=10, samples=120)
    ob.data.materials.append(mat_metal('clip_m', (0.7, 0.72, 0.75), 0.2, 0.1))
    return ob

def rock(name, size=0.2, seed=0, mat=None, flat=0.7):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=size)
    off = Vector((seed * 1.7, seed * 0.3, seed * 2.1))
    for v in bm.verts:
        n = noise.noise(v.co / size * 0.9 + off)
        v.co *= 1.0 + 0.28 * n
        v.co.z *= flat
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me))
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.materials.append(mat or mat_simple('rock_m', (0.32, 0.29, 0.26), 0.8))
    return ob

def firefly(name, loc, energy=0.8, color=(1.0, 0.78, 0.35), size=0.035):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=size)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc
    ob.data.materials.append(mat_emit(name + '_e', color, 7.0))
    ob.visible_shadow = False
    L = bpy.data.lights.new(name + '_L', 'POINT'); L.energy = energy; L.color = color
    L.shadow_soft_size = 0.05
    lo = link(bpy.data.objects.new(name + '_L', L)); lo.location = loc
    return ob, lo

def area_light(name, loc, rot, energy, size=2.0, color=(1, 1, 1)):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.size = size; L.color = color
    ob = link(bpy.data.objects.new(name, L)); ob.location = loc; ob.rotation_euler = rot
    return ob

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

def camera(loc, target, lens=90, fstop=2.8, focus=None, shift=(0, 0)):
    cd = bpy.data.cameras.new('cam'); cd.lens = lens
    cd.shift_x, cd.shift_y = shift
    cd.clip_start = 0.02; cd.clip_end = 400
    cam = link(bpy.data.objects.new('cam', cd)); cam.location = loc
    look_at(cam, target)
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = fstop
    cd.dof.focus_distance = focus if focus else (Vector(target) - Vector(loc)).length
    bpy.context.scene.camera = cam
    return cam

# ---------------------------------------------------------------- set pieces
def soil_box(name, size, loc, mat):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc
    ob.data.materials.append(mat)
    return ob

def displaced_plane(name, sx, sy, loc, rot, mat, amp=0.25, scale=0.6, cuts=60, seed=0):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=cuts, y_segments=cuts, size=1.0)
    off = Vector((seed, seed * 2, 0))
    for v in bm.verts:
        v.co.x *= sx; v.co.y *= sy
        v.co.z = amp * noise.fractal(Vector((v.co.x * scale, v.co.y * scale, 0)) + off, 1.0, 2.0, 4)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc; ob.rotation_euler = rot
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.materials.append(mat)
    return ob

def root(name, top, length, seed=0, r0=0.05, mat=None):
    random.seed(seed)
    pts = [Vector(top)]
    d = Vector((random.uniform(-0.2, 0.2), random.uniform(-0.1, 0.1), -1)).normalized()
    for i in range(6):
        d = (d + Vector((random.uniform(-0.35, 0.35), random.uniform(-0.2, 0.2), -0.2))).normalized()
        pts.append(pts[-1] + d * length / 6)
    ob, _, _ = tube(name, pts, lambda u, L: r0 * (1 - 0.85 * u) + 0.004, ring=10, samples=60)
    ob.data.materials.append(mat or mat_simple('root_m', (0.42, 0.30, 0.20), 0.75, sss=0.1))
    return ob

def rocket(state='assembled', loc=(0, 0, 0), with_nozzle=False):
    """Junk rocket: tin can body, foil cone, 3 match legs, cap decorations."""
    parts = []
    can = tin_can('rk_can')
    cone = foil_cone('rk_cone')
    cone.location = (0, 0, 3.08)
    parts += [can, cone]
    caps = []
    for i, (ang, col) in enumerate([(0.0, (0.75, 0.08, 0.06)), (2.1, (0.08, 0.25, 0.7)), (4.2, (0.85, 0.65, 0.08))]):
        c = bottle_cap(f'rk_cap{i}', col, r=0.32, h=0.13)
        c.rotation_euler = (math.pi / 2, 0, ang + math.pi / 2)
        c.location = (1.02 * math.cos(ang), 1.02 * math.sin(ang), 1.8)
        caps.append(c)
    parts += caps
    legs = []
    for i in range(3):
        a = i * 2 * math.pi / 3 + math.pi / 3
        m = matchstick(f'rk_leg{i}', L=1.5, burnt=(state == 'broken'))
        m.location = (1.35 * math.cos(a), 1.35 * math.sin(a), -0.55)
        m.rotation_euler = (0.38 * math.sin(a), -0.38 * math.cos(a), 0)
        legs.append(m)
    parts += legs
    clip = paperclip('rk_clip'); clip.location = (-0.2, -1.04, 2.5); clip.rotation_euler = (math.pi / 2, 0, 0)
    parts.append(clip)
    if with_nozzle:
        nz = bottle_cap('rk_nozzle', (0.75, 0.08, 0.06), r=0.5, h=0.2)
        nz.rotation_euler = (math.pi, 0, 0); nz.location = (0, 0, 0.0)
        parts.append(nz)
    root_e = bpy.data.objects.new('rocket', None); link(root_e)
    for p in parts:
        if p.parent is None:
            p.parent = root_e
    root_e.location = loc
    if state == 'broken':
        root_e.rotation_euler = (0.0, 1.35, 0.4)
        root_e.location = (loc[0], loc[1], loc[2] + 0.9)
        cone.parent = None
        cone.location = (loc[0] + 2.4, loc[1] - 0.6, 0.35)
        cone.rotation_euler = (1.9, 0.3, 0.6)
        for m in legs:
            m.parent = None
        for i, m in enumerate(legs):
            m.location = (loc[0] - 1.6 + i * 0.9, loc[1] - 1.2 + 0.3 * i, 0.04)
            m.rotation_euler = (math.pi / 2, 0, 0.7 * i)
        soot = mat_simple('soot', (0.11, 0.09, 0.075), 0.5, metal=0.6)  # scorched tin, still reads as metal
        can.data.materials.clear(); can.data.materials.append(soot)
    if state == 'pile':
        root_e.location = (loc[0], loc[1], loc[2] + 1.0)
        root_e.rotation_euler = (math.pi / 2, 0, 0.5)
        cone.parent = None; cone.location = (loc[0] + 2.3, loc[1] + 0.4, 0.0); cone.rotation_euler = (0.25, 0.0, 0)
        for i, c in enumerate(caps):
            c.parent = None; c.rotation_euler = (0, 0, 0); c.location = (loc[0] - 1.8 + 0.75 * i, loc[1] - 1.5, 0.0)
        for i, m in enumerate(legs):
            m.parent = None; m.location = (loc[0] - 1.0 + 0.25 * i, loc[1] - 2.3 + 0.1 * i, 0.04)
            m.rotation_euler = (math.pi / 2, 0, 1.4 + 0.08 * i)
        clip.parent = None; clip.location = (loc[0] + 1.4, loc[1] - 1.9, 0.02); clip.rotation_euler = (0, 0, 0.4)
    return root_e, dict(can=can, cone=cone, caps=caps, legs=legs, clip=clip)

def control_pebble(loc=(0, 0, 0), lit=(True, True, True)):
    st = rock('ctrl_stone', size=0.55, seed=11, mat=mat_simple('ctrl_m', (0.36, 0.34, 0.31), 0.7), flat=0.55)
    st.location = loc
    out = [st]
    for i in range(3):
        x = loc[0] - 0.25 + 0.25 * i
        if lit[i]:
            b, l = firefly(f'ctrl_led{i}', (x, loc[1] - 0.12, loc[2] + 0.3), energy=0.15, color=(1.0, 0.7, 0.25), size=0.045)
        else:
            b = rock(f'ctrl_led{i}', 0.045, seed=i, mat=mat_simple('led_off', (0.08, 0.07, 0.05), 0.5))
            b.location = (x, loc[1] - 0.12, loc[2] + 0.3)
        out.append(b)
    btn = lathe('ctrl_btn', [(0.16, 0), (0.17, 0.03), (0.15, 0.08), (0.08, 0.11), (0.0, 0.115)], seg=32)
    btn.location = (loc[0] + 0.15, loc[1] + 0.18, loc[2] + 0.26)
    btn.data.materials.append(mat_simple('btn_m', (0.7, 0.05, 0.03), 0.35, coat=0.8))
    out.append(btn)
    return out

# ---------------------------------------------------------------- workshop set
def shaft(name, center, r=1.0, z0=5.2, z1=16.0, mat=None, seed=2):
    seg, rings = 48, 40
    verts, faces = [], []
    for i in range(rings + 1):
        z = z0 + (z1 - z0) * i / rings
        for j in range(seg):
            a = 2 * math.pi * j / seg
            n = noise.fractal(Vector((math.cos(a) * 1.3, math.sin(a) * 1.3, z * 0.45 + seed)), 1.0, 2.0, 4)
            rr = r * (1.0 + 0.18 * n) * (1.0 + 0.25 * max(0.0, (z0 + 1.2 - z)) / 1.2)
            verts.append((center[0] + rr * math.cos(a), center[1] + rr * math.sin(a), z))
    for i in range(rings):
        for j in range(seg):
            a = i * seg + j; b = i * seg + (j + 1) % seg
            faces.append((a, a + seg, b + seg, b))
    ob = mesh_obj(name, verts, faces)
    ob.data.materials.append(mat)
    return ob

def ceiling_with_hole(name, sx, sy, z, hole, hr, mat, cuts=90, seed=4):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=cuts, y_segments=cuts, size=1.0)
    for v in bm.verts:
        v.co.x = v.co.x * sx; v.co.y = v.co.y * sy + 1.5
        v.co.z = z - 0.4 * noise.fractal(Vector((v.co.x * 0.5, v.co.y * 0.5, seed)), 1.0, 2.0, 4)
    kill = [v for v in bm.verts if (Vector((v.co.x, v.co.y)) - Vector(hole[:2])).length < hr]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me))
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.materials.append(mat)
    return ob

def workshop(shaft_xy=(2.2, 2.2), fireflies=True, mars=True, crumbs=True, seed=1):
    random.seed(seed)
    soil = mat_soil('soil', base=(0.085, 0.05, 0.032))
    floor_m = mat_soil('floor_soil', base=(0.13, 0.08, 0.05), layered=False)
    rockm = mat_simple('pebble', (0.30, 0.27, 0.24), 0.75)
    rockm2 = mat_simple('pebble2', (0.42, 0.36, 0.30), 0.7)
    objs = {}
    objs['floor'] = displaced_plane('floor', 9, 5, (0, 1.5, 0), (0, 0, 0), floor_m, amp=0.06, scale=0.9, cuts=120, seed=seed)
    objs['back'] = displaced_plane('back', 9, 4.0, (0, 5.2, 3.0), (math.pi / 2, 0, 0), soil, amp=0.45, scale=0.45, cuts=110, seed=seed + 1)
    objs['left'] = displaced_plane('left', 4.0, 4.0, (-8.0, 1.5, 3.0), (math.pi / 2, 0, math.pi / 2), soil, amp=0.4, scale=0.5, cuts=60, seed=seed + 2)
    objs['right'] = displaced_plane('right', 4.0, 4.0, (8.0, 1.5, 3.0), (math.pi / 2, 0, -math.pi / 2), soil, amp=0.4, scale=0.5, cuts=60, seed=seed + 3)
    objs['ceil'] = ceiling_with_hole('ceiling', 9, 4.5, 6.2, (shaft_xy[0], shaft_xy[1]), 1.15, soil)
    objs['shaft'] = shaft('shaft', shaft_xy, r=1.05, z0=5.6, z1=17.0, mat=soil)
    # pebbles on floor along walls and embedded in back wall
    for i in range(70):
        x = random.uniform(-7.5, 7.5)
        y = random.choice([random.uniform(3.6, 4.9), random.uniform(-1.5, 4.8)])
        s = random.uniform(0.05, 0.22) if y > 3.5 else random.uniform(0.03, 0.09)
        r_ = rock(f'peb{i}', s, seed=i + seed * 100, mat=random.choice([rockm, rockm2]))
        r_.location = (x, y, s * 0.3)
        r_.rotation_euler = (0, 0, random.uniform(0, 6.28))
    wallrock = mat_simple('wallrock', (0.16, 0.13, 0.11), 0.8)
    for i in range(16):
        x = random.uniform(-7.8, 7.8); z = random.uniform(0.8, 5.6)
        s = random.uniform(0.10, 0.30)
        r_ = rock(f'wallpeb{i}', s, seed=i + 500, mat=wallrock, flat=0.6)
        r_.location = (x, 5.15, z)
        r_.rotation_euler = (math.pi / 2, random.uniform(0, 6.28), 0)
    if crumbs:
        for i in range(160):
            r_ = rock(f'crumb{i}', random.uniform(0.012, 0.03), seed=i + 900, mat=floor_m)
            r_.location = (random.uniform(-6, 6), random.uniform(-1.5, 4.5), 0.01)
    rootm = mat_simple('root_m', (0.40, 0.29, 0.19), 0.75, sss=0.1)
    for i in range(9):
        x = random.uniform(-7, 7)
        if abs(x - shaft_xy[0]) < 1.4:
            x += 2.5
        root(f'root{i}', (x, random.uniform(2.5, 4.8), 6.3), random.uniform(1.2, 2.6), seed=i + seed * 10, r0=random.uniform(0.03, 0.07), mat=rootm)
    if mars:
        m = mat_emit('mars_e', (1.0, 0.28, 0.12), 60.0)
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.6)
        me = bpy.data.meshes.new('mars'); bm.to_mesh(me); bm.free()
        mo = link(bpy.data.objects.new('mars', me)); mo.data.materials.append(m)
        mo.location = (shaft_xy[0] + 3.0, shaft_xy[1] + 1.5, 160)
        objs['mars'] = mo
    # moonlight down the shaft
    L = bpy.data.lights.new('moon', 'SPOT'); L.energy = 2500; L.color = (0.62, 0.72, 1.0)
    L.spot_size = math.radians(30); L.spot_blend = 0.6; L.shadow_soft_size = 0.8
    lo = link(bpy.data.objects.new('moon', L)); lo.location = (shaft_xy[0], shaft_xy[1], 16.5)
    lo.rotation_euler = (0, 0, 0)
    objs['moon'] = lo
    if fireflies:
        ff = [(-5.5, 3.6, 3.4), (-2.6, 4.2, 4.6), (0.4, 3.0, 4.0), (4.6, 3.8, 3.2), (6.2, 2.6, 4.8), (-0.9, 1.4, 2.6)]
        for i, p in enumerate(ff):
            firefly(f'ff{i}', p, energy=random.uniform(7.0, 11.0), color=(1.0, 0.78, 0.36))
    return objs

def star_field(center, z=150, n=260, spread=30, seed=5):
    random.seed(seed)
    m = mat_emit('star_e', (0.85, 0.9, 1.0), 18.0)
    for i in range(n):
        s = random.uniform(0.05, 0.16) * (2.2 if random.random() < 0.06 else 1.0)
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=s)
        me = bpy.data.meshes.new(f'star{i}'); bm.to_mesh(me); bm.free()
        ob = link(bpy.data.objects.new(f'star{i}', me)); ob.data.materials.append(m)
        ob.location = (center[0] + random.uniform(-spread, spread), center[1] + random.uniform(-spread, spread), z + random.uniform(-5, 5))
        ob.visible_shadow = False
