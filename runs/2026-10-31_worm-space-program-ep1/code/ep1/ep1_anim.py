"""Episode 1 animatic (stage 2): the 13 story shots that follow the approved intro. Cycles on the Colab GPU + OIDN.
Worms are rebuilt every frame from spline control points (tail -> head), like intro.py does:
the head swells and nods with the worm's own voice (loudness from out/ep1_voices_env.json),
crawling is a ring wave travelling along the body. No keyframes: every frame is set up in code, then rendered.
usage: blender -b -P ep1_anim.py -- <shot ...|all>      frames already on disk are skipped (resume after a reset)
env:   W, H, SAMPLES, BOUNCES, FRAMES="13,20" (only these output frames), OUTDIR (default animatic/frames), CSV,
       FPS=24 for the final: output frame F shows animatic time 1 + (F-1)*12/FPS, so all timing stays as approved"""
import os, math, json, time, random, bisect
import boot
import bpy, bmesh
from mathutils import Vector, Quaternion, Matrix, noise
import wsp_lib as W
import shots as S1
import ep1_timing as TM

HERE = boot.HERE
OUT = os.environ.get('OUTDIR', os.path.join(HERE, 'animatic', 'frames'))
CSV = os.environ.get('CSV', os.path.join(HERE, 'animatic', 'render_times_animatic.csv'))
RES = (int(os.environ.get('W', 960)), int(os.environ.get('H', 540)))
SAMPLES = int(os.environ.get('SAMPLES', 16))
BOUNCES = int(os.environ.get('BOUNCES', 4))
OUT_FPS = int(os.environ.get('FPS', TM.FPS))
SUB = OUT_FPS // TM.FPS                      # output frames per animatic frame (1 animatic, 2 final)
SHAFT = (2.2, 2.2)
ROCKET = (2.2, 2.4, 0.55)
CAP0, CAPF = Vector((0.15, 0.55, 0.0)), Vector((-1.3, -0.75, 0.0))    # the extra cap before / after the tail flick
CTRL = (-2.4, 0.6, 0.25)                                               # control pebble
TH_LOC, TH_ROT = (-0.15, -0.15, 0.15), (0.0, math.radians(84), math.radians(6))   # thimble on its side, mouth to -x
_ENV = os.path.join(HERE, 'out', 'ep1_voices_env.json')
ENV = json.load(open(_ENV)) if os.path.exists(_ENV) else {}
EV = {k: TM.frame(v) for k, v in TM.EV.items()}
RANGE = {n: (a, b) for n, a, b in TM.SHOTS}


# ---------------------------------------------------------------- small helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(x):
    x = clamp(x); return x * x * (3 - 2 * x)


def ramp(f, f0, f1):
    return smooth((f - f0) / max(1e-6, f1 - f0))


def mix(a, b, t):
    if isinstance(a, (int, float)):
        return a + (b - a) * t
    return Vector(a).lerp(Vector(b), t)


def keyed(f, keys):
    """smooth interpolation through [(frame, value), ...]; values are numbers or 3-vectors"""
    if f <= keys[0][0]:
        v = keys[0][1]
    elif f >= keys[-1][0]:
        v = keys[-1][1]
    else:
        for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
            if f <= f1:
                v = mix(v0, v1, smooth((f - f0) / (f1 - f0))); break
    return v if isinstance(v, (int, float)) else Vector(v)


def voice(who, f):
    """loudness at animatic frame f (may be fractional in the 24 fps final)"""
    a = ENV.get(who)
    if not a or not 1 <= f <= len(a):
        return 0.0
    i = int(f) - 1; t = f - int(f)
    return a[i] if t == 0 or i + 1 >= len(a) else a[i] * (1 - t) + a[i + 1] * t


def hide(obs, flag=True):
    for ob in obs:
        ob.hide_render = flag
        for c in ob.children_recursive:
            c.hide_render = flag


def new_scene(world=0.3):
    W.reset(); W.world_night(world, stars=False)
    W.render_settings(RES[0], RES[1], SAMPLES, bounces=BOUNCES)
    sc = bpy.context.scene
    sc.cycles.adaptive_threshold = float(os.environ.get('ADAPTIVE', 0.05))
    sc.render.use_persistent_data = True
    return sc


def ico_mesh(name, r, sub=1):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def swarm(name, n, me, mat):
    """n objects sharing one small mesh (sparks, clods, dust)"""
    me.materials.append(mat)
    obs = []
    for i in range(n):
        ob = W.link(bpy.data.objects.new(f'{name}{i}', me)); ob.visible_shadow = False; obs.append(ob)
    return obs


def resample_ctrl(ctrl, n=9):
    pts, _ = W.resample(W.catmull([Vector(p) for p in ctrl], 10), n)
    return pts


# ---------------------------------------------------------------- worms
KIND = {
    'hero': dict(R=0.11, band=(0.70, 0.79), taper=0.42, z=0.11, mat=lambda: W.mat_worm('worm')),
    'skeptic': dict(R=0.15, band=(0.66, 0.77), taper=0.5, z=0.15, mat=lambda: W.mat_worm('skeptic_m', pale=0.45)),
    'helper': dict(R=0.085, band=(0.70, 0.78), taper=0.42, z=0.085, mat=lambda: W.mat_worm('helper_m', body=(0.22, 0.06, 0.05))),
    'helper2': dict(R=0.08, band=(0.70, 0.78), taper=0.42, z=0.08, mat=lambda: W.mat_worm('helper2_m', body=(0.27, 0.08, 0.055))),
}


def worm_mesh(name, ctrl, k, mat, pulse=0.0, wave=None, segs=96, groove=0.045, flatten=0.12):
    """wsp_lib.worm() plus two animation inputs: pulse (head swells while the worm talks), wave (crawl)."""
    R, (b0, b1), ht = k['R'], k['band'], k['taper']

    def radius(u, L):
        r = R
        r *= 0.35 + 0.65 * min(1.0, u / 0.10) ** 0.6
        if u > 0.80:
            r *= 1.0 - (1 - ht) * ((u - 0.80) / 0.20) ** 1.4
        e = min(u, 1 - u)
        if e < 0.018:
            r *= math.sqrt(max(0.0, 1 - ((0.018 - e) / 0.018) ** 2))
        if b0 < u < b1:
            r *= 1.0 + 0.10 * math.sin(math.pi * (u - b0) / (b1 - b0))
        fr = (u * segs) % 1.0; d = min(fr, 1 - fr)
        r *= 1.0 - groove * math.exp(-(d / 0.12) ** 2)
        if pulse and u > 0.76:
            r *= 1.0 + 0.32 * pulse * math.sin(math.pi * min(1.0, (u - 0.76) / 0.22)) ** 0.8
        if wave is not None and u < 0.9:
            r *= 1.0 + 0.07 * math.sin(2 * math.pi * (u * 3.5 - wave))
        return r

    def bandf(u):
        return math.sin(math.pi * (u - b0) / (b1 - b0)) ** 0.5 if b0 < u < b1 else 0.0

    ob, pts, T = W.tube(name, ctrl, radius, ring=30, samples=260, attr_fn=bandf, flatten=flatten)
    ob.data.materials.append(mat)
    W.subsurf(ob, 1, 1)
    return ob, pts, T


class Worm:
    def __init__(self, name, kind, helmet=False):
        self.name, self.kind, self.k = name, kind, KIND[kind]
        self.mat = self.k['mat']()
        self.ob, self.pts, self.T = None, None, None
        self.helmet = W.thimble(name + '_helmet') if helmet else None

    def clear(self):
        if self.ob:
            me = self.ob.data
            bpy.data.objects.remove(self.ob, do_unlink=True); bpy.data.meshes.remove(me)
            self.ob = None

    def set(self, ctrl, pulse=0.0, wave=None, tilt=0.25, helmet_on=True):
        self.clear()
        if ctrl is None or len(ctrl) < 2:
            if self.helmet and helmet_on:
                self.helmet.hide_render = True
            return
        self.ob, self.pts, self.T = worm_mesh(self.name, [Vector(p) for p in ctrl], self.k, self.mat, pulse, wave)
        if self.helmet and helmet_on:
            tip, t = self.pts[-1], self.T[-1]
            self.helmet.hide_render = False
            self.helmet.location = tip - t * 0.17
            e = t.to_track_quat('Z', 'Y').to_euler(); e.y += tilt          # as shots.hero()
            self.helmet.rotation_euler = e

    def head(self):
        return self.pts[-1].copy(), self.T[-1].copy()


