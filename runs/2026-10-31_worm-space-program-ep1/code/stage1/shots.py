import os
import sys, time, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
import wsp_lib as W
from logger import log

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out') + os.sep
BP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blueprint.png')
SHAFT = (2.2, 2.2)

def hero(ctrl, helmet=True, name='hero', tilt=0.25):
    ob, pts, T = W.worm(name, ctrl, R=0.11)
    th = None
    if helmet:
        th = W.thimble(name + '_helmet')
        tip, t = pts[-1], T[-1]
        th.location = tip - t * 0.17
        th.rotation_euler = t.to_track_quat('Z', 'Y').to_euler()
        th.rotation_euler.y += tilt
    return ob, pts, T, th

def skeptic(ctrl, name='skeptic'):
    return W.worm(name, ctrl, R=0.15, mat=W.mat_worm(name + '_m', pale=0.45), band=(0.66, 0.77), head_taper=0.5)

def helper(ctrl, name='helper'):
    return W.worm(name, ctrl, R=0.085, mat=W.mat_worm(name + '_m', body=(0.22, 0.06, 0.05)), band=(0.70, 0.78))

def charcoal_at(pts, T, length=0.32):
    tip, t = pts[-1], T[-1]
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.05, radius2=0.04, depth=length)
    me = bpy.data.meshes.new('charcoal'); bm.to_mesh(me); bm.free()
    ob = W.link(bpy.data.objects.new('charcoal', me))
    d = (t + Vector((0, 0, -1.2))).normalized()
    ob.location = tip + d * (length / 2 - 0.02)
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ob.data.materials.append(W.mat_simple('charcoal_m', (0.02, 0.018, 0.017), 0.9))
    return ob

def paper(loc, rot_z, size=(1.6, 2.0)):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=24, y_segments=30, size=1.0)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for l in f.loops:
            l[uv].uv = ((l.vert.co.x + 1) / 2, (l.vert.co.y + 1) / 2)
    for v in bm.verts:
        v.co.x *= size[0] / 2; v.co.y *= size[1] / 2
        v.co.z = 0.03 * math.sin(v.co.x * 3.1) * math.cos(v.co.y * 2.3) + 0.02 * (abs(v.co.x) / size[0])
    me = bpy.data.meshes.new('paper'); bm.to_mesh(me); bm.free()
    ob = W.link(bpy.data.objects.new('paper', me))
    ob.location = loc; ob.rotation_euler = (0, 0, rot_z)
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.materials.append(W.mat_paper('paper_m', BP))
    return ob

def dust(n, box, seed=3, size=(0.006, 0.02)):
    random.seed(seed)
    m = W.mat_simple('dust_m', (0.25, 0.18, 0.12), 0.9)
    for i in range(n):
        r = W.rock(f'dust{i}', random.uniform(*size), seed=i + 3000, mat=m)
        r.location = (random.uniform(box[0], box[1]), random.uniform(box[2], box[3]), random.uniform(box[4], box[5]))

def clear_floor(cx, cy, rx, ry, zmax=0.0):
    """Flatten the floor and drop crumbs/pebbles under a prop (paper, cap)."""
    fl = bpy.data.objects.get('floor')
    mw = fl.matrix_world; inv = mw.inverted()
    for v in fl.data.vertices:
        w = mw @ v.co
        if abs(w.x - cx) < rx and abs(w.y - cy) < ry:
            w.z = min(w.z, zmax); v.co = inv @ w
    for ob in list(bpy.data.objects):
        if ob.name.startswith(('crumb', 'peb')) and abs(ob.location.x - cx) < rx and abs(ob.location.y - cy) < ry:
            bpy.data.objects.remove(ob, do_unlink=True)

def render(name, samples=48, w=960, h=540):
    import os
    if os.environ.get('PREVIEW'):
        samples, w, h, name = 12, 480, 270, name + '_prev'
    W.render_settings(w, h, samples)
    s = bpy.context.scene
    s.render.filepath = OUT + name + '.png'
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    dt = round(time.time() - t0, 1)
    log('stills', 'render', f'{name} rendered in {dt}s on cloud CPU')
    print('render', name, dt)

