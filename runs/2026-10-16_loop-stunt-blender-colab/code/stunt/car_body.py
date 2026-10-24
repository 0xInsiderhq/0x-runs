"""Car body lofted from a 3-view blueprint (side / top / front splines).
Car space: X right, Y forward (nose +2.15), Z up, origin on the ground."""
import bpy, bmesh, math, bisect, time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import materials as M

LENGTH, HALF = 4.3, 2.15
# ---- side view (y, z): low sloping tail, low nose with integrated chin ----
SIDE = {
    "z_top":  [(-2.15, .72), (-1.95, .80), (-1.6, .90), (-1.0, 1.02), (-0.55, 1.10), (-0.15, 1.10), (0.80, .77), (1.2, .72), (1.95, .45), (2.15, .34)],
    "z_edge": [(-2.15, .71), (-1.95, .78), (-1.4, .89), (-1.0, .975), (-0.55, 1.075), (-0.15, 1.075), (0.78, .81), (1.2, .82), (1.6, .68), (1.95, .48), (2.15, .35)],
    "z_belt": [(-2.15, .68), (-1.95, .74), (-1.4, .84), (-1.0, .88), (-0.55, .86), (0.0, .82), (0.6, .79), (0.9, .785), (1.2, .79), (1.6, .65), (1.95, .455), (2.15, .33)],
    "z_bot":  [(-2.15, .32), (-1.95, .16), (-1.6, .12), (1.8, .12), (2.0, .13), (2.15, .16)],
}
# ---- top view (y, half width) ----
TOP = {
    "w":     [(-2.15, .86), (-1.9, .94), (-1.4, .975), (-0.6, .955), (0.2, .94), (0.8, .955), (1.2, .975), (1.6, .955), (2.0, .885), (2.15, .80)],
    "w_top": [(-2.15, .74), (-1.9, .82), (-1.4, .83), (-1.0, .71), (-0.55, .60), (-0.15, .60), (0.78, .80), (1.2, .86), (1.6, .84), (2.0, .78), (2.15, .70)],
}
# ---- front view: reference half-section at y=-0.55 as bezier segments (p0, h0, h1, p1, band, samples) ----
FRONT = [
    ((0.0, .12), (0.30, .12), (0.75, .12), (0.86, .12), "low", 5),
    ((0.86, .12), (0.92, .12), (0.955, .17), (0.955, .24), "low", 6),
    ((0.955, .24), (0.955, .40), (0.955, .70), (0.94, .86), "low", 8),
    ((0.94, .86), (0.86, .95), (0.72, 1.06), (0.60, 1.075), "glass", 8),
    ((0.60, 1.075), (0.45, 1.095), (0.25, 1.10), (0.0, 1.10), "crown", 12),
]
REF = dict(W=.955, Wt=.60, Xs=.94, Zb=.12, Zs=.86, Ze=1.075, Zt=1.10)
WHEELS = dict(FL=(-0.83, 1.20), FR=(0.83, 1.20), RL=(-0.82, -1.40), RR=(0.82, -1.40))
ARCH_R = 0.398
ARCH_IN = dict(F=0.74, R=0.52)   # inner end of the wheel-well cutter (front kept outboard: no cut through the bonnet)
MAT = dict(PAINT=0, WINDOW=1, UNDER=2, TRIM=3, LINER=4, INTAKE=5)
# side intake (y, z) outline and scoop depth (deeper towards the rear)
INTAKE = [(-0.76, 0.52), (-1.06, 0.70), (-1.10, 0.86), (-0.80, 0.845)]
def intake_x_in(y):
    t = min(1.0, max(0.0, (-0.76 - y) / 0.34)); return 0.925 - 0.055 * t

def pchip(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; n = len(pts)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]; d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [d[0]] + [0.0] * (n - 2) + [d[-1]]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    return xs, ys, m

def pchip_eval(c, x):
    xs, ys, m = c
    x = min(max(x, xs[0]), xs[-1]); i = min(max(bisect.bisect_right(xs, x) - 1, 0), len(xs) - 2)
    h = xs[i + 1] - xs[i]; t = (x - xs[i]) / h
    return ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h * m[i]
            + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h * m[i + 1])