def body(floor, top, look, z, head_len=0.3, nod=0.0):
    """floor: tail .. neck base on the ground (x, y); top: the raised neck (x, y, z); the head aims at `look`.
    nod tips the head down (the worm talks or agrees). Returns spline control points tail -> head."""
    pts = [Vector((p[0], p[1], z)) for p in floor]
    top = Vector(top); base = pts[-1]
    mid = base.lerp(top, 0.5); mid.z = z + (top.z - z) * 0.55
    d = (Vector(look) - top).normalized() + Vector((0, 0, -0.7 * nod))
    return pts + [mid, top, top + d.normalized() * head_len]


class Track:
    """a path on the floor; a crawling worm occupies the arc [s_head - L, s_head]"""
    def __init__(self, pts):
        self.d, _ = W.resample(W.catmull([Vector(p) for p in pts], 16), 400)
        self.cum = [0.0]
        for i in range(1, len(self.d)):
            self.cum.append(self.cum[-1] + (self.d[i] - self.d[i - 1]).length)
        self.L = self.cum[-1]

    def at(self, s):
        d, c = self.d, self.cum
        if s <= 0:
            return d[0] + (d[0] - d[1]).normalized() * (-s)
        if s >= c[-1]:
            return d[-1] + (d[-1] - d[-2]).normalized() * (s - c[-1])
        i = bisect.bisect_left(c, s); t = (s - c[i - 1]) / max(1e-9, c[i] - c[i - 1])
        return d[i - 1].lerp(d[i], t)

    def s_near(self, p):
        p = Vector(p); i = min(range(len(self.d)), key=lambda j: (self.d[j] - p).length)
        return self.cum[i]

    def span(self, a, b, n=9):
        return [self.at(a + (b - a) * i / (n - 1)) for i in range(n)]


# ---------------------------------------------------------------- camera
class Cam:
    def __init__(self, loc, target, lens=45, fstop=4.0):
        self.cam = W.camera(tuple(loc), tuple(target), lens=lens, fstop=fstop)

    def set(self, f, loc, target, lens=None, focus=None, drift=0.012, shake=0.0):
        """hand-held drift by noise; focus = a point to keep sharp (default: the target)"""
        loc, target = Vector(loc), Vector(target)
        n = noise.noise_vector(Vector((f * 0.06, 3.7, 1.1))) * drift
        if shake:
            n += noise.noise_vector(Vector((f * 1.9, 9.1, 4.4))) * shake
        c = self.cam
        c.location = loc + n
        W.look_at(c, target + n * 0.5)
        if lens:
            c.data.lens = lens
        c.data.dof.focus_distance = ((Vector(focus) if focus is not None else target) - c.location).length


# ---------------------------------------------------------------- render loop
def fpath(f):
    return os.path.join(OUT, f'{f:04d}.png')


def render_shot(name, build, frame):
    f0, f1 = RANGE[name]
    todo = list(range((f0 - 1) * SUB + 1, f1 * SUB + 1))          # output frame numbers
    if os.environ.get('FRAMES'):
        sel = {int(x) for x in os.environ['FRAMES'].split(',')}
        todo = [f for f in todo if f in sel]
    todo = [f for f in todo if not os.path.exists(fpath(f))]
    if not todo:
        print('SKIP', name, flush=True); return
    os.makedirs(OUT, exist_ok=True); os.makedirs(os.path.dirname(CSV), exist_ok=True)
    t0 = time.time(); build(); print('BUILD', name, round(time.time() - t0, 1), flush=True)
    sc = bpy.context.scene
    for f in todo:
        frame(1 + (f - 1) / SUB if SUB > 1 else f)
        sc.render.filepath = fpath(f)
        t0 = time.time(); bpy.ops.render.render(write_still=True); dt = round(time.time() - t0, 2)
        new = not os.path.exists(CSV)
        with open(CSV, 'a') as fh:
            if new:
                fh.write('frame,seconds,gpu\n')
            fh.write(f'{f},{dt},{boot.GPU_NAME}\n')
        print('FRAME', name, f, dt, flush=True)


# ---------------------------------------------------------------- shared sets
def workshop(ff=True, world=0.3, crumbs=True):
    new_scene(world)
    return W.workshop(SHAFT, fireflies=ff, mars=False, crumbs=crumbs)


def charcoal():
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.05, radius2=0.04, depth=0.32)
    me = bpy.data.meshes.new('charcoal'); bm.to_mesh(me); bm.free()
    ob = W.link(bpy.data.objects.new('charcoal', me))
    ob.data.materials.append(W.mat_simple('charcoal_m', (0.02, 0.018, 0.017), 0.9))
    return ob


def spot(name, loc, target, energy, size=30, blend=0.5, color=(1.0, 1.0, 1.0), soft=0.3):
    L = bpy.data.lights.new(name, 'SPOT'); L.energy = energy; L.color = color
    L.spot_size = math.radians(size); L.spot_blend = blend; L.shadow_soft_size = soft
    ob = W.link(bpy.data.objects.new(name, L)); ob.location = loc
    W.look_at(ob, target)
    return ob


def fireball_mat(name='fire_m'):
    """smooth fireball (approved by Dima on frame 409, 31.10; back in v3): warm yellow-orange core,
    redder and see-through toward the rim, soft edge. returns (material, emission node, fade value: 0 ball, 1 gone)"""
    m = W.new_mat(name); nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    ramp_ = nt.nodes.new('ShaderNodeValToRGB'); cr = ramp_.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (1.0, 0.62, 0.16, 1)
    cr.elements[1].position = 1.0; cr.elements[1].color = (0.7, 0.05, 0.01, 1)
    cr.elements.new(0.35).color = (1.0, 0.33, 0.05, 1)
    em = nt.nodes.new('ShaderNodeEmission'); tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    edge = nt.nodes.new('ShaderNodeMath'); edge.operation = 'POWER'; edge.inputs[1].default_value = 0.4
    fade = nt.nodes.new('ShaderNodeValue'); fade.outputs[0].default_value = 0.0
    add = nt.nodes.new('ShaderNodeMath'); add.operation = 'ADD'; add.use_clamp = True
    mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lw.outputs['Facing'], ramp_.inputs['Fac']); nt.links.new(ramp_.outputs['Color'], em.inputs['Color'])
    nt.links.new(lw.outputs['Facing'], edge.inputs[0])
    nt.links.new(edge.outputs[0], add.inputs[0]); nt.links.new(fade.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], mx.inputs['Fac'])
    nt.links.new(em.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs['Surface'])
    return m, em, fade


