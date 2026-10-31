"""Series intro sample: cold-open hook (hero rises into the sky circle) and the 0x studio ident.
Renders PNG frames at 12 fps (stop-motion feel, doubled to 24 fps on encode).
usage: python3 intro.py hook|ident   env: W,H,SAMPLES,FRAMES="1,15,30"
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
import wsp_lib as W
import shots

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, 'fonts')
RW, RH = int(os.environ.get('W', 1280)), int(os.environ.get('H', 720))
SAMPLES = int(os.environ.get('SAMPLES', 10))
FPS = 12
N = 30  # 2.5 s


def key(ob, path, frame, value, interp='BEZIER'):
    setattr(ob, path, value) if not isinstance(value, tuple) else setattr(ob, path, value)
    ob.keyframe_insert(data_path=path, frame=frame)
    try:
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                if kp.co[0] == frame:
                    kp.interpolation = interp
    except Exception:
        pass


def render_frames(name, per_frame=None, n=None):
    n = n or N
    sc = bpy.context.scene
    W.render_settings(RW, RH, SAMPLES)
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, n
    outdir = os.path.join(HERE, 'out', 'intro', name)
    os.makedirs(outdir, exist_ok=True)
    frames = os.environ.get('FRAMES')
    frames = [int(f) for f in frames.split(',')] if frames else list(range(1, n + 1))
    import time
    for f in frames:
        sc.frame_set(f)
        if per_frame:
            per_frame(f)
        sc.render.filepath = os.path.join(outdir, f'{f:04d}.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('frame', name, f, round(time.time() - t0, 1), flush=True)


# ------------------------------------------------------------------ hook
def hook():
    shots.render = lambda *a, **k: None
    shots.s1_hook()                       # builds the shaft scene with the hero in its final pose
    hero = bpy.data.objects['hero']; helm = bpy.data.objects['hero_helmet']
    rig = bpy.data.objects.new('hero_rig', None); W.link(rig)
    for ob in (hero, helm):
        ob.parent = rig
    # rise along the neck direction: start hidden below the frame, pop up, small settle
    d = Vector((0, -0.35, 0.95)).normalized()
    start = tuple(-1.05 * d)
    rig.location = start; rig.keyframe_insert('location', frame=1)
    rig.location = start; rig.keyframe_insert('location', frame=4)
    rig.location = tuple(0.06 * d); rig.keyframe_insert('location', frame=17)
    rig.location = (0, 0, 0); rig.keyframe_insert('location', frame=21)
    # head turns slightly toward Mars and freezes
    rig.rotation_euler = (0, 0, 0); rig.keyframe_insert('rotation_euler', frame=21)
    rig.rotation_euler = (math.radians(-2.5), math.radians(2.0), 0); rig.keyframe_insert('rotation_euler', frame=27)
    # hand-held drift
    cam = bpy.context.scene.camera
    base = cam.location.copy()
    for f, o in [(1, (0, 0, 0)), (10, (0.01, -0.005, 0)), (20, (-0.006, 0.008, 0)), (30, (0.004, 0.0, 0))]:
        cam.location = base + Vector(o); cam.keyframe_insert('location', frame=f)
    render_frames('hook')


# ------------------------------------------------------------------ ident
def text_obj(name, body, font, size, loc, extrude=0.0, bevel=0.0, mat=None, align='CENTER', spacing=1.0):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.font = bpy.data.fonts.load(font)
    cu.size = size; cu.extrude = extrude; cu.bevel_depth = bevel; cu.bevel_resolution = 3
    cu.align_x = align; cu.align_y = 'CENTER'; cu.space_character = spacing
    ob = bpy.data.objects.new(name, cu); W.link(ob)
    ob.location = loc; ob.rotation_euler = (math.radians(90), 0, 0)
    if mat:
        cu.materials.append(mat)
    return ob


def world_bbox(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    pts = [e.matrix_world @ Vector(c) for c in e.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def ident():
    W.reset()
    w = bpy.data.worlds.new('black'); bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = [n for n in w.node_tree.nodes if n.type == 'BACKGROUND'][0]
    bg.inputs['Color'].default_value = (0.004, 0.003, 0.002, 1); bg.inputs['Strength'].default_value = 1.0
    gold = W.mat_simple('gold', (1.0, 0.64, 0.22), 0.2, metal=1.0)
    bold = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'; reg = os.path.join(FONTS, 'Cinzel-700.ttf')
    zero = text_obj('t0', '0', bold, 1.9, (-0.62, 0, 0.35), extrude=0.14, bevel=0.03, mat=gold)
    ex = text_obj('tx', 'x', bold, 1.9, (0.42, 0, 0.18), extrude=0.14, bevel=0.03, mat=gold)
    bpy.context.view_layer.update()
    lo, hi = world_bbox(zero)
    c = (lo + hi) / 2; wdt = hi.x - lo.x; hgt = hi.z - lo.z
    # the hole: dark soil disc inside the counter of the 0, its edge hidden behind the gold ring
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=1.0)
    me = bpy.data.meshes.new('hole'); bm.to_mesh(me); bm.free()
    hole = W.link(bpy.data.objects.new('hole', me))
    hole.location = (c.x, 0.04, c.z); hole.rotation_euler = (math.radians(90), 0, 0)
    hole.scale = (wdt * 0.33, hgt * 0.40, 1)
    hole.data.materials.append(W.mat_simple('hole_m', (0.006, 0.004, 0.003), 0.95))
    # cursor >_ glowing orange, blinking
    cur_m = W.mat_emit('cursor_e', (1.0, 0.28, 0.02), 3.2)
    cur = text_obj('cursor', '>_', bold, 0.75, (1.42, 0, -0.08), extrude=0.03, mat=cur_m, align='LEFT')
    em = [n for n in cur_m.node_tree.nodes if n.type == 'EMISSION'][0].inputs['Strength']
    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = 'CONSTANT'   # hard on/off blink
    for f in range(1, N + 1, 6):
        em.default_value = 3.2 if (f // 6) % 2 == 0 else 0.25
        em.keyframe_insert('default_value', frame=f)
    prefs.keyframe_new_interpolation_type = 'BEZIER'
    # subtitle, fades in
    sub_m = W.mat_emit('sub_e', (1.0, 0.86, 0.62), 0.0)
    text_obj('sub1', 'PRODUCTION', reg, 0.36, (0.25, -0.05, -0.95), mat=sub_m, spacing=1.35)
    sub2_m = W.mat_emit('sub2_e', (0.85, 0.78, 0.66), 0.0)
    text_obj('sub2', 'presents', os.path.join(FONTS, 'Cinzel-400.ttf'), 0.22, (0.25, -0.05, -1.32), mat=sub2_m, spacing=1.2)
    for m, f0 in ((sub_m, 9), (sub2_m, 13)):
        s = [n for n in m.node_tree.nodes if n.type == 'EMISSION'][0].inputs['Strength']
        s.default_value = 0.0; s.keyframe_insert('default_value', frame=f0)
        s.default_value = 1.6; s.keyframe_insert('default_value', frame=f0 + 5)
    # the hero slides out of the 0 along a track like a periscope; rebuilt every frame
    cz = c.z - hgt * 0.05
    track = [Vector(p) for p in [(c.x, 1.6, cz), (c.x, 0.6, cz), (c.x, 0.04, cz), (c.x, -0.22, cz + 0.06),
                                  (c.x, -0.3, cz + 0.3), (c.x, -0.29, cz + 0.55), (c.x, -0.27, cz + 0.8)]]
    dense = W.catmull(track, 24); dense, Lt = W.resample(dense, 400)
    cum = [0.0]
    for i in range(1, len(dense)):
        cum.append(cum[-1] + (dense[i] - dense[i - 1]).length)
    def at_len(u):
        u = max(0.0, min(cum[-1], u))
        for i in range(1, len(cum)):
            if cum[i] >= u:
                t = (u - cum[i - 1]) / max(1e-9, cum[i] - cum[i - 1])
                return dense[i - 1].lerp(dense[i], t)
        return dense[-1]
    u_hole = cum[next(i for i, p in enumerate(dense) if p.y <= 0.04)]
    Lw = 1.55
    # emergence s (head position along the track) and roar bend per frame
    keys_s = [(1, 0.0), (5, 0.0), (9, 1.04), (11, 0.98), (24, 0.98), (28, 0.0), (30, 0.0)]
    keys_r = [(1, 0), (12, 0), (14, 1), (16, 0.85), (18, 1), (21, 0), (30, 0)]
    def interp(keys, f):
        for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
            if f0 <= f <= f1:
                t = (f - f0) / (f1 - f0); t = t * t * (3 - 2 * t)
                return v0 + (v1 - v0) * t
        return keys[-1][1]
    u_end = cum[-1]
    def build(f):
        for n in ('hero', 'hero_helmet'):
            ob = bpy.data.objects.get(n)
            if ob:
                bpy.data.objects.remove(ob, do_unlink=True)
        sv = interp(keys_s, f); rv = interp(keys_r, f)
        head_u = u_hole - 0.4 + sv * (u_end - u_hole + 0.4)
        ctrl = [at_len(head_u - Lw + Lw * k / 7) for k in range(8)]
        # roar: head and neck bend back toward the camera-up, small shake
        if rv > 0:   # roar: head stretches up and shakes side to side
            side = 0.07 if f % 2 else -0.07
            for k, wgt in ((5, 0.3), (6, 0.65), (7, 1.0)):
                ctrl[k] = ctrl[k] + Vector((side * wgt * rv, -0.04 * wgt * rv, 0.14 * wgt * rv))
        shots.hero([tuple(p) for p in ctrl], tilt=0.0)
    # backdrop just behind the letters: hides everything behind it, faint warm glow in the middle
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
    me = bpy.data.meshes.new('backdrop'); bm.to_mesh(me); bm.free()
    bd = W.link(bpy.data.objects.new('backdrop', me)); bd.location = (0.25, 0.3, 0.1)
    bd.rotation_euler = (math.radians(90), 0, 0); bd.scale = (9, 6, 1)
    bdm = W.new_mat('backdrop_m'); nt = bdm.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    tc = nt.nodes.new('ShaderNodeTexCoord'); gr = nt.nodes.new('ShaderNodeTexGradient'); gr.gradient_type = 'SPHERICAL'
    nt.links.new(tc.outputs['Object'], gr.inputs['Vector'])
    pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 3.0
    nt.links.new(gr.outputs['Fac'], pw.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.07
    nt.links.new(pw.outputs[0], mul.inputs[0])
    em2 = nt.nodes.new('ShaderNodeEmission'); em2.inputs['Color'].default_value = (1.0, 0.5, 0.18, 1)
    nt.links.new(mul.outputs[0], em2.inputs['Strength']); nt.links.new(em2.outputs[0], out.inputs['Surface'])
    bd.data.materials.append(bdm)
    # lights: soft warm key, two rims, a glint sweeping across the gold
    W.area_light('key', (-3.5, -5.5, 4.5), (math.radians(50), 0, math.radians(-32)), 150, 4, (1.0, 0.86, 0.66))
    W.area_light('rimL', (-3.5, 3.0, 2.5), (math.radians(-60), 0, math.radians(-130)), 260, 2, (1.0, 0.7, 0.4))
    W.area_light('rimR', (3.5, 3.0, 2.5), (math.radians(-60), 0, math.radians(130)), 260, 2, (1.0, 0.7, 0.4))
    W.area_light('fill', (0, -7, 0.5), (math.radians(88), 0, 0), 60, 6, (0.9, 0.85, 0.8))
    glint = W.area_light('glint', (-4.0, -3.0, 1.2), (math.radians(80), 0, math.radians(-50)), 500, 0.5, (1.0, 0.95, 0.85))
    if isinstance(glint, tuple):
        glint = glint[0]
    gob = glint if hasattr(glint, 'location') else bpy.data.objects['glint']
    gob.location = (-4.0, -3.0, 1.2); gob.keyframe_insert('location', frame=1)
    gob.location = (4.0, -3.0, 1.2); gob.keyframe_insert('location', frame=N)
    # camera: slow push-in
    cam = W.camera((0.2, -8.6, 0.25), (0.2, 0, 0.08), lens=52, fstop=11)
    cam.location = (0.2, -8.6, 0.25); cam.keyframe_insert('location', frame=1)
    cam.location = (0.2, -7.7, 0.22); cam.keyframe_insert('location', frame=N)
    render_frames('ident', per_frame=build)



# ------------------------------------------------------------------ ident v2: crown-cap medallion (sketch 1)
N2 = 42  # 3.5 s


def slab(name, outline, y0, y1, mat, cx=0.0, cz=0.0, bevel=0.03):
    """2D outline in the XZ plane extruded along +y (front face at y0)."""
    bm = bmesh.new()
    fr = [bm.verts.new((cx + x, y0, cz + z)) for x, z in outline]
    bk = [bm.verts.new((cx + x, y1, cz + z)) for x, z in outline]
    bm.faces.new(fr); bm.faces.new(bk[::-1])
    sides = []
    for i in range(len(fr)):
        j = (i + 1) % len(fr)
        sides.append(bm.faces.new((fr[i], fr[j], bk[j], bk[i])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in sides:
        f.smooth = True
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = W.link(bpy.data.objects.new(name, me)); ob.data.materials.append(mat)
    if bevel:
        b = ob.modifiers.new('bev', 'BEVEL'); b.width = bevel; b.segments = 3; b.limit_method = 'ANGLE'
    return ob


def circle_outline(r, n=128):
    return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def crimp_outline(R1, R2, k=21, per=14):
    out = []
    for i in range(k * per):
        a = 2 * math.pi * i / (k * per) + math.pi / 2
        c = (math.cos(k * (a - math.pi / 2)) + 1) / 2
        r = R2 + (R1 - R2) * c ** 0.6
        out.append((r * math.cos(a), r * math.sin(a)))
    return out


def torus(name, R, r, loc, mat):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=128, minor_segments=14,
                                     location=loc, rotation=(math.radians(90), 0, 0))
    ob = bpy.context.active_object; ob.name = name
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.materials.append(mat)
    return ob


def emit_sphere(name, loc, r, mat, sub=1):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = W.link(bpy.data.objects.new(name, me)); ob.location = loc; ob.data.materials.append(mat)
    ob.visible_shadow = False
    return ob


def ident2():
    import random
    random.seed(21)
    W.reset()
    w = bpy.data.worlds.new('black'); bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = [n for n in w.node_tree.nodes if n.type == 'BACKGROUND'][0]
    bg.inputs['Color'].default_value = (0.004, 0.003, 0.002, 1)
    gold = W.mat_simple('gold', (1.0, 0.64, 0.22), 0.18, metal=1.0)
    gold_dark = W.mat_simple('gold_dark', (0.62, 0.38, 0.12), 0.32, metal=1.0)
    gold_rib = W.mat_simple('gold_rib', (0.95, 0.66, 0.28), 0.3, metal=1.0)
    cz = 0.9
    # medallion: crimped crown cap, flat top, two raised rings, recessed night-sky portal
    slab('cap_rim', crimp_outline(2.32, 2.08), -0.05, 0.25, gold, cz=cz, bevel=0.04)
    slab('cap_top', circle_outline(1.98), -0.12, 0.2, gold_dark, cz=cz, bevel=0.03)
    torus('ring_out', 1.88, 0.065, (0, -0.13, cz), gold)
    torus('ring_in', 1.73, 0.055, (0, -0.12, cz), gold)
    sky_m = W.new_mat('sky_m'); nt = sky_m.node_tree
    for n_ in list(nt.nodes):
        if n_.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n_)
    out = [n_ for n_ in nt.nodes if n_.type == 'OUTPUT_MATERIAL'][0]
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (0.6, 0.6, 0.6); mp.inputs['Location'].default_value = (-0.15, 0, -0.25)
    gr = nt.nodes.new('ShaderNodeTexGradient'); gr.gradient_type = 'SPHERICAL'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.003, 0.004, 0.009, 1); ramp.color_ramp.elements[1].color = (0.03, 0.045, 0.1, 1)
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 1.0
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], gr.inputs['Vector'])
    nt.links.new(gr.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    sky = slab('sky', circle_outline(1.69), -0.126, -0.121, sky_m, cz=cz, bevel=0)
    star_m = W.mat_emit('star_m', (0.9, 0.93, 1.0), 9.0)
    for i in range(80):
        while True:
            x, z = random.uniform(-1.6, 1.6), random.uniform(-0.75, 1.6)
            if x * x + z * z < 1.55 ** 2:
                break
        emit_sphere(f'st{i}', (x, -0.135, cz + z), random.uniform(0.007, 0.02) * (2.0 if random.random() < 0.07 else 1.0), star_m)
    mars_m = W.mat_emit('mars_m', (1.0, 0.24, 0.07), 6.0)
    ms = emit_sphere('mars', (0.72, -0.2, cz + 0.86), 0.17, mars_m, sub=4)
    for p_ in ms.data.polygons:
        p_.use_smooth = True
    halo_m = W.mat_emit('mars_halo', (1.0, 0.3, 0.1), 0.35)
    hs = emit_sphere('mars_halo', (0.72, -0.13, cz + 0.86), 0.3, halo_m, sub=3)
    for p_ in hs.data.polygons:
        p_.use_smooth = True
    # soil mound inside the portal, clipped to the portal circle
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0, location=(0, -0.05, cz - 1.42))
    mound = bpy.context.active_object; mound.name = 'mound'; mound.scale = (1.8, 0.42, 0.62)
    for p in mound.data.polygons:
        p.use_smooth = True
    mound.data.materials.append(W.mat_soil('mound_soil', base=(0.07, 0.04, 0.024), layered=False, scale=0.6))
    tex = bpy.data.textures.new('lump', 'CLOUDS'); tex.noise_scale = 0.35
    dsp = mound.modifiers.new('dsp', 'DISPLACE'); dsp.texture = tex; dsp.strength = 0.07
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.69, depth=3.0, location=(0, 0, cz), rotation=(math.radians(90), 0, 0))
    cutter = bpy.context.active_object; cutter.name = 'cutter'; cutter.hide_render = True; cutter.display_type = 'WIRE'
    bo = mound.modifiers.new('clip', 'BOOLEAN'); bo.operation = 'INTERSECT'; bo.object = cutter
    for i in range(10):
        r_ = W.rock(f'peb{i}', random.uniform(0.04, 0.09), seed=i + 70, mat=W.mat_simple('peb_m', (0.16, 0.13, 0.1), 0.8))
        r_.location = (random.uniform(-1.2, 1.2), -0.42, cz - 1.0 - random.uniform(0.05, 0.4))
    # ribbon with the motto
    rib_y0, rib_z0, half = -0.62, cz - 1.62, 0.25
    bm = bmesh.new(); rows = []
    for i in range(49):
        x = -2.55 + 5.1 * i / 48; q = (x / 2.55) ** 2
        zc = rib_z0 + 0.34 * q; y = rib_y0 + 0.14 * q
        rows.append((bm.verts.new((x, y, zc - half)), bm.verts.new((x, y, zc + half))))
    for i in range(48):
        bm.faces.new((rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]))
    me = bpy.data.meshes.new('ribbon'); bm.to_mesh(me); bm.free()
    rib = W.link(bpy.data.objects.new('ribbon', me)); rib.data.materials.append(gold_rib)
    for p in rib.data.polygons:
        p.use_smooth = True
    so = rib.modifiers.new('sol', 'SOLIDIFY'); so.thickness = 0.04
    ze = rib_z0 + 0.34
    for sgn in (-1, 1):
        tail = [(2.45, ze + 0.2), (3.3, ze + 0.3), (3.0, ze - 0.02), (3.32, ze - 0.34), (2.45, ze - 0.26)]
        tail = [(sgn * x, z) for x, z in tail]
        if sgn < 0:
            tail = tail[::-1]
        slab(f'tail{sgn}', tail, rib_y0 + 0.3, rib_y0 + 0.34, gold_dark, bevel=0.01)
    # motto: one letter per object, laid along the ribbon arc and tilted with it
    motto_m = W.mat_simple('motto_m', (0.045, 0.022, 0.006), 0.7)
    cfont = os.path.join(FONTS, 'Cinzel-700.ttf')
    text, size, gap, space_w = 'PER TERRAM AD ASTRA', 0.27, 0.045, 0.14
    letters = []
    for ch in text:
        if ch == ' ':
            letters.append((None, space_w)); continue
        ob = text_obj('m_' + ch, ch, cfont, size, (0, 0, 0), extrude=0.012, mat=motto_m)
        letters.append((ob, 0.0))
    bpy.context.view_layer.update()
    widths = []
    for ob, w_ in letters:
        if ob is None:
            widths.append(w_); continue
        lo, hi = world_bbox(ob); widths.append(hi.x - lo.x)
    total = sum(widths) + gap * (len(widths) - 1)
    x = -total / 2
    for (ob, _), wdt in zip(letters, widths):
        xc = x + wdt / 2; x += wdt + gap
        if ob is None:
            continue
        q = (xc / 2.55) ** 2
        ob.location = (xc, rib_y0 + 0.14 * q - 0.04, rib_z0 + 0.34 * q + 0.1)
        slope = 2 * 0.34 * xc / 2.55 ** 2
        ob.rotation_euler = (math.radians(90), -math.atan(slope), 0)
    # wordmark
    pf = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'  # lining zero and a real lowercase x
    text_obj('word0x', '0x', pf, 1.4, (0, -0.1, -2.42), extrude=0.1, bevel=0.022, mat=gold)
    sub_m = W.mat_emit('sub_e', (1.0, 0.8, 0.45), 0.0)
    text_obj('production', 'PRODUCTION', os.path.join(FONTS, 'Cinzel-700.ttf'), 0.4, (0.1, -0.1, -3.3), mat=sub_m, spacing=1.45)
    s_ = [n_ for n_ in sub_m.node_tree.nodes if n_.type == 'EMISSION'][0].inputs['Strength']
    s_.default_value = 0.0; s_.keyframe_insert('default_value', frame=6)
    s_.default_value = 1.5; s_.keyframe_insert('default_value', frame=12)
    # sparkles that twinkle
    spark_m = W.mat_emit('spark_m', (1.0, 0.85, 0.5), 4.0)
    star4 = [(0, 1), (0.2, 0.2), (1, 0), (0.2, -0.2), (0, -1), (-0.2, -0.2), (-1, 0), (-0.2, 0.2)]
    for i, (x, z, sz, ph) in enumerate([(-2.55, cz + 1.95, 0.17, 0), (2.5, cz + 2.1, 0.14, 7), (2.95, cz + 0.55, 0.08, 3), (-3.0, cz + 0.3, 0.08, 10)]):
        sob = slab(f'spark{i}', [(a * sz, b * sz) for a, b in star4], -0.3, -0.29, spark_m, cx=x, cz=z, bevel=0)
        sob.location = (0, 0, 0)
        for f, v in ((1 + ph, 0.6), (6 + ph, 1.15), (11 + ph, 0.5), (17 + ph, 1.1), (24 + ph, 0.55), (31 + ph, 1.15), (38 + ph, 0.6)):
            sob.delta_scale = (v, v, v)
        # scale about its own center: parent to an empty at the sparkle center
        pivot = bpy.data.objects.new(f'spark_piv{i}', None); W.link(pivot); pivot.location = (x, -0.3, z)
        for v_ in sob.data.vertices:
            v_.co.x -= x; v_.co.z -= z
        sob.parent = pivot
        for f, v in ((1 + ph, 0.6), (6 + ph, 1.15), (11 + ph, 0.5), (17 + ph, 1.1), (24 + ph, 0.55), (31 + ph, 1.15), (38 + ph, 0.6)):
            pivot.scale = (v, v, v); pivot.keyframe_insert('scale', frame=f)
        sob.delta_scale = (1, 1, 1)
    # the hero pops out of the mound, looks at Mars, roars, ducks back
    track = [Vector(p) for p in [(0.0, 0.0, cz - 1.75), (0.0, -0.08, cz - 1.38), (0.02, -0.22, cz - 1.0),
                                  (0.05, -0.34, cz - 0.6), (0.1, -0.4, cz - 0.22), (0.16, -0.42, cz + 0.12)]]
    dense = W.catmull(track, 24); dense, _ = W.resample(dense, 400)
    cum = [0.0]
    for i in range(1, len(dense)):
        cum.append(cum[-1] + (dense[i] - dense[i - 1]).length)
    def at_len(u):
        u = max(0.0, min(cum[-1], u))
        for i in range(1, len(cum)):
            if cum[i] >= u:
                t = (u - cum[i - 1]) / max(1e-9, cum[i] - cum[i - 1])
                return dense[i - 1].lerp(dense[i], t)
        return dense[-1]
    u_emerge = cum[next(i for i, p in enumerate(dense) if p.z >= cz - 0.86)]
    Lw, u_end = 2.0, cum[-1]
    keys_s = [(1, 0.0), (10, 0.0), (14, 1.04), (16, 0.98), (30, 0.98), (35, 0.0), (42, 0.0)]
    keys_l = [(1, 0), (15, 0), (19, 1), (29, 1), (33, 0), (42, 0)]
    keys_r = [(1, 0), (19, 0), (20, 1), (22, 0.85), (24, 1), (26, 0.85), (27, 0), (42, 0)]
    def interp(keys, f):
        for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
            if f0 <= f <= f1:
                t = (f - f0) / (f1 - f0); t = t * t * (3 - 2 * t)
                return v0 + (v1 - v0) * t
        return keys[-1][1]
    def build(f):
        for n_ in ('hero', 'hero_helmet'):
            ob = bpy.data.objects.get(n_)
            if ob:
                bpy.data.objects.remove(ob, do_unlink=True)
        sv, lv, rv = interp(keys_s, f), interp(keys_l, f), interp(keys_r, f)
        head_u = u_emerge - 0.6 + sv * (u_end - u_emerge + 0.6)
        ctrl = [at_len(head_u - Lw + Lw * k / 7) for k in range(8)]
        for k, wgt in ((5, 0.3), (6, 0.65), (7, 1.0)):
            ctrl[k] = ctrl[k] + Vector((0.22 * wgt * lv, 0, 0.06 * wgt * lv))       # look at Mars
            if rv > 0:
                side = 0.12 if f % 2 else -0.12
                ctrl[k] = ctrl[k] + Vector((side * wgt * rv, -0.06 * wgt * rv, 0.26 * wgt * rv))
        ob, pts, T = W.worm('hero', [tuple(p) for p in ctrl], R=0.2, mat=W.mat_worm('hero_m2', body=(0.12, 0.032, 0.02), band=(0.42, 0.19, 0.14)))
        th = W.thimble('hero_helmet'); th.scale = (1.85, 1.85, 1.85)
        tip, t = pts[-1], T[-1]
        th.location = tip - t * 0.31; th.rotation_euler = t.to_track_quat('Z', 'Y').to_euler()
    # backdrop with a faint warm glow
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
    me = bpy.data.meshes.new('backdrop'); bm.to_mesh(me); bm.free()
    bd = W.link(bpy.data.objects.new('backdrop', me)); bd.location = (0, 2.2, 0.2)
    bd.rotation_euler = (math.radians(90), 0, 0); bd.scale = (14, 9, 1)
    bdm = W.new_mat('backdrop_m'); nt = bdm.node_tree
    for n_ in list(nt.nodes):
        if n_.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n_)
    out = [n_ for n_ in nt.nodes if n_.type == 'OUTPUT_MATERIAL'][0]
    tc = nt.nodes.new('ShaderNodeTexCoord'); gr = nt.nodes.new('ShaderNodeTexGradient'); gr.gradient_type = 'SPHERICAL'
    nt.links.new(tc.outputs['Object'], gr.inputs['Vector'])
    pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.5
    nt.links.new(gr.outputs['Fac'], pw.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.09
    nt.links.new(pw.outputs[0], mul.inputs[0])
    em2 = nt.nodes.new('ShaderNodeEmission'); em2.inputs['Color'].default_value = (1.0, 0.5, 0.18, 1)
    nt.links.new(mul.outputs[0], em2.inputs['Strength']); nt.links.new(em2.outputs[0], out.inputs['Surface'])
    bd.data.materials.append(bdm)
    # lights: warm key, two rims, soft fill, a glint sweeping across the gold
    W.area_light('key', (-5, -9, 6.5), (math.radians(48), 0, math.radians(-29)), 1100, 6, (1.0, 0.86, 0.66))
    W.area_light('rimL', (-6, 3.5, 3.5), (math.radians(-62), 0, math.radians(-125)), 900, 3, (1.0, 0.7, 0.4))
    W.area_light('rimR', (6, 3.5, 3.5), (math.radians(-62), 0, math.radians(125)), 900, 3, (1.0, 0.7, 0.4))
    W.area_light('fill', (0, -13, -1), (math.radians(90), 0, 0), 260, 10, (0.9, 0.85, 0.8))
    W.area_light('sky_lift', (0, -3, cz + 0.3), (math.radians(90), 0, 0), 25, 2.5, (0.55, 0.65, 1.0))
    gl = W.area_light('glint', (-8, -6.5, 2.2), (math.radians(82), 0, math.radians(-52)), 2600, 0.8, (1.0, 0.95, 0.85))
    gl.keyframe_insert('location', frame=1)
    gl.location = (8, -6.5, 2.2); gl.keyframe_insert('location', frame=N2)
    cam = W.camera((0, -12.6, -0.15), (0, 0, -0.2), lens=35, fstop=16)
    cam.location = (0, -12.6, -0.15); cam.keyframe_insert('location', frame=1)
    cam.location = (0, -12.0, -0.12); cam.keyframe_insert('location', frame=N2)
    render_frames('ident2', per_frame=build, n=N2)


if __name__ == '__main__':
    {'hook': hook, 'ident': ident, 'ident2': ident2}[sys.argv[1]]()