CURVES = {k: pchip(v) for k, v in {**SIDE, **TOP}.items()}
def F(name, y): return pchip_eval(CURVES[name], y)

def bez(p0, h0, h1, p1, t):
    u = 1 - t
    return tuple(u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c + t * t * t * d for a, b, c, d in zip(p0, h0, h1, p1))

def _template():
    pts = [(FRONT[0][0], "low")]
    for (p0, h0, h1, p1, band, n) in FRONT:
        for k in range(1, n + 1): pts.append((bez(p0, h0, h1, p1, k / n), band))
    return pts
TPL = _template()
I_S = max(i for i, (_, b) in enumerate(TPL) if b == "low")
I_E = max(i for i, (_, b) in enumerate(TPL) if b == "glass")
N_GLASS = I_E - I_S

def section(y):
    zb, zs, ze, zt = F("z_bot", y), F("z_belt", y), F("z_edge", y), F("z_top", y)
    w, wt = F("w", y), F("w_top", y); Xs = REF["Xs"] * w / REF["W"]
    pts = []
    for k, ((xt, zp), band) in enumerate(TPL):
        if k <= I_S:
            x = xt * w / REF["W"]; z = zb + (zp - REF["Zb"]) * (zs - zb) / (REF["Zs"] - REF["Zb"])
        elif k <= I_E:
            x = wt + (xt - REF["Wt"]) * (Xs - wt) / (REF["Xs"] - REF["Wt"]); z = zs + (zp - REF["Zs"]) * (ze - zs) / (REF["Ze"] - REF["Zs"])
        else:
            x = xt * wt / REF["Wt"]; z = ze + (zp - REF["Ze"]) * (zt - ze) / (REF["Zt"] - REF["Ze"])
        pts.append((x, z))
    pts[0] = (0.0, pts[0][1]); pts[-1] = (0.0, pts[-1][1])
    return pts

def stations(n=120):
    out = []
    for i in range(n):
        s = i / (n - 1); out.append(-HALF + LENGTH * (0.6 * s + 0.4 * (0.5 - 0.5 * math.cos(math.pi * s))))
    return out

# ---------------- blueprint curves (reference drawing, not rendered) ----------------
def _curve_obj(name, pts3, coll):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts3) - 1)
    for bp, (co, hl, hr) in zip(sp.bezier_points, pts3):
        bp.co = co; bp.handle_left_type = bp.handle_right_type = "FREE"; bp.handle_left = hl; bp.handle_right = hr
    ob = bpy.data.objects.new(name, cu); coll.objects.link(ob); ob.hide_render = True
    return ob

def blueprint(coll):
    for name, pts in {**SIDE, **TOP}.items():
        xs, ys, m = CURVES[name]; data = []
        f3 = (lambda p: (-2.5, p[0], p[1])) if name in SIDE else (lambda p: (p[1], p[0], -0.02))
        for i in range(len(xs)):
            hl = (xs[i] - (xs[i] - xs[i - 1]) / 3, ys[i] - m[i] * (xs[i] - xs[i - 1]) / 3) if i else (xs[i], ys[i])
            hr = (xs[i] + (xs[i + 1] - xs[i]) / 3, ys[i] + m[i] * (xs[i + 1] - xs[i]) / 3) if i < len(xs) - 1 else (xs[i], ys[i])
            data.append((f3((xs[i], ys[i])), f3(hl), f3(hr)))
        _curve_obj("BP_" + name, data, coll)
    data = []
    for k, (p0, h0, h1, p1, band, n) in enumerate(FRONT):
        if k == 0: data.append(((p0[0], 4.0, p0[1]), (p0[0], 4.0, p0[1]), (h0[0], 4.0, h0[1])))
        else: data[-1] = (data[-1][0], data[-1][1], (h0[0], 4.0, h0[1]))
        data.append(((p1[0], 4.0, p1[1]), (h1[0], 4.0, h1[1]), (p1[0], 4.0, p1[1])))
    _curve_obj("BP_front", data, coll)