# ---------------------------------------------------------------- shots
def s1_hook():
    """Cover frame: from the bottom of the shaft, a big circle of night sky,
    a red dot of Mars, the hero's helmeted head rising into it as a silhouette."""
    import os
    sx, sy = SHAFT
    top_z = float(os.environ.get('S1_TOP', 7.3))
    W.reset(); W.world_night(float(os.environ.get('S1_SKY', 3.2)), stars=False)
    soil = W.mat_soil('soil', base=(0.085, 0.05, 0.032))
    floor_m = W.mat_soil('floor_soil', base=(0.13, 0.08, 0.05), layered=False)
    W.displaced_plane('floor', 3.5, 3.5, (sx, sy - 0.8, 0), (0, 0, 0), floor_m, amp=0.05, scale=0.9, cuts=80, seed=1)
    wall_m = W.mat_soil('shaft_soil', base=(0.17, 0.10, 0.06), layered=False, scale=2.2)
    # walls are seen at grazing angles here: kill the grey Fresnel sheen
    _b = [n for n in wall_m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    _b.inputs['Specular IOR Level'].default_value = 0.05; _b.inputs['Roughness'].default_value = 1.0
    W.shaft('shaft', (sx, sy), r=1.15, z0=-0.4, z1=top_z, mat=wall_m)
    # grass blades on the rim lean over the opening, roots hang from the walls
    random.seed(11)
    grass = W.mat_simple('grass_m', (0.02, 0.035, 0.015), 0.6)
    for i in range(22):
        a = random.uniform(0, 2 * math.pi); r0 = 1.18
        b = Vector((sx + r0 * math.cos(a), sy + r0 * math.sin(a), top_z - 0.05))
        inward = Vector((-math.cos(a), -math.sin(a), 0))
        hgt = random.uniform(0.35, 0.9); lean = random.uniform(0.15, 0.55)
        pts = [b, b + Vector((0, 0, hgt * 0.5)) + inward * lean * 0.3, b + Vector((0, 0, hgt)) + inward * lean]
        ob, _, _ = W.tube(f'grass{i}', pts, lambda u, L: 0.035 * (1 - 0.9 * u) + 0.004, ring=6, samples=16)
        ob.data.materials.append(grass)
    rootm = W.mat_simple('root_m', (0.40, 0.29, 0.19), 0.75, sss=0.1)
    for i, a in enumerate([0.6, 2.4, 4.3]):
        W.root(f'root{i}', (sx + 1.05 * math.cos(a), sy + 1.05 * math.sin(a), top_z - 0.8 - i * 0.7), random.uniform(0.8, 1.4), seed=40 + i, r0=0.035, mat=rootm)
    # camera on the floor, a bit off the axis; frame-up points to +y
    C = Vector((sx, sy - 0.75, 0.18)); T_ = Vector((sx, sy, top_z))
    cam = W.camera(tuple(C), tuple(T_), lens=30, fstop=8, focus=1.6, shift=(0, float(os.environ.get('S1_SHIFT', -0.05))))
    bpy.context.view_layer.update()
    right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0)); up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
    d0 = (T_ - C).normalized()
    # stars and Mars far above, inside the sky circle
    W.star_field((sx, sy + 15), z=150, n=190, spread=24)
    for ob in bpy.data.objects:
        if ob.name.startswith('star'):
            ob.scale = (0.7, 0.7, 0.7)
    mars_m = W.mat_emit('mars_e', (1.0, 0.07, 0.015), float(os.environ.get('S1_MARS', 2.4)))
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=2.3)
    me = bpy.data.meshes.new('mars'); bm.to_mesh(me); bm.free()
    mars = W.link(bpy.data.objects.new('mars', me)); mars.data.materials.append(mars_m)
    mars.location = C + (d0 + right * 0.06 + up * 0.05).normalized() * 150
    # cold moonlight down the shaft, faint warm bounce from the workshop
    L = bpy.data.lights.new('moon', 'SPOT'); L.energy = float(os.environ.get('S1_MOON', 1800)); L.color = (0.82, 0.85, 1.0)
    L.spot_size = math.radians(40); L.spot_blend = 0.7; L.shadow_soft_size = 1.0
    lo = W.link(bpy.data.objects.new('moon', L)); lo.location = (sx, sy + 0.3, top_z + 6)
    W.firefly('ff_low', (sx + 0.9, sy - 1.6, 0.6), energy=6.0)
    glow = bpy.data.lights.new('workshop_glow', 'POINT'); glow.energy = float(os.environ.get('S1_GLOW', 50)); glow.color = (1.0, 0.62, 0.3); glow.shadow_soft_size = 0.6
    W.link(bpy.data.objects.new('workshop_glow', glow)).location = (sx - 0.5, sy - 1.0, 0.3)
    g2 = bpy.data.lights.new('workshop_glow2', 'POINT'); g2.energy = float(os.environ.get('S1_GLOW2', 30)); g2.color = (1.0, 0.6, 0.28); g2.shadow_soft_size = 0.5
    W.link(bpy.data.objects.new('workshop_glow2', g2)).location = (sx - 0.7, sy + 0.7, 0.3)
    # hero: body from the frame bottom, head over the camera, pointing at the sky
    hx = sx + 0.08
    # frame-up points to -y here, so the body comes from +y (below the frame)
    hero([(hx + 0.4, sy + 1.3, 0.11), (hx + 0.3, sy + 0.8, 0.11), (hx + 0.2, sy + 0.35, 0.25), (hx + 0.12, sy + 0.05, 0.6),
          (hx + 0.07, sy - 0.2, 1.05), (hx + 0.05, sy - 0.35, 1.45), (hx + 0.05, sy - 0.42, 1.75)], tilt=0.0)
    render('s1_hook')