def soft_puff_mat(name, color, scale=1.8):
    """soft volumetric puff for an object of radius 1: density fades smoothly to zero well inside the mesh
    (no facets, blurred edge) and is broken up by 4D noise that drifts with time.
    returns (material, density value node, noise W value node)"""
    m = W.new_mat(name); nt = m.node_tree; L = nt.links.new
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    tc = nt.nodes.new('ShaderNodeTexCoord')
    w = nt.nodes.new('ShaderNodeValue')
    # low-frequency warp of the radius, so the outline billows instead of reading as a ball
    wn = nt.nodes.new('ShaderNodeTexNoise'); wn.noise_dimensions = '4D'; wn.inputs['Scale'].default_value = 0.9
    L(tc.outputs['Object'], wn.inputs['Vector']); L(w.outputs[0], wn.inputs['W'])
    wc = nt.nodes.new('ShaderNodeVectorMath'); wc.operation = 'SUBTRACT'; wc.inputs[1].default_value = (0.5, 0.5, 0.5)
    L(wn.outputs['Color'], wc.inputs[0])
    ws = nt.nodes.new('ShaderNodeVectorMath'); ws.operation = 'SCALE'; ws.inputs['Scale'].default_value = 0.6
    L(wc.outputs['Vector'], ws.inputs[0])
    wa = nt.nodes.new('ShaderNodeVectorMath'); wa.operation = 'ADD'; L(tc.outputs['Object'], wa.inputs[0]); L(ws.outputs['Vector'], wa.inputs[1])
    ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; L(wa.outputs['Vector'], ln.inputs[0])
    fall = nt.nodes.new('ShaderNodeMapRange'); fall.clamp = True
    fall.inputs['From Min'].default_value, fall.inputs['From Max'].default_value = 0.2, 0.92
    fall.inputs['To Min'].default_value, fall.inputs['To Max'].default_value = 1.0, 0.0
    L(ln.outputs['Value'], fall.inputs['Value'])
    soft = nt.nodes.new('ShaderNodeMath'); soft.operation = 'POWER'; soft.inputs[1].default_value = 1.6
    L(fall.outputs['Result'], soft.inputs[0])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'
    nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = 5.0; nz.inputs['Roughness'].default_value = 0.6
    L(tc.outputs['Object'], nz.inputs['Vector']); L(w.outputs[0], nz.inputs['W'])
    bill = nt.nodes.new('ShaderNodeMapRange'); bill.clamp = True
    bill.inputs['From Min'].default_value, bill.inputs['From Max'].default_value = 0.3, 0.62
    L(nz.outputs['Fac'], bill.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; L(soft.outputs[0], mul.inputs[0]); L(bill.outputs['Result'], mul.inputs[1])
    dens = nt.nodes.new('ShaderNodeValue'); dens.outputs[0].default_value = 0.0
    d = nt.nodes.new('ShaderNodeMath'); d.operation = 'MULTIPLY'; L(mul.outputs[0], d.inputs[0]); L(dens.outputs[0], d.inputs[1])
    sc_ = nt.nodes.new('ShaderNodeVolumeScatter'); sc_.inputs['Color'].default_value = (*color, 1)
    sc_.inputs['Anisotropy'].default_value = 0.3; L(d.outputs[0], sc_.inputs['Density'])
    ab = nt.nodes.new('ShaderNodeVolumeAbsorption'); ab.inputs['Color'].default_value = (*color, 1)
    da = nt.nodes.new('ShaderNodeMath'); da.operation = 'MULTIPLY'; da.inputs[1].default_value = 0.5; L(d.outputs[0], da.inputs[0])
    L(da.outputs[0], ab.inputs['Density'])
    add = nt.nodes.new('ShaderNodeAddShader'); L(sc_.outputs[0], add.inputs[0]); L(ab.outputs[0], add.inputs[1])
    L(add.outputs[0], out.inputs['Volume'])
    return m, dens, w


def puff(name, mat):
    ob = W.link(bpy.data.objects.new(name, ico_mesh(name + '_me', 1.0, 3)))
    ob.data.materials.append(mat); ob.visible_shadow = False
    return ob


def point_along(ob, p, d):
    ob.location = p; ob.rotation_euler = Vector(d).to_track_quat('Z', 'Y').to_euler()


def blueprint_set():
    workshop()
    S1.clear_floor(-0.2, 0.8, 1.15, 1.25, zmax=-0.02)
    S1.paper((-0.2, 0.8, 0.05), 0.12)
    W.firefly('ff_paper', (1.3, 2.1, 2.3), energy=10.0)
    W.area_light('key', (-2.5, -3.5, 4), (math.radians(45), 0, math.radians(-30)), 90, 3, (1.0, 0.8, 0.55))
    W.area_light('rim', (0.8, 4.2, 3.0), (math.radians(-62), 0, math.radians(175)), 140, 3, (0.6, 0.75, 1.0))


PAPER_LOOK = Vector((-0.2, 0.8, 0.05))
SK_BLUE = [(2.6, 2.6), (2.0, 2.9), (1.5, 2.45)]
HP_BLUE = [(-2.2, 3.4), (-1.6, 3.0), (-1.2, 2.6)]
HP2_BLUE = [(1.9, -0.9), (1.5, -0.5), (1.1, -0.2)]


# ---------------------------------------------------------------- A: the blueprint
def a1_scribble():
    st = {}

    def build():
        blueprint_set()
        st['hero'] = Worm('hero', 'hero', helmet=True); st['sk'] = Worm('skeptic', 'skeptic')
        st['hp'] = Worm('helper', 'helper'); st['hp2'] = Worm('helper2', 'helper2')
        st['coal'] = charcoal()
        st['cam'] = Cam((1.0, -3.1, 1.05), (-0.5, 1.0, 0.35), lens=40, fstop=4.0)

    def frame(f):
        p = voice('hero', f)
        proud = ramp(f, 8, 11)                       # scribbling, then the head comes up to the team
        q = Vector((-0.45 + 0.28 * math.sin(f * 1.35), 0.82 + 0.22 * math.sin(f * 0.9 + 1.0), 0.06))
        look = q.lerp(Vector((1.1, 2.1, 0.95)), proud)
        top = Vector((-1.2, 0.8, 0.42 + 0.2 * proud))
        hl = mix(max(0.22, (q - top).length - 0.3), 0.3, proud)
        st['hero'].set(body([(-3.4, 1.8), (-2.6, 1.2), (-1.9, 1.3), (-1.5, 0.95)], top, look, 0.11, hl, 0.35 * p), pulse=p)
        tip, t = st['hero'].head()
        point_along(st['coal'], tip + t * 0.13, t)
        st['sk'].set(body(SK_BLUE, (1.22, 2.1, 0.85), PAPER_LOOK, 0.15, 0.36), pulse=voice('skeptic', f))
        st['hp'].set(body(HP_BLUE, (-1.1, 2.35, 0.5 + 0.06 * math.sin(f * 1.4)), q, 0.085, 0.24))
        st['hp2'].set(body(HP2_BLUE, (0.85, 0.05, 0.38), PAPER_LOOK, 0.08, 0.22))
        st['cam'].set(f, (1.0, -3.1, 1.05), (-0.5, 1.0, 0.35), focus=(-1.0, 0.8, 0.45))
    return build, frame


def a2_blueprint():
    st = {}

    def build():
        blueprint_set()
        W.area_light('top', (-0.2, 0.6, 3.6), (0, 0, 0), 60, 2.5, (1.0, 0.9, 0.75))
        st['hero'] = Worm('hero', 'hero', helmet=True)
        coal = charcoal(); coal.location = (-1.05, 0.2, 0.05); coal.rotation_euler = (math.pi / 2, 0, 0.6)
        st['cam'] = Cam((-0.2, -0.5, 2.65), (-0.22, 0.85, 0.05), lens=32, fstop=5.6)

    def frame(f):
        p = voice('hero', f)
        spots = [(-0.3, 1.15), (-0.18, 0.95), (-0.34, 1.3)]
        sx, sy = spots[int(f // 4) % 3]
        tap = Vector((sx, sy, 0.06 + 0.1 * max(0.0, math.sin(f * 2.2))))
        top = Vector((-1.2, 1.05, 0.44))
        st['hero'].set(body([(-3.0, 1.6), (-2.3, 1.3), (-1.7, 1.15)], top, tap, 0.11, (tap - top).length - 0.04, 0.3 * p), pulse=p)
        st['cam'].set(f, (-0.2, -0.5, 2.65), (-0.22, 0.85, 0.05), drift=0.008)
    return build, frame


def a3_skeptic():
    st = {}

    def build():
        blueprint_set()
        W.area_light('skey', (-0.8, -1.0, 1.6), (math.radians(60), 0, math.radians(-35)), 45, 1.5, (1.0, 0.82, 0.6))
        st['sk'] = Worm('skeptic', 'skeptic'); st['hp'] = Worm('helper', 'helper')
        st['cam'] = Cam((0.3, -0.75, 0.7), (1.18, 2.0, 0.62), lens=50, fstop=2.8)

    def frame(f):
        p = voice('skeptic', f)
        low = ramp(f, 26, 36)                         # slow, all the way down
        top = Vector((1.25, 2.12, 0.88 - 0.32 * low))
        look = mix(PAPER_LOOK + Vector((0, 0, 0.2)), Vector((0.95, 1.5, -0.4)), low)
        st['sk'].set(body(SK_BLUE, top, look, 0.15, 0.36, 0.35 * p), pulse=p)
        st['hp'].set(body(HP_BLUE, (-1.1, 2.35, 0.5), PAPER_LOOK, 0.085, 0.24))
        st['cam'].set(f, (0.3, -0.75, 0.7), (1.18, 2.0, 0.62), focus=top)
    return build, frame


# ---------------------------------------------------------------- B: the build montage
def b1_can():
    st = {}
    J1, J2 = EV['jerk1'], EV['jerk2']

    def build():
        workshop()
        S1.clear_floor(-0.8, 2.4, 2.4, 1.4, zmax=0.0)
        st['can'] = W.tin_can('can')
        st['w'] = [Worm('helper', 'helper'), Worm('hero', 'hero', helmet=True), Worm('helper2', 'helper2')]
        W.area_light('key', (-4.0, -3.0, 3.5), (math.radians(55), 0, math.radians(-50)), 160, 3, (1.0, 0.8, 0.55))
        st['cam'] = Cam((-2.3, -0.5, 1.15), (-2.0, 2.4, 0.35), lens=30, fstop=4.0)

    def frame(f):
        # Dima 31.10: harder jerks with a wind-up: slow deep pull-back, one-frame snap, the can jumps and rocks
        cx = keyed(f, [(37, -1.3), (J1, -1.3), (J1 + 1, -0.8), (J1 + 3, -0.68), (J2, -0.68), (J2 + 1, -0.12), (J2 + 3, 0.0), (58, 0.0)])
        wob = sum(0.13 * math.exp(-(f - j) / 3.0) * math.sin((f - j) * 1.5) for j in (J1, J2) if f >= j)
        can = st['can']; can.location = (cx, 2.4, 0.0); can.rotation_euler = (0.0, -wob, 0.0)
        # wind 1 = fully pulled back and coiled, -0.35 = lunge past the contact point on the snap
        wind = keyed(f, [(37, 0), (38, 0), (J1 - 1, 1), (J1, -0.35), (J1 + 3, 0), (J2 - 6, 0), (J2 - 1, 1), (J2, -0.35), (J2 + 3, 0), (58, 0)])
        for w, dy, who in zip(st['w'], (-0.45, 0.0, 0.45), ('helper', 'hero', 'helper2')):
            yy = 2.4 + dy
            hx = cx - math.sqrt(1 - dy * dy) - 0.02 - 0.55 * max(0.0, wind) - 0.1 * min(0.0, wind)
            a = 0.05 + 0.3 * max(0.0, wind)                                 # body coils like a spring
            z = w.k['z']; p = voice(who, f)
            floor = [(hx - 2.5, yy + a), (hx - 1.9, yy - a), (hx - 1.3, yy + a), (hx - 0.75, yy - a * 0.5)]
            top = (hx - 0.32, yy, 0.26 + 0.18 * max(0.0, wind))            # head rears up on the wind-up
            w.set(body(floor, top, (hx + 0.6, yy, 0.22 - 0.1 * max(0.0, wind)), z, 0.3, 0.3 * p), pulse=p, wave=f * 0.3)
        shake = sum(0.05 * math.exp(-(f - j) / 1.5) for j in (J1, J2) if f >= j)
        st['cam'].set(f, (-2.3 + 0.4 * (cx + 1.3), -0.5, 1.15), (-2.0 + 0.4 * (cx + 1.3), 2.4, 0.35), focus=(cx - 1.2, 2.4, 0.3), shake=shake)
    return build, frame


def b2_caps():
    st = {}

    def build():
        workshop()
        S1.clear_floor(1.2, 1.0, 3.2, 1.0, zmax=0.0)
        st['caps'] = []
        for nm, col in (('cap_r', (0.75, 0.08, 0.06)), ('cap_b', (0.08, 0.25, 0.7)), ('cap_g', (0.85, 0.65, 0.08))):
            c = W.bottle_cap(nm, col, r=0.32, h=0.13); c.rotation_mode = 'ZXY'; st['caps'].append(c)
        st['w'] = [Worm('helper', 'helper'), Worm('helper2', 'helper2'), Worm('hero', 'hero', helmet=True)]
        W.area_light('key', (-1.0, -4.0, 3.0), (math.radians(60), 0, math.radians(-15)), 160, 4, (1.0, 0.8, 0.55))
        st['cam'] = Cam((0.4, -3.0, 0.42), (0.6, 1.0, 0.35), lens=30, fstop=4.0)

    def frame(f):
        u = (f - 59) / 18
        lanes = ((1.9, -0.7, 0.45), (3.0, 0.3, 1.25), (4.0, 1.2, 2.0))     # x from, x to, y
        for c, w, (x0, x1, y), who in zip(st['caps'], st['w'], lanes, ('helper', 'helper2', 'hero')):
            x = x0 + (x1 - x0) * u
            c.location = (x, y, 0.33); c.rotation_euler = (math.pi / 2, 0.0, (x0 - x) / 0.32)
            z = w.k['z']; hx = x + 0.32 + 0.05; p = voice(who, f)
            floor = [(hx + 2.6, y + 0.12), (hx + 1.9, y - 0.1), (hx + 1.25, y + 0.1), (hx + 0.7, y)]
            w.set(body(floor, (hx + 0.32, y - 0.02, 0.3), (x, y - 0.02, 0.3), z, 0.3, 0.3 * p), pulse=p, wave=f * 0.35)
        st['cam'].set(f, (0.4, -3.0, 0.42), (0.9 - 0.6 * u, 1.0, 0.35), focus=(0.6 - 1.2 * u, 0.45, 0.3))
    return build, frame


def rocket_set(state='assembled'):
    root, parts = W.rocket(state, loc=ROCKET)
    return root, parts


def b3_legs():
    st = {}
    a = 2 * math.pi * 2 / 3 + math.pi / 3
    rh = Vector((math.cos(a), math.sin(a), 0)); th = Vector((-rh.y, rh.x, 0))
    k_axis = Vector((-math.sin(a), math.cos(a), 0))
    base = Vector((ROCKET[0], ROCKET[1], 0)) + rh * 1.35

    def build():
        workshop()
        root, parts = rocket_set()
        hide([parts['cone'], parts['clip']] + parts['caps'])
        leg = parts['legs'][2]; leg.rotation_mode = 'QUATERNION'; st['leg'] = leg
        st['hero'] = Worm('hero', 'hero', helmet=True)
        W.area_light('key', tuple(base - th * 3 + Vector((0, 0, 3))), (math.radians(55), 0, math.radians(-20)), 150, 3, (1.0, 0.8, 0.55))
        cl = base - th * 3.4 + rh * 1.0 + Vector((0, 0, 0.75)); tg = base + rh * 0.3 + Vector((0, 0, 0.6))
        st['cl'], st['tg'] = cl, tg
        st['cam'] = Cam(cl, tg, lens=35, fstop=4.0)

    def frame(f):
        ang = keyed(f, [(78, math.pi / 2), (82, math.pi / 2), (85, 1.22), (87, 1.18), (89, -0.52), (91, -0.32), (93, -0.38)])
        q = Quaternion(k_axis, ang); st['leg'].rotation_quaternion = q
        d = q @ Vector((0, 0, 1)); P = base + d * 0.95
        top = Vector((P.x, P.y, 0)) + rh * 0.45 + Vector((0, 0, max(0.28, P.z * 0.8)))
        proud = ramp(f, 91, 94)
        look = P.lerp(Vector((ROCKET[0], ROCKET[1], 3.0)), proud)
        p = voice('hero', f)
        floor = [base + rh * 3.4 + th * 0.3, base + rh * 2.7 - th * 0.1, base + rh * 2.0 + th * 0.1, base + rh * 1.45]
        hl = mix(min(0.32, max(0.15, (P - top).length)), 0.3, proud)
        st['hero'].set(body([(v.x, v.y) for v in floor], top, look, 0.11, hl, 0.3 * p), pulse=p, wave=f * 0.2)
        st['cam'].set(f, st['cl'], st['tg'], focus=P)
    return build, frame


def b4_weld():
    st = {}
    a = 2 * math.pi * 2 / 3 + math.pi / 3
    rh = Vector((math.cos(a), math.sin(a), 0)); th = Vector((-rh.y, rh.x, 0))
    Wp = Vector((ROCKET[0], ROCKET[1], 0)) + rh * 1.0 + Vector((0, 0, 0.87))
    rnd = random.Random(4)
    sparks_v = [Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 1.0))).normalized() * rnd.uniform(1.5, 3.5) + rh * 1.2
                for _ in range(48)]

    def build():
        workshop()
        root, parts = rocket_set(); hide([parts['cone']])
        st['hero'] = Worm('hero', 'hero', helmet=True)
        st['torch'], st['torch_L'] = W.firefly('torch', tuple(Wp), energy=3.0)
        L = bpy.data.lights.new('weld', 'POINT'); L.color = (0.85, 0.9, 1.0); L.shadow_soft_size = 0.02
        st['weld'] = W.link(bpy.data.objects.new('weld', L)); st['weld'].location = Wp + rh * 0.05
        st['sparks'] = swarm('spark', len(sparks_v), ico_mesh('spark_me', 0.012), W.mat_emit('spark_e', (1.0, 0.75, 0.35), 15.0))
        W.area_light('key', tuple(Wp + rh * 2 - th * 2 + Vector((0, 0, 2))), (math.radians(50), 0, math.radians(20)), 60, 2, (1.0, 0.8, 0.55))
        st['cl'] = Wp + rh * 2.3 - th * 1.15 + Vector((0, 0, -0.25))
        st['cam'] = Cam(st['cl'], Wp, lens=50, fstop=2.8)

    def frame(f):
        top = Wp + rh * 0.5 + Vector((0, 0, -0.08 + 0.02 * math.sin(f * 1.3)))
        fl = Vector((Wp.x, Wp.y, 0))
        floor = [fl + rh * 3.0 + th * 0.35, fl + rh * 2.35 - th * 0.1, fl + rh * 1.75 + th * 0.05, fl + rh * 1.25]
        st['hero'].set(body([(v.x, v.y) for v in floor], top, Wp, 0.11, 0.28 + 0.03 * math.sin(f * 2.0)))
        tip, t = st['hero'].head()
        st['torch'].location = tip + t * 0.07; st['torch_L'].location = tip + t * 0.07
        st['weld'].data.energy = 15 + 30 * abs(math.sin(f * 2.7))
        for i, (ob, v) in enumerate(zip(st['sparks'], sparks_v)):
            age = ((f * 0.9 + i * 0.37) % 6) / 12.0
            ob.location = Wp + v * age + Vector((0, 0, -4.5 * age * age))
            ob.hide_render = age > 0.4 or ob.location.z < 0.02
        st['cam'].set(f, st['cl'], Wp, drift=0.01)
    return build, frame