# ---------------- loft ----------------
def loft():
    ys = stations(); nh = len(TPL); Mr = 2 * nh - 2
    bm = bmesh.new(); rings = []
    for y in ys:
        sec = section(y)
        pts = [(x, y, z) for (x, z) in sec] + [(-x, y, z) for (x, z) in reversed(sec[1:-1])]
        rings.append([bm.verts.new(p) for p in pts])
    tidx = lambda p: p if p < nh else 2 * nh - 2 - p
    crease = bm.edges.layers.float.new("crease_edge")
    for i in range(len(ys) - 1):
        ym = 0.5 * (ys[i] + ys[i + 1])
        for j in range(Mr):
            j2 = (j + 1) % Mr
            f = bm.faces.new((rings[i][j], rings[i + 1][j], rings[i + 1][j2], rings[i][j2]))
            k = max(tidx(j), tidx(j2)); band = TPL[k][1]
            mat = MAT["PAINT"]
            if band == "low" and k <= FRONT[0][5]: mat = MAT["UNDER"]
            elif band == "glass" and (k - I_S - 1) < N_GLASS - 1 and -0.88 < ym < 0.66: mat = MAT["WINDOW"]
            elif band == "crown" and (k - I_E - 1) >= 2 and (-0.12 < ym < 0.74 or -0.98 < ym < -0.62): mat = MAT["WINDOW"]
            f.material_index = mat
    bm.edges.ensure_lookup_table()
    for i in range(len(ys) - 1):
        hood = 0.5 * (ys[i] + ys[i + 1]) > 0.85            # softer character lines on the bonnet
        for j, val in ((I_S, 0.9), (I_E, 0.85), (Mr - I_S, 0.9), (Mr - I_E, 0.85)):
            e = bm.edges.get((rings[i][j], rings[i + 1][j]))
            if e: e[crease] = val * (0.45 if hood else 1.0)
    for ring, val, mat in ((rings[0], 0.8, MAT["PAINT"]), (rings[-1], 0.6, MAT["TRIM"])):
        for j in range(Mr):
            e = bm.edges.get((ring[j], ring[(j + 1) % Mr]))
            if e: e[crease] = val
        f = bm.faces.new(ring); f.material_index = mat
        for _ in range(3):
            res = bmesh.ops.inset_region(bm, faces=[f], thickness=0.012, depth=0.0, use_even_offset=True)
            for nf in res["faces"]: nf.material_index = mat
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("CarBody"); bm.to_mesh(me); bm.free()
    return me

def bake(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = obj.data; obj.modifiers.clear(); obj.data = me; bpy.data.meshes.remove(old)

def bvh_of(obj):
    me = obj.data
    return BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])