def s2_blueprint():
    W.reset(); W.world_night(0.3, stars=False)
    W.workshop(SHAFT, mars=False)
    clear_floor(-0.2, 0.8, 1.15, 1.25, zmax=-0.02)
    paper((-0.2, 0.8, 0.05), 0.12)
    h, pts, T, th = hero([(-3.4, 1.8, 0.11), (-2.6, 1.2, 0.11), (-1.9, 1.3, 0.12), (-1.45, 0.9, 0.3), (-1.18, 0.75, 0.55), (-1.02, 0.7, 0.42)], tilt=0.3)
    charcoal_at(pts, T)
    sk, p2, T2 = skeptic([(2.6, 2.6, 0.15), (2.0, 2.9, 0.15), (1.5, 2.4, 0.2), (1.25, 2.15, 0.6), (1.2, 2.0, 0.85), (1.05, 1.85, 0.75)])
    hp, p3, T3 = helper([(-2.2, 3.4, 0.085), (-1.6, 3.0, 0.085), (-1.2, 2.6, 0.2), (-1.1, 2.35, 0.45), (-1.0, 2.2, 0.5)])
    W.firefly('ff_paper', (1.3, 2.1, 2.3), energy=10.0)
    W.area_light('key', (-2.5, -3.5, 4), (math.radians(45), 0, math.radians(-30)), 90, 3, (1.0, 0.8, 0.55))
    W.camera((-0.55, -4.4, 3.7), (-0.45, 0.85, 0.15), lens=70, fstop=4.5)
    render('s2_blueprint')