def b5_foil():
    st = {}
    c = Vector((ROCKET[0], ROCKET[1], 0))
    ztop = ROCKET[2] + 3.1

    def build():
        workshop()
        root, parts = rocket_set(); st['cone'] = parts['cone']
        st['hero'] = Worm('hero', 'hero', helmet=True)
        W.area_light('key', (0.0, -1.0, 5.5), (math.radians(40), 0, math.radians(-30)), 220, 3, (1.0, 0.82, 0.6))
        st['cam'] = Cam((0.6, -1.6, 5.4), (2.2, 2.4, 3.7), lens=32, fstop=4.0)

    def frame(f):
        u = ramp(f, 112, 125)
        j = 0.05 * math.sin(f * 2.3)
        st['cone'].scale = (1.0 + j, 1.0 - j, 0.18 + 0.82 * u)
        ang = -1.2 + (f - 112) * 0.42                       # the hero runs round the rim, wrapping foil
        arc = 3.0 / 1.14
        ctrl = []
        for i in range(9):
            t = ang - arc + arc * i / 8
            ctrl.append(c + Vector((1.14 * math.cos(t), 1.14 * math.sin(t), ztop - 0.02 + (0.18 if i == 8 else 0.06 if i == 7 else 0))))
        st['hero'].set(ctrl, wave=f * 0.4)
        st['cam'].set(f, (0.6, -1.6, 5.4), (2.2, 2.4, 3.7), focus=c + Vector((0, -1.1, ztop)))
    return build, frame