# ---------------- cutters (arches, panel gaps, intakes) ----------------
def rounded_path(corners, r=0.05, step=0.008, closed=False):
    """polyline through corners with rounded corners, resampled every `step` metres"""
    pts = []; n = len(corners)
    if not closed: pts.append(Vector(corners[0]))
    for i in (range(n) if closed else range(1, n - 1)):
        a, p, b = Vector(corners[i - 1]), Vector(corners[i]), Vector(corners[(i + 1) % n])
        rr = min(r, (a - p).length * 0.45, (b - p).length * 0.45)
        p0, p1 = p + (a - p).normalized() * rr, p + (b - p).normalized() * rr
        for k in range(7):
            t = k / 6; pts.append(p0 * (1 - t) ** 2 + p * 2 * (1 - t) * t + p1 * t * t)
    pts.append(Vector(corners[-1]) if not closed else pts[0].copy())
    out = [pts[0]]
    for q in pts[1:]:
        k = max(1, int((q - out[-1]).length // step)); a = out[-1]
        out.extend([a.lerp(q, s / k) for s in range(1, k + 1)])
    return out[:-1] if closed else out

def project(bvh, path2d, mode):
    res = []
    for q in path2d:
        a, b = q[0], q[1]
        if mode == "top": o, d = Vector((a, b, 3.0)), Vector((0, 0, -1))
        elif mode == "side+": o, d = Vector((3.0, a, b)), Vector((-1, 0, 0))
        else: o, d = Vector((-3.0, a, b)), Vector((1, 0, 0))
        hit, n, idx, dist = bvh.ray_cast(o, d)
        if hit is not None: res.append((hit, n))
    return res

def slab(bm, pn, closed, hw=0.002, din=0.012, dout=0.03):
    P = [p for p, n in pn]; Nn = [n for p, n in pn]; n = len(P)
    secs = []
    for i in range(n):
        a = P[i - 1] if (closed or i > 0) else P[i]; b = P[(i + 1) % n] if (closed or i < n - 1) else P[i]
        t = (b - a).normalized()
        nn = (Nn[i - 1] + Nn[i] * 2 + Nn[(i + 1) % n]).normalized()
        bb = nn.cross(t).normalized()
        c = [P[i] + nn * dout + bb * hw, P[i] + nn * dout - bb * hw, P[i] - nn * din - bb * hw, P[i] - nn * din + bb * hw]
        secs.append([bm.verts.new(v) for v in c])
    for i in range(n if closed else n - 1):
        s0, s1 = secs[i], secs[(i + 1) % n]
        for k in range(4): bm.faces.new((s0[k], s0[(k + 1) % 4], s1[(k + 1) % 4], s1[k]))
    if not closed:
        bm.faces.new(secs[0][::-1]); bm.faces.new(secs[-1])

def box(bm, center, size, bevel=0.0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r["verts"]
    for v in vs: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(center)
    if bevel > 0:
        es = list({e for v in vs for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=es, offset=bevel, segments=3, affect="EDGES", profile=0.5)
    return vs

def cylinder_x(bm, center, r, length, seg=64):
    res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=length)
    for v in res["verts"]:
        x, y, z = v.co; v.co = Vector((z, y, x)) + Vector(center)  # axis Z -> X

def intake_cutter(bm, s):
    """recessed scoop: prism from the side outline, inner wall deepening towards the rear"""
    path = rounded_path(INTAKE, 0.035, step=0.01, closed=True)
    inner = [bm.verts.new((s * intake_x_in(p.x), p.x, p.y)) for p in path]
    outer = [bm.verts.new((s * 1.3, p.x, p.y)) for p in path]
    n = len(path)
    for i in range(n): bm.faces.new((inner[i], inner[(i + 1) % n], outer[(i + 1) % n], outer[i]))
    bm.faces.new(inner); bm.faces.new(outer)

def _cutter_obj(name, bm, coll):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob); ob.hide_render = True
    return ob

def arch_cutter(key, coll):
    x, y = WHEELS[key]; s = 1 if x > 0 else -1
    x0, x1 = ARCH_IN[key[0]], 1.27
    bm = bmesh.new(); cylinder_x(bm, (s * (x0 + x1) / 2, y, 0.35), ARCH_R, x1 - x0, seg=96)
    return _cutter_obj("Cut_" + key, bm, coll)

def intake_cutters(coll):
    bm = bmesh.new()
    for s in (1, -1): intake_cutter(bm, s)
    return _cutter_obj("Cut_intakes", bm, coll)

def gap_cutters(bvh, coll):
    bm = bmesh.new()
    for s in (1, -1):
        door = [(0.62, F("z_belt", 0.62) + 0.012), (0.70, 0.26), (-0.62, 0.26), (-0.70, F("z_belt", -0.70) + 0.012)]
        slab(bm, project(bvh, rounded_path(door, 0.05), "side+" if s > 0 else "side-"), closed=False)
    deck = [(-0.62, -1.92), (0.62, -1.92), (0.62, -1.05), (-0.62, -1.05)]          # engine lid only, no bonnet lines
    slab(bm, project(bvh, rounded_path(deck, 0.08, closed=True), "top"), closed=True)
    return _cutter_obj("Cut_gaps", bm, coll)

def apply_cut(ob, cut, solver="FAST"):
    b = ob.modifiers.new("Cut", "BOOLEAN"); b.operation = "DIFFERENCE"; b.solver = solver; b.object = cut
    if solver == "EXACT": b.material_mode = "INDEX"; b.use_self = False; b.use_hole_tolerant = False
    bake(ob); bpy.data.objects.remove(cut)

def arch_open(ob, key):
    """True if a ray from outside through the wheel centre no longer hits the body skin"""
    x, y = WHEELS[key]; s = 1 if x > 0 else -1
    hit, n, i, d = bvh_of(ob).ray_cast(Vector((s * 3.0, y, 0.35)), Vector((-s, 0, 0)))
    return hit is None or abs(hit.x) < ARCH_IN[key[0]] + 0.02

def classify_cut_faces(ob, bvh_skin):
    """faces created by the cutters lie inside the original skin: paint them liner / intake graphite"""
    n_l = n_i = 0
    for p in ob.data.polygons:
        c = p.center; loc, nrm, idx, dist = bvh_skin.find_nearest(c)
        if dist is None or dist < 0.003: continue
        if abs(c.x) > 0.75 and -1.2 < c.y < -0.68 and 0.45 < c.z < 0.92:
            p.material_index = MAT["INTAKE"]; n_i += 1
        else:
            p.material_index = MAT["LINER"]; n_l += 1
    print(f"  cut faces: liner {n_l}, intake {n_i}", flush=True)

# ---------------- glass ----------------
def make_glass(body, coll):
    bm = bmesh.new(); bm.from_mesh(body.data); bm.normal_update()
    wi = MAT["WINDOW"]
    out = bmesh.new(); vmap = {}
    for f in bm.faces:
        if f.material_index != wi: continue
        vs = []
        for v in f.verts:
            if v.index not in vmap: vmap[v.index] = out.verts.new(v.co + v.normal * 0.0025)
            vs.append(vmap[v.index])
        try: out.faces.new(vs)
        except ValueError: pass
    me = bpy.data.meshes.new("Glass"); out.to_mesh(me); out.free(); bm.free()
    me.materials.append(M.glass("WindowGlass", (0.52, 0.56, 0.58)))
    ob = bpy.data.objects.new("Glass", me); coll.objects.link(ob)
    sol = ob.modifiers.new("Thick", "SOLIDIFY"); sol.thickness = 0.005; sol.offset = 1.0
    bake(ob); ob.data.shade_smooth()
    return ob

def build_body(coll):
    t0 = time.time()
    me = loft()
    for m in (M.car_paint(), M.window_back(), M.underbody(), M.trim_black(), M.liner(), M.intake_inner()): me.materials.append(m)
    ob = bpy.data.objects.new("Body", me); coll.objects.link(ob)
    me.shade_smooth()
    sub = ob.modifiers.new("Subsurf", "SUBSURF"); sub.levels = 2; sub.render_levels = 2; sub.use_creases = True
    bake(ob)
    bvh = bvh_of(ob)
    for key in WHEELS:
        apply_cut(ob, arch_cutter(key, coll))
        for solver in ("FAST",):
            if arch_open(ob, key): break
            print(f"  arch {key} not open, retry {solver}", flush=True)
            apply_cut(ob, arch_cutter(key, coll), solver)
        print(f"  arch {key}: {'open' if arch_open(ob, key) else 'FAILED'}", flush=True)
    apply_cut(ob, intake_cutters(coll))
    apply_cut(ob, gap_cutters(bvh, coll))
    classify_cut_faces(ob, bvh)
    print(f"  body: loft+subsurf+booleans {time.time() - t0:.1f}s, {len(ob.data.polygons)} faces", flush=True)
    try:
        bv = ob.modifiers.new("Bevel", "BEVEL"); bv.limit_method = "ANGLE"; bv.angle_limit = math.radians(40)
        bv.width = 0.0012; bv.segments = 2; bv.use_clamp_overlap = True
        bake(ob)
    except Exception as e:
        print("bevel skipped:", e); ob.modifiers.clear()
    ob.data.shade_smooth(); ob.data.set_sharp_from_angle(angle=math.radians(50))
    glass = make_glass(ob, coll)
    print(f"  body total {time.time() - t0:.1f}s", flush=True)
    return ob, glass, bvh_of(ob)