def s3_cap():
    W.reset(); W.world_night(0.3, stars=False)
    W.workshop(SHAFT, mars=False)
    W.rocket('assembled', loc=(SHAFT[0], 2.4, 0.55))
    cap = W.bottle_cap('extra_cap', (0.75, 0.08, 0.06), r=0.5, h=0.2)
    cap.location = (-0.35, -0.75, 0.0); cap.rotation_euler = (0.0, 0.0, 0.3)
    h, pts, T, th = hero([(-3.4, 1.4, 0.11), (-2.8, 0.7, 0.11), (-2.2, 0.4, 0.12), (-1.7, -0.1, 0.3), (-1.45, -0.45, 0.62), (-1.2, -0.62, 0.62)], tilt=0.45)
    ffc, _ = W.firefly('ff_cap', (-0.2, -1.4, 1.3), energy=4.0); ffc.visible_camera = False
    W.area_light('key', (-3, -4, 3), (math.radians(55), 0, math.radians(-35)), 70, 3, (1.0, 0.8, 0.55))
    clear_floor(-0.35, -0.75, 0.6, 0.6, zmax=0.0)
    W.camera((-1.25, -3.3, 0.42), (0.3, 0.9, 0.8), lens=30, fstop=2.8, focus=2.72)
    render('s3_cap')