# ---------------------------------------------------------------- C: the extra cap
def c_cap():
    """four cuts (Dima 31.10): cap, rocket, cap, tail flick. Hero big and the brightest thing in frame,
    the cap beside him (never in front of him), the rocket behind him."""
    st = {}
    H = Vector((0.95, 0.2, 0.55))                                          # hero's raised head
    floorA = [(2.4, 0.0), (1.9, -0.15), (1.45, -0.1), (1.15, 0.05)]       # body trails off to the right
    floorB = [(0.7, 1.05), (1.15, 1.2), (1.65, 1.05), (2.0, 0.7)]          # turned away, tail behind the cap
    cap_eye = CAP0 + Vector((0.25, -0.05, 0.2)); rocket_eye = Vector((2.2, 2.4, 4.2))
    push = (CAPF - CAP0).normalized()
    CUTS = [  # first frame, camera, target, lens, focus
        (127, (-0.32, -1.87, 0.45), (0.7, 0.4, 0.35), 35, H),             # 1 the cap: hero and cap side by side
        (135, (0.45, -0.55, 0.3), (1.35, 1.1, 1.5), 22, H),               # 2 the rocket: low, it towers behind him
        (142, (0.6, -1.3, 0.55), (0.5, 0.45, 0.3), 40, H),                # 3 the cap again, closer
        (148, (1.89, -1.37, 0.5), (0.8, 0.75, 0.3), 24, CAP0),            # 4 the tail flick, side on
    ]

    def build():
        workshop()
        rocket_set()
        st['cap'] = W.bottle_cap('extra_cap', (0.75, 0.08, 0.06), r=0.5, h=0.2)
        S1.clear_floor(-0.6, -0.1, 1.6, 1.3, zmax=0.0)
        W.area_light('key', (-3, -4, 3), (math.radians(55), 0, math.radians(-35)), 25, 3, (1.0, 0.8, 0.55))
        st['hkey'] = spot('hero_key', (0.1, -1.5, 1.7), H, 120, 40, 0.6, (1.0, 0.86, 0.68))
        st['hrim'] = spot('hero_rim', (1.7, 1.5, 1.4), H, 90, 30, 0.6, (0.75, 0.85, 1.0))
        st['hero'] = Worm('hero', 'hero', helmet=True)
        st['cam'] = Cam(CUTS[0][1], CUTS[0][2], lens=35, fstop=3.2)

    def frame(f):
        p = voice('hero', f)
        look = keyed(f, [(127, cap_eye), (134, cap_eye), (136, rocket_eye), (141, rocket_eye), (142, cap_eye), (147, cap_eye)])
        lean = ramp(f, 142, 146) * (1 - ramp(f, 147, 149))               # 3rd cut: he leans over the cap
        topA = H + Vector((-0.12, 0.08, -0.08)) * lean + Vector((0, 0, 0.08)) * ramp(f, 135, 137) * (1 - ramp(f, 141, 142))
        A = body(floorA, topA, look, 0.11, 0.3, 0.35 * p)
        B = body(floorB, (2.15, 0.35, 0.58), (2.9, 0.9, 0.8), 0.11, 0.3, 0.35 * p)
        turn = ramp(f, 148, 150)
        ctrl = [a.lerp(b, turn) for a, b in zip(A, B)]
        flick = keyed(f, [(149, 0), (EV['flick'], 1), (EV['flick'] + 2, 0.15), (156, 0)])
        ctrl[0] += Vector((push.x, push.y, 0)) * 0.45 * flick; ctrl[1] += Vector((push.x, push.y, 0)) * 0.18 * flick
        st['hero'].set(ctrl, pulse=p, tilt=0.45)
        s = keyed(f, [(EV['flick'], 0), (EV['flick'] + 1, 0.3), (156, 1.0)])
        st['cap'].location = CAP0.lerp(CAPF, s); st['cap'].rotation_euler = (0, 0, 0.3 + 2.4 * s)
        head = st['hero'].pts[-1]
        for L in (st['hkey'], st['hrim']):                                 # the hero's lights follow his head
            W.look_at(L, head)
        _, loc, tgt, lens, foc = [c for c in CUTS if c[0] <= f][-1]
        st['cam'].set(f, loc, tgt, lens=lens, focus=head if foc is H else foc, drift=0.008)
    return build, frame


# ---------------------------------------------------------------- D: countdown
HERO_CTRL_FLOOR = [(-0.6, 1.7), (-1.0, 1.4), (-1.4, 1.15), (-1.75, 1.0)]
SK_AFTER = [(0.9, 1.9), (0.4, 1.6), (-0.1, 1.3)]
SK_AFTER_TOP = (-0.3, 1.1, 0.85)


def control(lit=True):
    objs = W.control_pebble(CTRL, lit=(lit, lit, lit))
    return objs, objs[-1]


def set_leds(f, on):
    for i, o in enumerate(on):
        m = bpy.data.materials.get(f'ctrl_led{i}_e'); L = bpy.data.objects.get(f'ctrl_led{i}_L')
        if m:
            em = [n for n in m.node_tree.nodes if n.type == 'EMISSION'][0]
            em.inputs['Strength'].default_value = 7.0 if o else 0.0
            em.inputs['Color'].default_value = (1.0, 0.7, 0.25, 1) if o else (0.05, 0.04, 0.03, 1)
        if L:
            L.data.energy = 0.15 if o else 0.0


def d_count():
    st = {}
    btn_top = Vector((CTRL[0] + 0.15, CTRL[1] + 0.18, CTRL[2] + 0.26 + 0.115))
    leds = [Vector((CTRL[0] - 0.25 + 0.25 * i, CTRL[1] - 0.12, CTRL[2] + 0.3)) for i in range(3)]

    def build():
        workshop()
        rocket_set()
        objs, st['btn'] = control(); st['btn_z'] = st['btn'].location.z
        S1.clear_floor(CTRL[0], CTRL[1], 0.7, 0.6, zmax=0.0)
        st['hero'] = Worm('hero', 'hero', helmet=True); st['sk'] = Worm('skeptic', 'skeptic')
        W.area_light('key', (-3.5, -1.5, 2.2), (math.radians(60), 0, math.radians(-45)), 22, 2, (1.0, 0.8, 0.55))
        st['cam'] = Cam((-1.6, -2.6, 0.8), (-2.25, 0.65, 0.45), lens=40, fstop=2.8)

    def frame(f):
        set_leds(f, [f < EV['blu'], f < EV['mo'], f < EV['button']])
        p = voice('hero', f)
        i = 0 if f < EV['mo'] - 2 else 1 if f < EV['shlip'] - 2 else 2
        wind = keyed(f, [(EV['shlip'] - 1, 0), (EV['button'] - 1, 1), (EV['button'], 0)])
        hit = keyed(f, [(EV['button'] - 1, 0), (EV['button'], 1), (EV['button'] + 3, 1), (180, 0.6)])
        top = Vector((-2.05, 0.85, 0.72)) + Vector((0.1, 0.15, 0.25)) * wind + Vector((-0.05, -0.08, -0.14)) * hit
        look = leds[i].lerp(btn_top, max(wind, hit))
        hl = mix(0.3, (btn_top - top).length, hit)
        st['hero'].set(body(HERO_CTRL_FLOOR, top, look, 0.11, hl, 0.4 * p), pulse=p)
        st['btn'].location.z = st['btn_z'] - 0.04 * hit
        st['sk'].set(body(SK_AFTER, SK_AFTER_TOP, (-2.4, 0.6, 0.4), 0.15, 0.36))
        st['cam'].set(f, (-1.6, -2.6, 0.8), (-2.25, 0.65, 0.45), focus=leds[1])
    return build, frame


# ---------------------------------------------------------------- E: launch and explosion
TRK_F = [(-3.1, 0.35, 0.11), (-2.6, 0.3, 0.11), (-2.0, 0.25, 0.11), (-1.4, 0.2, 0.11), (-0.95, -0.1, 0.11),
         (-0.55, -0.17, 0.11), (-0.15, -0.15, 0.13), (0.13, -0.12, 0.13)]
HERO_L = 3.0


def hero_lying(trk):
    s = trk.s_near(TH_LOC) - 0.25
    return trk.span(s - HERO_L, s)


def rocket_pose(f, root):
    t = max(0.0, (f - EV['liftoff']) / 12)
    ign = f >= EV['ignite']
    jit = 0.02 * math.sin(f * 7.3) if ign and t == 0 else 0.0
    root.location = (ROCKET[0] + 0.6 * t * t + jit, ROCKET[1], ROCKET[2] + 1.6 * t * t)
    root.rotation_euler = (0.35 * t * math.sin(t * 14) + jit, 0.3 * t * math.sin(t * 11 + 1), 0.0)