def s4_helmet():
    W.reset(); W.world_night(0.2, stars=False)
    W.workshop(SHAFT, fireflies=False, mars=False)
    W.rocket('broken', loc=(SHAFT[0] + 0.5, 2.6, 0.0))
    bpy.data.objects['rocket'].rotation_euler.z = -0.45  # side of the can to camera, not its round end
    sm = bpy.data.materials['soot']; b = [n for n in sm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    b.inputs['Base Color'].default_value = (0.11, 0.09, 0.075, 1); b.inputs['Metallic'].default_value = 0.6; b.inputs['Roughness'].default_value = 0.5
    cap = W.bottle_cap('extra_cap', (0.75, 0.08, 0.06), r=0.5, h=0.2)
    cap.location = (-0.8, -0.1, 0.0); cap.rotation_euler = (0.0, 0.0, 0.3)
    th = W.thimble('helmet_down')
    th.rotation_euler = (0, math.radians(84), math.radians(18))
    th.location = (0.35, 0.3, 0.15)
    # worm order is tail -> head: the head goes deep into the thimble, the tail stays out
    W.worm('hero_hidden', [(-0.02, -0.12, 0.07), (0.0, 0.06, 0.08), (0.12, 0.2, 0.12), (0.28, 0.28, 0.15), (0.42, 0.32, 0.155), (0.56, 0.37, 0.165)], R=0.1, flatten=0.1)
    sk, p2, T2 = skeptic([(3.6, 1.2, 0.15), (3.0, 1.6, 0.15), (2.4, 1.3, 0.2), (2.15, 1.0, 0.55), (2.05, 0.85, 0.9), (1.85, 0.7, 0.92)])
    W.firefly('ff_last', (-0.6, -0.25, 0.85), energy=10.0)
    W.area_light('dimfill', (-2, -6, 3), (math.radians(65), 0, math.radians(-15)), 45, 4, (0.7, 0.75, 0.9))
    ffh, _ = W.firefly('ff_helmet', (0.2, -0.3, 0.8), energy=4.0); ffh.visible_camera = False
    dust(160, (-2.5, 3.0, -1.5, 3.0, 0.2, 4.5))
    soot = W.mat_simple('soot2', (0.04, 0.035, 0.03), 0.95)
    for i in range(30):
        r = W.rock(f'debris{i}', random.uniform(0.04, 0.12), seed=i + 7000, mat=soot)
        r.location = (random.uniform(-1.0, 4.0), random.uniform(0.5, 3.5), 0.02)
    clear_floor(0.35, 0.3, 0.5, 0.5, zmax=0.02)
    W.camera((-0.35, -2.6, 0.6), (0.55, 0.6, 0.3), lens=40, fstop=3.2, focus=3.02)
    render('s4_helmet')

def sheet_chars():
    W.reset(); W.world_night(0.15, stars=False)
    soil = W.mat_soil('soil', base=(0.085, 0.05, 0.032))
    W.displaced_plane('floor', 10, 7, (0, 1, 0), (0, 0, 0), W.mat_soil('fs', base=(0.13, 0.08, 0.05), layered=False), amp=0.05, cuts=80)
    W.displaced_plane('wall', 10, 5, (0, 4.8, 2.5), (math.pi / 2, 0, 0), W.mat_soil('soil_dark', base=(0.05, 0.03, 0.02)), amp=0.3, scale=0.5)
    hero([(-2.6, 1.0, 0.11), (-2.1, 0.45, 0.11), (-1.6, 0.6, 0.11), (-1.25, 0.25, 0.25), (-1.1, 0.15, 0.7), (-1.12, 0.12, 1.15)])
    skeptic([(2.6, 1.3, 0.15), (2.9, 0.7, 0.15), (2.4, 0.35, 0.18), (1.75, 0.3, 0.35), (1.5, 0.25, 0.75), (1.42, 0.2, 0.98)])
    helper([(0.6, 1.5, 0.085), (0.1, 1.0, 0.085), (0.25, 0.55, 0.15), (0.3, 0.45, 0.45), (0.25, 0.4, 0.62)])
    W.firefly('ff1', (-0.5, 0.8, 2.0), energy=5)
    W.area_light('key', (-3, -4, 3.0), (math.radians(65), 0, math.radians(-35)), 200, 3, (1.0, 0.82, 0.6))
    W.area_light('rim', (0.5, 3.2, 3.2), (math.radians(-60), 0, math.radians(175)), 260, 3, (0.6, 0.75, 1.0))
    W.camera((0.15, -10.5, 1.15), (0.15, 0.5, 0.6), lens=55, fstop=8)
    render('sheet_chars')

def sheet_rocket():
    W.reset(); W.world_night(0.15, stars=False)
    W.displaced_plane('floor', 16, 14, (0, 2.0, 0), (0, 0, 0), W.mat_soil('fs', base=(0.13, 0.08, 0.05), layered=False), amp=0.05, cuts=120)
    W.displaced_plane('wall', 16, 9, (0, 6.0, 4.0), (math.pi / 2, 0, 0), W.mat_soil('soil', base=(0.07, 0.042, 0.027)), amp=0.35, scale=0.5)
    W.rocket('pile', loc=(-5.6, 1.6, 0.0))
    W.rocket('assembled', loc=(0.0, 2.0, 0.55))
    W.rocket('broken', loc=(4.6, 2.2, 0.0))
    W.area_light('key', (-4, -8, 6), (math.radians(55), 0, math.radians(-20)), 520, 6, (1.0, 0.82, 0.6))
    W.area_light('rim', (0, 4.0, 7), (math.radians(-35), 0, math.radians(180)), 260, 6, (0.6, 0.75, 1.0))
    W.area_light('fill_broken', (8.5, -5.5, 5), (math.radians(55), 0, math.radians(50)), 260, 5, (1.0, 0.8, 0.6))
    W.camera((0.0, -14.5, 3.2), (0.0, 1.8, 1.7), lens=32, fstop=11)
    render('sheet_rocket')

def sheet_workshop():
    W.reset(); W.world_night(0.6, stars=True)
    W.workshop(SHAFT)
    W.rocket('assembled', loc=(SHAFT[0], 2.4, 0.55))
    hero([(-2.6, 0.2, 0.11), (-2.0, -0.3, 0.11), (-1.5, -0.1, 0.11), (-1.2, -0.3, 0.25), (-1.05, -0.35, 0.7), (-0.95, -0.3, 1.05)])
    skeptic([(-4.6, 1.8, 0.15), (-4.0, 1.4, 0.15), (-3.6, 1.6, 0.2), (-3.3, 1.4, 0.6), (-3.2, 1.3, 0.82)])
    helper([(0.2, 0.6, 0.085), (0.6, 0.2, 0.085), (1.0, 0.5, 0.09), (1.2, 0.8, 0.2)])
    W.area_light('warmfill', (-4, -8, 5), (math.radians(60), 0, math.radians(-20)), 260, 6, (1.0, 0.75, 0.5))
    W.camera((-0.4, -13.0, 2.6), (0.2, 2.0, 2.2), lens=45, fstop=8)
    render('sheet_workshop')

if __name__ == '__main__':
    globals()[sys.argv[1]]()