def e_launch():
    st = {}
    fb = EV['boom']
    rnd = random.Random(7)

    def build():
        workshop()
        W.area_light('rkfill', (-1.0, -4.5, 3.5), (math.radians(60), 0, math.radians(-25)), 260, 4, (1.0, 0.8, 0.55))
        root, parts = rocket_set(); st['root'], st['parts'] = root, parts
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.45, radius2=0.02, depth=1.2)
        me = bpy.data.meshes.new('flame'); bm.to_mesh(me); bm.free()
        fl = W.link(bpy.data.objects.new('flame', me)); fl.parent = root; fl.location = (0, 0, -0.6); fl.rotation_euler = (math.pi, 0, 0)
        st['flame_m'] = W.mat_emit('flame_e', (1.0, 0.55, 0.15), 30.0); fl.data.materials.append(st['flame_m']); fl.visible_shadow = False
        st['flame'] = fl
        L = bpy.data.lights.new('flame_L', 'POINT'); L.color = (1.0, 0.6, 0.25); L.shadow_soft_size = 0.3
        st['flame_L'] = W.link(bpy.data.objects.new('flame_L', L)); st['flame_L'].parent = root; st['flame_L'].location = (0, 0, -0.5)
        # the moment of the explosion: where every part is, then each flies off on its own arc
        rocket_pose(fb, root); bpy.context.view_layer.update()
        st['C'] = root.matrix_world.translation.copy() + Vector((0, 0, 1.5))
        fly = [parts['cone'], parts['clip']] + parts['caps'] + parts['legs']
        st['fly'] = []
        for ob in fly:
            M = ob.matrix_world.copy()
            v = (M.translation - st['C']).normalized() * rnd.uniform(3, 6) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(2, 5)))
            ax = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
            st['fly'].append((ob, M, v, ax, rnd.uniform(8, 16)))
        # broken can lands at the back, hidden until the smoke covers it
        broot, bparts = W.rocket('broken', loc=(2.7, 2.6, 0.0)); broot.rotation_euler.z = -0.45
        st['broken'] = [bparts['can']] + bparts['legs']; st['broot'] = broot
        st['broot_end'], st['broot_rot'] = broot.location.copy(), broot.rotation_euler.copy()
        hide([bparts['cone'], bparts['clip']] + bparts['caps'] + st['broken'])
        # v3 (Dima 31.10): the approved fireball is back, v2's sparks and flying junk stay,
        # the smoke is a big soft brown-grey volume puff (the v2 Mantaflow cloud read as a small grey ball)
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0)
        fbm = bpy.data.meshes.new('fireball_me'); bm.to_mesh(fbm); bm.free()
        for p_ in fbm.polygons:
            p_.use_smooth = True
        st['fire_m'], st['fire_em'], st['fire_fade'] = fireball_mat()
        st['fire'] = swarm('fireball', 1, fbm, st['fire_m'])[0]; st['fire'].location = st['C']
        sm, st['soot_d'], st['soot_w'] = soft_puff_mat('soot_puff_m', (0.44, 0.37, 0.3))
        st['soot'] = puff('soot_puff', sm)
        F = bpy.data.lights.new('flash', 'POINT'); F.color = (1.0, 0.42, 0.1); F.shadow_soft_size = 0.6
        st['flash'] = W.link(bpy.data.objects.new('flash', F)); st['flash'].location = st['C']
        G = bpy.data.lights.new('fire_glow', 'POINT'); G.color = (1.0, 0.35, 0.08); G.shadow_soft_size = 0.8
        st['glow'] = W.link(bpy.data.objects.new('fire_glow', G)); st['glow'].location = st['C']
        st['sparks'] = swarm('spark', 90, ico_mesh('spark_me', 0.03), W.mat_emit('spark_e', (1.0, 0.7, 0.3), 40.0))
        st['spark_v'] = [Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.6, 1))).normalized() * rnd.uniform(4, 9) for _ in st['sparks']]
        st['spark_life'] = [rnd.uniform(0.5, 1.1) for _ in st['sparks']]
        st['clods'] = swarm('clod', 50, ico_mesh('clod_me', 1.0, 2), W.mat_soil('clod_m', base=(0.12, 0.075, 0.045), layered=False))
        st['clod_v'] = [Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.2, 1.2))).normalized() * rnd.uniform(2.5, 6) for _ in st['clods']]
        for ob in st['clods']:
            s = rnd.uniform(0.06, 0.18); ob.scale = (s, s * rnd.uniform(0.7, 1.2), s * 0.8)
        # launch dust at the base: soft volume puffs (the v2 alpha spheres read as faceted plastic balls)
        dm, st['dust_d'], st['dust_w'] = soft_puff_mat('dust_puff_m', (0.5, 0.41, 0.31), scale=2.4)
        st['dust'] = [puff(f'dust_puff{i}', dm) for i in range(3)]
        st['dust_o'] = [Vector((-0.9, -0.3, 0)), Vector((0.95, -0.2, 0)), Vector((0.1, -0.8, 0))]
        # people and things
        objs, btn = control(lit=False); set_leds(0, [False] * 3)
        st['hero'] = Worm('hero', 'hero', helmet=True); st['sk'] = Worm('skeptic', 'skeptic')
        st['hp'] = Worm('helper', 'helper'); st['hp2'] = Worm('helper2', 'helper2')
        st['trk'] = Track(TRK_F)
        st['cam'] = Cam((-0.6, -10.0, 2.2), (0.0, 2.0, 2.3), lens=40, fstop=8.0)

    def ballistic(p0, v, t, g, floor):
        z = p0.z + v.z * t - 0.5 * g * t * t
        if z > floor:
            return Vector((p0.x + v.x * t, p0.y + v.y * t, z)), False
        tl = (v.z + math.sqrt(max(0.0, v.z * v.z + 2 * g * (p0.z - floor)))) / g
        return Vector((p0.x + v.x * tl, p0.y + v.y * tl, floor)), True

    def frame(f):
        root, parts = st['root'], st['parts']
        boom = f >= fb; tb = (f - fb) / 12
        rocket_pose(min(f, fb), root)
        hide([parts['can']], boom)
        on = EV['ignite'] <= f < fb
        st['flame'].hide_render = not on
        st['flame'].scale = (1.0, 1.0, 0.6 + 0.5 * abs(math.sin(f * 3.1)) + (0.6 if f >= EV['liftoff'] else 0.0))
        st['flame_L'].data.energy = (60 + 40 * abs(math.sin(f * 2.3))) if on else 0.0
        bpy.context.view_layer.update()
        for ob, M, v, ax, spin in st['fly']:
            if boom:
                p, landed = ballistic(M.translation, v, tb, 12.0, 0.08)
                ang = spin * min(tb, 0.9)
                ob.matrix_world = Matrix.Translation(p) @ Quaternion(ax, ang).to_matrix().to_4x4() @ M.to_3x3().to_4x4()
        # fireball as approved on frame 409: grows, then dims and turns see-through instead of going black
        fire = st['fire']; fire.hide_render = not (fb <= f <= fb + 7)
        s = 0.3 + 1.6 * ramp(f, fb, fb + 3); fire.scale = (s, s, s)
        st['fire_em'].inputs['Strength'].default_value = 2.4 * (1 - 0.7 * ramp(f, fb + 1, fb + 6))
        st['fire_fade'].outputs[0].default_value = ramp(f, fb + 2, fb + 7)
        # soot: comes up under the fireball, swells, drifts up and thins out over ~1.3 s
        so = st['soot']; so.hide_render = not boom
        r = 0.8 + 2.1 * (1 - (1 - ramp(f, fb, fb + 18)) ** 2)
        so.scale = (r, r * 0.85, r * 0.9); so.location = st['C'] + Vector((0, 0, 1.0 * ramp(f, fb, fb + 18)))
        st['soot_d'].outputs[0].default_value = 22.0 * ramp(f, fb, fb + 3) * (1 - ramp(f, fb + 5, fb + 16))
        st['soot_w'].outputs[0].default_value = f * 0.06
        # flash (Dima 31.10): peaks for 2-3 frames and dies fast, the soil stays brown with shadows
        st['flash'].data.energy = 3500 * math.exp(-tb / 0.06) if boom else 0.0
        st['glow'].data.energy = 250 * math.exp(-tb / 0.5) if boom else 0.0
        for ob, v, life in zip(st['sparks'], st['spark_v'], st['spark_life']):
            p, landed = ballistic(st['C'], v, tb, 6.0, 0.03)
            ob.location = p; ob.hide_render = not boom or tb > life or landed
        for ob, v in zip(st['clods'], st['clod_v']):
            p, _ = ballistic(st['C'], v, tb, 12.0, ob.scale.z); ob.location = p; ob.hide_render = not boom
        dust_on = EV['ignite'] <= f < fb
        ts = max(0.0, (f - EV['ignite']) / 12)
        for ob, o in zip(st['dust'], st['dust_o']):
            ob.hide_render = not dust_on
            ob.location = Vector((ROCKET[0], ROCKET[1], 0.35 + 0.35 * ts)) + o * (1.0 + 0.4 * ts)
            r = 0.55 + 0.45 * ts; ob.scale = (r * 1.3, r, r * 0.8)
        st['dust_d'].outputs[0].default_value = 8.0 * ramp(f, EV['ignite'], EV['ignite'] + 3)
        st['dust_w'].outputs[0].default_value = f * 0.08
        # the burnt can now falls out of the blast onto its approved spot instead of appearing behind smoke balls
        hide(st['broken'][:1], not boom); hide(st['broken'][1:], f < fb + 4)
        u = ramp(f, fb, fb + 6) if boom else 0.0
        top = st['C'] - Vector((0, 0, 1.5))
        st['broot'].location = top.lerp(st['broot_end'], u * u) + Vector((0, 0, 0.6 * math.sin(math.pi * min(1.0, u * 1.2))))
        st['broot'].rotation_euler = (st['broot_rot'].x * u, st['broot_rot'].y * u + 2.0 * (1 - u), st['broot_rot'].z)
        # worms: watch, then the blast throws the hero flat and his helmet off
        p = voice('hero', f)
        look = root.matrix_world.translation + Vector((0, 0, 1.5))
        stand = body(HERO_CTRL_FLOOR, (-2.0, 0.9, 0.85), look, 0.11, 0.3, 0.3 * p)
        if not boom:
            st['hero'].set(stand, pulse=p)
        else:
            u = ramp(f, fb, fb + 5)
            a, b = resample_ctrl(stand), hero_lying(st['trk'])
            ctrl = [x.lerp(y, u) + Vector((0, 0, 0.35 * math.sin(math.pi * u))) for x, y in zip(a, b)]
            st['hero'].set(ctrl, helmet_on=False)
            h = st['hero'].helmet; h.hide_render = False
            hu = ramp(f, fb, fb + 7)
            h.location = mix(Vector(stand[-1]), Vector(TH_LOC), hu) + Vector((0, 0, 1.2 * math.sin(math.pi * hu)))
            h.rotation_euler = (TH_ROT[0] + 6 * (1 - hu), TH_ROT[1] * hu, TH_ROT[2] + 4 * (1 - hu))
        flinch = ramp(f, fb, fb + 2)
        st['sk'].set(body(SK_AFTER, Vector(SK_AFTER_TOP) - Vector((0, 0, 0.25 * flinch)), look, 0.15, 0.36))
        duck = ramp(f, fb - 1, fb + 1)
        st['hp'].set(body([(-3.6, 2.2), (-3.3, 1.7), (-3.0, 1.3)], (-2.9, 1.05, 0.45 - 0.3 * duck), look, 0.085, 0.24))
        st['hp2'].set(body([(-4.1, 0.9), (-3.6, 0.7), (-3.2, 0.55)], (-3.0, 0.45, 0.4 - 0.28 * duck), look, 0.08, 0.22))
        shake = 0.18 * math.exp(-tb / 0.35) if boom else (0.015 if f >= EV['ignite'] else 0.0)
        st['cam'].set(f, (-0.6, -10.0, 2.4), (0.2, 2.0, 2.75), shake=shake)
    return build, frame


# ---------------------------------------------------------------- F, G: the aftermath
def aftermath(st):
    workshop(ff=False, world=0.2)
    broot, bparts = W.rocket('broken', loc=(2.7, 2.6, 0.0)); broot.rotation_euler.z = -0.45
    hide([bparts['cone'], bparts['clip']] + bparts['caps'])
    st['cap'] = W.bottle_cap('extra_cap', (0.75, 0.08, 0.06), r=0.5, h=0.2)
    st['cap'].location = CAPF; st['cap'].rotation_euler = (0, 0, 0.3 + 2.4)
    S1.clear_floor(CAPF.x, CAPF.y, 0.6, 0.6, zmax=0.0)
    S1.clear_floor(TH_LOC[0], TH_LOC[1], 0.5, 0.4, zmax=0.02)
    control(lit=False); set_leds(0, [False] * 3)
    st['th'] = W.thimble('helmet_down'); st['th'].location = TH_LOC; st['th'].rotation_euler = TH_ROT
    soot = W.mat_simple('soot2', (0.04, 0.035, 0.03), 0.95)
    rnd = random.Random(9)
    for i in range(36):
        r = W.rock(f'debris{i}', rnd.uniform(0.04, 0.12), seed=i + 7000, mat=soot)
        r.location = (rnd.uniform(-0.5, 4.5), rnd.uniform(0.6, 3.6), 0.02)
    st['dust'] = swarm('dust', 160, ico_mesh('dust_me', 1.0, 1), W.mat_simple('dust_m', (0.25, 0.18, 0.12), 0.9))
    st['dust_p'] = [(rnd.uniform(-3.0, 2.5), rnd.uniform(-1.5, 3.0), rnd.uniform(0, 5.5), rnd.uniform(0.35, 0.8)) for _ in st['dust']]
    for ob in st['dust']:
        s = rnd.uniform(0.006, 0.02); ob.scale = (s, s, s)
    W.firefly('ff_last', (-1.15, -1.05, 0.85), energy=10.0)
    W.area_light('dimfill', (-2, -6, 3), (math.radians(65), 0, math.radians(-15)), 45, 4, (0.7, 0.75, 0.9))
    ffh, _ = W.firefly('ff_helmet', (-0.3, -0.7, 0.8), energy=4.0); ffh.visible_camera = False
    # Dima 31.10: keep it dark, but the skeptic's head turn and the hero's crawl must read as silhouettes
    W.area_light('fill', (-0.6, -3.2, 1.3), (math.radians(75), 0, math.radians(-5)), 30, 3, (1.0, 0.82, 0.62))
    spot('sk_rim', (-0.1, 2.9, 1.9), (-0.3, 1.1, 0.75), 70, 40, 0.5, (0.7, 0.8, 1.0), 0.4)
    spot('hero_rim', (-1.3, 1.9, 1.3), (-1.2, 0.15, 0.1), 60, 70, 0.6, (0.7, 0.8, 1.0), 0.4)
    st['hero'] = Worm('hero', 'hero'); st['sk'] = Worm('skeptic', 'skeptic')
    st['trk'] = Track(TRK_F)


def dust_fall(st, f):
    t = f / 12
    for ob, (x, y, z0, v) in zip(st['dust'], st['dust_p']):
        ob.location = (x, y, 5.5 - ((5.5 - z0) + v * t) % 5.5)


def f_silence():
    st = {}

    def build():
        aftermath(st)
        st['cam'] = Cam((-0.55, -3.6, 0.8), (-0.45, 0.2, 0.3), lens=35, fstop=3.2)

    def frame(f):
        dust_fall(st, f)
        st['hero'].set(hero_lying(st['trk']), wave=None)
        hero_head = st['hero'].pts[-1]
        look = keyed(f, [(217, CAPF + Vector((0, 0, 0.1))), (230, CAPF + Vector((0, 0, 0.1))), (246, hero_head), (252, hero_head)])
        st['sk'].set(body(SK_AFTER, SK_AFTER_TOP, look, 0.15, 0.36))
        u = (f - 217) / 35                              # slow, linear push-in on the cap
        st['cam'].set(f, mix(Vector((-0.55, -3.6, 0.8)), Vector((-0.85, -2.9, 0.6)), u),      # push stops short: the skeptic stays in
                      mix(Vector((-0.45, 0.2, 0.3)), Vector((-0.85, 0.0, 0.3)), u), lens=35 + 5 * u, focus=CAPF, drift=0.008)
    return build, frame


def g_helmet():
    st = {}

    def build():
        aftermath(st)
        st['sI'] = st['trk'].L
        st['s0'] = st['trk'].s_near(TH_LOC) - 0.25
        st['cam'] = Cam((0.15, -2.3, 0.5), (-0.5, -0.05, 0.15), lens=38, fstop=3.2)

    def frame(f):
        dust_fall(st, f)
        s = keyed(f, [(253, st['s0']), (257, st['s0']), (280, st['sI'] + HERO_L - 0.35), (294, st['sI'] + HERO_L - 0.35)])
        a, b = s - HERO_L, min(s, st['sI'])                 # only the part still outside the thimble
        moo = voice('hero', f)
        twitch = 0.08 * math.sin(f * 1.7) * ramp(f, EV['moo'] + 2, EV['moo'] + 6)
        if b - a > 0.12:
            ctrl = st['trk'].span(a, b, 9)
            ctrl[0] += Vector((0, twitch, 0))
            st['hero'].set(ctrl, wave=f * 0.3 if f < 281 else None)
        else:
            st['hero'].set(None)
        st['th'].rotation_euler = (TH_ROT[0] + 0.06 * moo * math.sin(f * 3.0), TH_ROT[1], TH_ROT[2])
        st['sk'].set(body(SK_AFTER, SK_AFTER_TOP, TH_LOC, 0.15, 0.36))
        st['cam'].set(f, (0.15, -2.3, 0.5), (-0.5, -0.05, 0.15), focus=TH_LOC, drift=0.006)
    return build, frame


SHOTS = dict(a1_scribble=a1_scribble, a2_blueprint=a2_blueprint, a3_skeptic=a3_skeptic, b1_can=b1_can, b2_caps=b2_caps,
             b3_legs=b3_legs, b4_weld=b4_weld, b5_foil=b5_foil, c_cap=c_cap, d_count=d_count, e_launch=e_launch,
             f_silence=f_silence, g_helmet=g_helmet)

if __name__ == '__main__':
    names = boot.args() or ['all']
    if names == ['all']:
        names = [n for n, _, _ in TM.SHOTS]
    for n in names:
        b, fr = SHOTS[n]()
        render_shot(n, b, fr)
