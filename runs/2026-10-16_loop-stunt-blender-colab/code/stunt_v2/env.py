"""Night airfield: concrete runway, stunt loop with warm LED edges, red edge markers, ground fog/smoke, haze, sky."""
import bpy, bmesh, math
from mathutils import Vector
import materials as M, traj as T, car_wheels as CW, car_body as CB

RUNWAY_HALF = 18.0
def _stop_d():
    """v2.2: the car stops ~5 m earlier than in v1/v2; the wet patch and the final light follow it"""
    sp = T.EV["stop_pos"] if T.EV else (T.OLD_STOP[0], T.OLD_STOP[1], 0.0)
    return (sp[0] - T.OLD_STOP[0], sp[1] - T.OLD_STOP[1])

def mesh(name, bm, mats, coll, smooth=False):
    return CW.mesh_obj(name, bm, mats, coll, None, smooth)

# ---------------- materials ----------------
def concrete():
    m, nt = M.new("Concrete")
    if not nt: return m
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    X, Y = sep.outputs["X"], sep.outputs["Y"]
    def joint(v, period):
        d = M.math(nt, "PINGPONG", v, period / 2)
        return M.maprange(nt, d, 0.0, 0.012, 1.0, 0.0)
    j = M.math(nt, "MAXIMUM", joint(X, 7.5), joint(Y, 5.0))
    big = M.noise(nt, co, 0.04, 6.0, 0.6); mid = M.noise(nt, co, 0.6, 8.0, 0.65); fine = M.noise(nt, co, 60.0, 4.0, 0.5)
    base = M.mix(nt, M.maprange(nt, big.outputs["Fac"], 0.3, 0.7, 0.0, 1.0), (0.20, 0.20, 0.195, 1), (0.34, 0.335, 0.32, 1))
    base = M.mix(nt, M.maprange(nt, mid.outputs["Fac"], 0.45, 0.75, 0.0, 0.35), base, (0.12, 0.115, 0.11, 1))
    ax = M.math(nt, "ABSOLUTE", X)
    dash = M.math(nt, "MULTIPLY", M.maprange(nt, ax, 0.22, 0.24, 1.0, 0.0),
                  M.maprange(nt, M.math(nt, "PINGPONG", M.math(nt, "ADD", Y, 1000.0), 25.0), 9.6, 10.0, 0.0, 1.0))
    edge = M.math(nt, "MULTIPLY", M.maprange(nt, ax, RUNWAY_HALF - 0.9, RUNWAY_HALF - 0.88, 0.0, 1.0),
                  M.maprange(nt, ax, RUNWAY_HALF, RUNWAY_HALF + 0.02, 1.0, 0.0))
    paint = M.math(nt, "MULTIPLY", M.math(nt, "MAXIMUM", dash, edge),
                   M.maprange(nt, M.noise(nt, co, 3.0, 6.0, 0.7).outputs["Fac"], 0.35, 0.6, 0.15, 0.85))
    col = M.mix(nt, paint, base, (0.62, 0.62, 0.6, 1))
    tm = M.noise(nt, M.vmath(nt, "MULTIPLY", co, (6.0, 0.08, 1.0)), 1.0, 4.0, 0.5)
    tyre = M.math(nt, "MULTIPLY", M.maprange(nt, ax, 1.2, 2.6, 1.0, 0.0), M.maprange(nt, tm.outputs["Fac"], 0.5, 0.75, 0.0, 0.55))
    col = M.mix(nt, tyre, col, (0.03, 0.03, 0.03, 1))
    col = M.mix(nt, M.math(nt, "MULTIPLY", j, 0.85), col, (0.03, 0.03, 0.03, 1))
    damp = M.maprange(nt, M.noise(nt, co, 0.08, 5.0, 0.6).outputs["Fac"], 0.58, 0.66, 0.0, 1.0)
    rough = M.mix(nt, damp, 0.82, 0.32, "FLOAT")
    SD = _stop_d(); WET_C = (20.5 + SD[0], 11.0 + SD[1])
    wetd = M.vmath(nt, "DISTANCE", M.vmath(nt, "MULTIPLY", co, (1.0, 1.0, 0.0)), (WET_C[0] - T.RUNWAY_CX, WET_C[1], 0.0))
    wet = M.maprange(nt, wetd, 5.0, 13.0, 1.0, 0.0)                    # v2.1: wet asphalt where the car stops (reflections)
    rough = M.mix(nt, wet, rough, 0.1, "FLOAT")
    col = M.mix(nt, M.math(nt, "MULTIPLY", wet, 0.55), col, (0.05, 0.05, 0.05, 1))
    h = M.math(nt, "ADD", M.math(nt, "MULTIPLY", fine.outputs["Fac"], 0.6), M.math(nt, "MULTIPLY", j, -1.0))
    p = M.principled(nt, Base_Color=col, Roughness=rough, Normal=M.bump(nt, h, 0.35, 0.01))
    M.out(nt, p.outputs[0]); return m

def steel():
    m, nt = M.new("LoopSteel")
    if not nt: return m
    co = M.coords(nt); n = M.noise(nt, co, 1.5, 6.0, 0.6); g = M.noise(nt, co, 80.0, 3.0, 0.5)
    col = M.mix(nt, M.maprange(nt, n.outputs["Fac"], 0.45, 0.7, 0.0, 0.6), (0.045, 0.047, 0.05, 1), (0.11, 0.095, 0.08, 1))
    p = M.principled(nt, Base_Color=col, Metallic=0.6, Roughness=0.48, Normal=M.bump(nt, g.outputs["Fac"], 0.2, 0.003))
    M.out(nt, p.outputs[0]); return m

def fog_material():
    m, nt = M.new("GroundFog")
    if not nt: return m
    m.cycles.volume_step_rate = 0.06
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    val = M.N(nt, "ShaderNodeValue", label="drift"); val.name = "drift"; val.outputs[0].default_value = 0.0
    drift = M.N(nt, "ShaderNodeCombineXYZ"); nt.links.new(val.outputs[0], drift.inputs["X"])
    sh = M.math(nt, "MULTIPLY", val.outputs[0], 0.25); nt.links.new(sh, drift.inputs["Y"])
    p = M.vmath(nt, "SUBTRACT", co, drift.outputs[0])
    n1 = M.noise(nt, p, 0.045, 2.0, 0.5, dims="4D", w=M.math(nt, "MULTIPLY", val.outputs[0], 0.02))
    n2 = M.noise(nt, M.vmath(nt, "MULTIPLY", p, (1.0, 1.0, 2.5)), 0.22, 2.0, 0.55)
    fall = M.math(nt, "POWER", M.maprange(nt, sep.outputs["Z"], 0.0, 0.6, 1.0, 0.0), 1.4)
    fog = M.math(nt, "MULTIPLY", fall, M.maprange(nt, n1.outputs["Fac"], 0.35, 0.68, 0.15, 1.3))
    ax = M.math(nt, "ABSOLUTE", M.math(nt, "SUBTRACT", sep.outputs["X"], T.RUNWAY_CX))
    band = M.math(nt, "MAXIMUM", M.maprange(nt, M.math(nt, "ABSOLUTE", M.math(nt, "SUBTRACT", ax, RUNWAY_HALF)), 3.0, 9.0, 1.0, 0.0),
                  M.maprange(nt, M.math(nt, "ABSOLUTE", M.math(nt, "SUBTRACT", sep.outputs["Y"], T.Y_LOOP + 2)), 6.0, 18.0, 0.8, 0.0))
    smoke = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", band, M.maprange(nt, sep.outputs["Z"], 0.0, 0.6, 1.0, 0.0)),
                   M.maprange(nt, n2.outputs["Fac"], 0.5, 0.72, 0.0, 1.0))
    dens = M.math(nt, "ADD", M.math(nt, "MULTIPLY", fog, 0.035), M.math(nt, "MULTIPLY", smoke, 0.10))
    v = M.N(nt, "ShaderNodeVolumePrincipled"); M.S(nt, v.inputs["Density"], dens)
    v.inputs["Color"].default_value = (0.82, 0.84, 0.88, 1); v.inputs["Anisotropy"].default_value = 0.45
    M.out(nt, None, v.outputs[0]); return m

def haze_material():
    m, nt = M.new("Haze")
    if not nt: return m
    v = M.N(nt, "ShaderNodeVolumeScatter"); v.inputs["Density"].default_value = 0.0010; v.inputs["Anisotropy"].default_value = 0.6
    v.inputs["Color"].default_value = (0.85, 0.87, 0.9, 1)
    M.out(nt, None, v.outputs[0]); return m

# ---------------- loop ----------------
def loop_path(xc, th0, th1, n, plate=None):
    """samples of (centre, outward normal) along the riding surface"""
    pts = []
    if plate == "in":
        for k in range(20): pts.append((Vector((xc, T.Y_LOOP - 14 + 14 * k / 20, 0.0)), Vector((0, 0, -1))))
    for k in range(n + 1):
        th = th0 + (th1 - th0) * k / n
        pts.append((Vector((xc, T.Y_LOOP + T.R * math.sin(th), T.R * (1 - math.cos(th)))), Vector((0, math.sin(th), -math.cos(th)))))
    if plate == "out":
        for k in range(1, 21): pts.append((Vector((xc, T.Y_LOOP + 14 * k / 20, 0.0)), Vector((0, 0, -1))))
    return pts

def sweep(bm, path, prof, closed_prof=True, cap=True):
    secs = []
    for (c, n) in path:
        secs.append([bm.verts.new(c + Vector((u, 0, 0)) + n * v) for (u, v) in prof])
    m = len(prof)
    for a, b in zip(secs, secs[1:]):
        for i in range(m if closed_prof else m - 1):
            i2 = (i + 1) % m; bm.faces.new((a[i], a[i2], b[i2], b[i]))
    if cap: bm.faces.new(secs[0][::-1]); bm.faces.new(secs[-1])

def tube_prof(u, v, r, n=10):
    return [(u + r * math.cos(2 * math.pi * k / n), v + r * math.sin(2 * math.pi * k / n)) for k in range(n)]

def build_loop(coll):
    U = [(-1.70, 0.14), (1.70, 0.14), (1.70, -0.32), (1.62, -0.32), (1.62, 0.0), (-1.62, 0.0), (-1.62, -0.32), (-1.70, -0.32)]
    halves = [loop_path(T.X_LOOP, 0.0, math.pi, 220, "in"), loop_path(T.X_LOOP + T.X_DESC, T.TH_DESC0, 2 * math.pi, 200, "out")]
    bm = bmesh.new()
    for h in halves: sweep(bm, h, U)
    mesh("LoopTrack", bm, [steel()], coll)
    led = M.emission("LoopLED", (1.0, 0.52, 0.2), 22.0)
    bm = bmesh.new()
    for h in halves:
        for (u, v) in ((-1.66, -0.345), (1.66, -0.345), (-1.71, 0.15), (1.71, 0.15)):
            sweep(bm, h, tube_prof(u, v, 0.024))
    mesh("LoopLED", bm, [led], coll, smooth=True)
    bm = bmesh.new(); feet = bmesh.new()
    def col(x, y, ztop):
        CB.box(bm, (x, y, ztop / 2), (0.26, 0.26, ztop)); CB.box(feet, (x, y, 0.15), (0.9, 0.9, 0.3))
    for xc, ths in ((T.X_LOOP, (45, 90, 135, 180)), (T.X_LOOP + T.X_DESC, (225, 270, 315))):
        prev = None
        for th in ths:
            t = math.radians(th); y = T.Y_LOOP + (T.R + 0.14) * math.sin(t); zr = T.R * (1 - math.cos(t)) + 0.14 * (-math.cos(t))
            ztop = max(zr, 0.5) + (0.45 if th >= 90 else 0.0)
            for s in (-1, 1):
                col(xc + s * 2.35, y, ztop)
                CB.box(bm, (xc + s * 2.0, y, zr), (0.75, 0.2, 0.2))
                if prev:
                    py, pz = prev
                    for zz in (0.25 * min(ztop, pz), 0.6 * min(ztop, pz)):
                        CB.box(bm, (xc + s * 2.35, (y + py) / 2, zz), (0.12, abs(y - py), 0.12))
            if th == 180: CB.box(bm, (xc, y, ztop + 0.1), (4.9, 0.3, 0.3))
            prev = (y, ztop)
    mesh("LoopFrame", bm, [steel()], coll)
    mesh("Footings", feet, [concrete()], coll)

# ---------------- runway, markers, sky, distant set ----------------
def build_ground(coll):
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=500)
    mesh("Airfield", bm, [concrete()], coll).location.x = T.RUNWAY_CX

def build_markers(coll):
    red = M.emission("MarkerRed", (1.0, 0.03, 0.01), 40.0)
    bm, dome = bmesh.new(), bmesh.new(); lights = []
    for s in (-1, 1):
        for k in range(27):
            x, y = T.RUNWAY_CX + s * (RUNWAY_HALF + 0.6), -30 + 12 * k
            c = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.13, radius2=0.11, depth=0.14)
            for v in c["verts"]: v.co += Vector((x, y, 0.07))
            d = bmesh.ops.create_uvsphere(dome, u_segments=16, v_segments=8, radius=0.085)
            for v in d["verts"]: v.co = Vector((v.co.x, v.co.y, max(v.co.z, 0.0) * 0.8)) + Vector((x, y, 0.14))
            ld = bpy.data.lights.new("Marker", "POINT"); ld.energy = 14; ld.color = (1.0, 0.05, 0.02); ld.shadow_soft_size = 0.06
            lo = bpy.data.objects.new("Marker", ld); coll.objects.link(lo); lo.location = (x, y, 0.22); lights.append(lo)
    mesh("MarkerBases", bm, [steel()], coll); mesh("MarkerDomes", dome, [red], coll, smooth=True)
    return lights

def build_distant(coll):
    bm = bmesh.new(); win = bmesh.new()
    for i, (x, w, h) in enumerate(((-120, 70, 22), (-30, 60, 18), (60, 80, 24), (150, 50, 16))):
        CB.box(bm, (x, 330, h / 2), (w, 40, h))
        for k in range(int(w // 9)):
            CB.box(win, (x - w / 2 + 6 + 9 * k, 309.9, 3.0 + (k % 2) * 0.6), (2.2, 0.2, 1.2))
    CB.box(bm, (95, 290, 21), (0.6, 0.6, 42))
    mesh("Hangars", bm, [M.simple("HangarDark", (0.02, 0.02, 0.022), 0.7)], coll)
    mesh("HangarWindows", win, [M.emission("WarmWindow", (1.0, 0.62, 0.3), 6.0)], coll)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=0.35)
    for v in bm.verts: v.co += Vector((95, 290, 42.3))
    beacon = M.emission("Beacon", (1.0, 0.05, 0.02), 80.0)
    mesh("Beacon", bm, [beacon], coll, smooth=True)
    e = beacon.node_tree.nodes["Emission"].inputs["Strength"]
    FT = T.FRAME_T or [(f - 1) / T.FPS for f in range(1, T.FRAMES + 1)]
    for f in range(1, T.FRAMES + 1):                                   # blinks on the story clock (slows in slow-mo)
        e.default_value = 80.0 * (1.0 if int(FT[f - 1] / 0.75) % 2 == 0 else 0.0); e.keyframe_insert("default_value", frame=f)
    for fc in beacon.node_tree.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "CONSTANT"

def build_volumes(coll):
    bm = bmesh.new(); CB.box(bm, (T.RUNWAY_CX, 85, 0.25), (130, 230, 0.9))
    fog = mesh("GroundFog", bm, [fog_material()], coll); fog.visible_shadow = False
    haze = None   # no scene-wide volume: fog only as a thin ground layer
    d = fog.active_material.node_tree.nodes["drift"].outputs[0]
    FT = T.FRAME_T or [(f - 1) / T.FPS for f in range(1, T.FRAMES + 1)]
    for f in range(1, T.FRAMES + 1):
        d.default_value = 0.7 * FT[f - 1]; d.keyframe_insert("default_value", frame=f)
    for fc in fog.active_material.node_tree.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    return fog, haze

def build_sky(scene):
    w = bpy.data.worlds.new("Night"); scene.world = w; w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
    tc = M.N(nt, "ShaderNodeTexCoord"); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    t = M.maprange(nt, sep.outputs["Z"], -0.02, 0.35, 0.0, 1.0)
    col = M.mix(nt, t, (0.020, 0.015, 0.013, 1), (0.0018, 0.0026, 0.0048, 1))
    bg = M.N(nt, "ShaderNodeBackground"); M.S(nt, bg.inputs["Color"], col); bg.inputs["Strength"].default_value = 1.0
    o = M.N(nt, "ShaderNodeOutputWorld"); nt.links.new(bg.outputs[0], o.inputs["Surface"])
    ld = bpy.data.lights.new("Moon", "SUN"); ld.energy = 0.3; ld.color = (0.62, 0.72, 1.0); ld.angle = math.radians(0.6)
    mo = bpy.data.objects.new("Moon", ld); scene.collection.objects.link(mo)
    mo.rotation_euler = (math.radians(68), 0, math.radians(200))

def build_floodlights(coll):
    """light masts. v2: two masts aimed at the loop top and the flight path (key + rim), one keeps the landing/final look"""
    head = M.emission("FloodHead", (0.85, 0.9, 1.0), 20.0); SD = _stop_d()
    bm, hb = bmesh.new(), bmesh.new()
    top = (T.X_LOOP, T.Y_LOOP, 17.5); mid = (T.X_LOOP, T.Y_LOOP - 16, 8.0); low = (T.X_LOOP, T.Y_LOOP - 22, 4.0)
    masts = (((T.X_LOOP + 34, T.Y_LOOP + 26, 22), ((top, 30000, 30), (mid, 30000, 34))),        # behind the loop: key on the top + rim on the flight
             ((-24, 52, 20), (((T.X_LOOP, T.Y_LOOP - 6, 14), 25000, 34), (low, 25000, 38))),   # left side: key on the flight
             ((48, 8, 18), (((20 + SD[0], 14 + SD[1], 0), 7000, 70), ((20 + SD[0], 14 + SD[1], 0), 7000, 70))))                # landing / final (as v1)
    for (x, y, h), spots in masts:
        CB.box(bm, (x, y, h / 2), (0.45, 0.45, h))
        for k, (tgt, energy, cone) in enumerate(spots):
            p = Vector((x, y, h + 0.6)) + Vector((0, 0, 0)) + Vector(((-0.9, 0.9)[k], 0, 0))
            d = (Vector(tgt) - p).normalized()
            CB.box(hb, tuple(p + d * 0.35), (0.9, 0.9, 0.12))
            ld = bpy.data.lights.new("Flood", "SPOT"); ld.energy = energy; ld.spot_size = math.radians(cone); ld.spot_blend = 0.5
            ld.shadow_soft_size = 0.5; ld.color = (0.85, 0.9, 1.0)
            lo = bpy.data.objects.new("Flood", ld); coll.objects.link(lo); lo.location = p
            lo.rotation_mode = "QUATERNION"; lo.rotation_quaternion = d.to_track_quat("-Z", "Y")
    mesh("FloodMasts", bm, [steel()], coll); mesh("FloodHeads", hb, [head], coll)

def build(scene):
    coll = bpy.data.collections.new("Environment"); scene.collection.children.link(coll)
    build_ground(coll); build_loop(coll); build_markers(coll); build_distant(coll); build_floodlights(coll)
    build_volumes(coll); build_sky(scene)
    return coll

# ---------------- v2.2: the car is lit for the whole flight ----------------
BEAM_DENS = 0.030
UPLIGHTS = (   # ground fixture, aim point on the flight path, energy W, cone (full angle, deg)
    ((15.5, 57.0, 0.35), (T.X_LOOP, 55.5, 16.3), 9000, 18),     # left, near the top: the car right after the detach
    ((35.5, 50.5, 0.35), (T.X_LOOP, 51.5, 14.6), 9000, 18),     # right: mid-roll
    ((12.5, 50.0, 0.35), (T.X_LOOP, 48.5, 13.3), 9000, 18),     # left: end of the roll (underside towards camera B)
    ((34.5, 40.0, 0.35), (T.X_LOOP, 43.0, 9.6), 8000, 20),      # right: descent
)
RIM_POS, FILL_POS = (30.0, 84.0, 24.0), (17.0, 33.0, 0.45)

def beam_material():
    """local volumetric beam: soft-edged cone of haze lit by its own spot, fades in near the lamp and out with height"""
    m, nt = M.new("FloodBeam")
    if not nt: return m
    m.cycles.volume_step_rate = 0.08
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    z = sep.outputs["Z"]
    L = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="blen").outputs["Fac"]
    tn = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="btan").outputs["Fac"]
    r = M.vmath(nt, "LENGTH", M.vmath(nt, "MULTIPLY", co, (1.0, 1.0, 0.0)))
    w = M.math(nt, "ADD", M.math(nt, "MULTIPLY", z, tn), 0.12)
    radial = M.math(nt, "POWER", M.maprange(nt, M.math(nt, "DIVIDE", r, w), 0.0, 1.0, 1.0, 0.0), 1.3)
    along = M.math(nt, "MULTIPLY", M.maprange(nt, z, 0.3, 3.5, 0.0, 1.0), M.maprange(nt, M.math(nt, "DIVIDE", z, L), 0.45, 1.0, 1.0, 0.0))
    n = M.noise(nt, M.vmath(nt, "MULTIPLY", co, (1.0, 1.0, 0.35)), 0.35, 3.0, 0.55)
    tex = M.maprange(nt, n.outputs["Fac"], 0.3, 0.7, 0.55, 1.35)
    d = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", radial, along), M.math(nt, "MULTIPLY", tex, BEAM_DENS))
    v = M.N(nt, "ShaderNodeVolumePrincipled"); M.S(nt, v.inputs["Density"], d)
    v.inputs["Color"].default_value = (0.9, 0.92, 0.95, 1); v.inputs["Anisotropy"].default_value = 0.2
    M.out(nt, None, v.outputs[0]); return m

def _fixture(bm_body, bm_lens, p, d, radius=0.32, depth=0.42):
    """drum-shaped lamp head pointing along d"""
    from mathutils import Matrix
    q = Vector(d).to_track_quat("Z", "Y"); Mx = Matrix.Translation(Vector(p)) @ q.to_matrix().to_4x4()
    c = bmesh.ops.create_cone(bm_body, cap_ends=True, segments=20, radius1=radius, radius2=radius, depth=depth)
    bmesh.ops.transform(bm_body, matrix=Mx, verts=c["verts"])
    c = bmesh.ops.create_cone(bm_lens, cap_ends=True, segments=20, radius1=radius * 0.85, radius2=radius * 0.85, depth=0.02)
    bmesh.ops.transform(bm_lens, matrix=Mx @ Matrix.Translation((0, 0, depth / 2 + 0.01)), verts=c["verts"])

def _key_energy(ld, fn):
    FT = T.FRAME_T
    for f in range(1, T.FRAMES + 1):
        ld.energy = fn(FT[f - 1]); ld.keyframe_insert("energy", frame=f)

def build_flight_lights(coll, root):
    ev = T.EV; ss = T.sstep
    head = bpy.data.materials.get("FloodHead") or M.emission("FloodHead", (0.85, 0.9, 1.0), 20.0)
    bm_body, bm_lens, bm_pole = bmesh.new(), bmesh.new(), bmesh.new()
    beam_m = beam_material()
    for i, (p, tgt, energy, cone) in enumerate(UPLIGHTS):
        d = (Vector(tgt) - Vector(p)).normalized()
        _fixture(bm_body, bm_lens, p, d)
        CB.box(bm_body, (p[0], p[1], 0.08), (0.9, 0.9, 0.16))
        ld = bpy.data.lights.new(f"UpLight{i}", "SPOT"); ld.energy = energy; ld.spot_size = math.radians(cone); ld.spot_blend = 0.3
        ld.shadow_soft_size = 0.15; ld.color = (0.86, 0.9, 1.0)
        lo = bpy.data.objects.new(f"UpLight{i}", ld); coll.objects.link(lo); lo.location = Vector(p) + d * 0.25
        lo.rotation_mode = "QUATERNION"; lo.rotation_quaternion = d.to_track_quat("-Z", "Y")
        L = 30.0; tn = math.tan(math.radians(cone / 2) * 1.15)
        bm = bmesh.new(); c = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.12, radius2=0.12 + L * tn, depth=L)
        for v in c["verts"]: v.co.z += L / 2
        ob = mesh(f"Beam{i}", bm, [beam_m], coll); ob.visible_shadow = False
        ob.location = Vector(p) + d * 0.25; ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = d.to_track_quat("Z", "Y")
        ob["blen"] = L; ob["btan"] = tn
    # follow spots (operator-aimed, as in a stunt show): rim from behind the loop, fill on the underside from the ground
    CB.box(bm_pole, (RIM_POS[0], RIM_POS[1], RIM_POS[2] / 2), (0.45, 0.45, RIM_POS[2]))
    for name, pos, energy, cone, col, fn in (
            ("RimFollow", (RIM_POS[0], RIM_POS[1], RIM_POS[2] + 0.6), 60000, 9, (0.85, 0.9, 1.0),
             lambda t: 60000 * ss(ev["t_loop"] - 0.6, ev["t_loop"] - 0.2, t) * (1 - ss(ev["t_land"] + 0.1, ev["t_land"] + 0.8, t))),
            ("UnderFill", FILL_POS, 36000, 9, (1.0, 0.93, 0.84),
             lambda t: 36000 * ss(ev["t_top"] - 0.35, ev["t_top"] - 0.1, t) * (1 - ss(ev["t_land"] - 0.55, ev["t_land"] - 0.25, t)))):
        tgt = Vector((T.X_LOOP, 52.0, 14.0)); d = (tgt - Vector(pos)).normalized()
        _fixture(bm_body, bm_lens, pos, d, 0.38, 0.5)
        ld = bpy.data.lights.new(name, "SPOT"); ld.energy = energy; ld.spot_size = math.radians(cone); ld.spot_blend = 0.35
        ld.shadow_soft_size = 0.2; ld.color = col
        lo = bpy.data.objects.new(name, ld); coll.objects.link(lo); lo.location = Vector(pos) + d * 0.3
        c = lo.constraints.new("TRACK_TO"); c.target = root; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
        _key_energy(ld, fn)
    if FILL_POS[2] < 1.0: CB.box(bm_body, (FILL_POS[0], FILL_POS[1], 0.08), (0.9, 0.9, 0.16))
    mesh("FlightLampBodies", bm_body, [steel()], coll); mesh("FlightLampHeads", bm_lens, [head], coll); mesh("RimTower", bm_pole, [steel()], coll)
    # warm spill from the loop LEDs under the top of the loop (the car's underside faces them right after the detach)
    for sx in (-1, 1):
        for y in (T.Y_LOOP - 1.5, T.Y_LOOP, T.Y_LOOP + 1.5):
            ld = bpy.data.lights.new("LEDSpill", "POINT"); ld.energy = 450; ld.color = (1.0, 0.52, 0.2); ld.shadow_soft_size = 0.05
            lo = bpy.data.objects.new("LEDSpill", ld); coll.objects.link(lo); lo.location = (T.X_LOOP + sx * 1.50, y, 2 * T.R - 0.55)
            try: lo.visible_camera = False
            except Exception: pass
    build_loop_reflection(coll)
    build_paint_cards(coll)
    print("flight lights:", len(UPLIGHTS), "uplights + beams, rim/fill follow spots, LED spill, loop reflection glow", flush=True)

def build_loop_reflection(coll):
    """glossy-only warm copy of the loop LEDs: invisible to the camera and to diffuse light, it only shows up in reflections,
    so the off-frame loop reads as warm highlights sliding over the paint in the opening shot (a slow chase runs along it).
    Switched off right after the pass-by."""
    ev = T.EV; ss = T.sstep
    m, nt = M.new("LoopReflGlow")
    try: m.cycles.emission_sampling = "NONE"
    except Exception: pass
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    ang = M.math(nt, "ARCTAN2", M.math(nt, "SUBTRACT", sep.outputs["Z"], T.R), M.math(nt, "SUBTRACT", sep.outputs["Y"], T.Y_LOOP))
    chase = M.N(nt, "ShaderNodeValue"); chase.name = "chase"; on = M.N(nt, "ShaderNodeValue"); on.name = "on"
    wave = M.math(nt, "SINE", M.math(nt, "SUBTRACT", M.math(nt, "MULTIPLY", ang, 3.0), chase.outputs[0]))
    k = M.math(nt, "ADD", M.math(nt, "MULTIPLY", wave, 0.45), 0.55)
    lp = M.N(nt, "ShaderNodeLightPath")
    st = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", k, lp.outputs["Is Glossy Ray"]), M.math(nt, "MULTIPLY", on.outputs[0], 9.0))
    em = M.N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.52, 0.2, 1); M.S(nt, em.inputs["Strength"], st)
    tr = M.N(nt, "ShaderNodeBsdfTransparent"); ad = M.N(nt, "ShaderNodeAddShader")      # see-through when dark: never blocks the real LEDs
    nt.links.new(em.outputs[0], ad.inputs[0]); nt.links.new(tr.outputs[0], ad.inputs[1])
    M.out(nt, ad.outputs[0])
    halves = [loop_path(T.X_LOOP, 0.0, math.pi, 160), loop_path(T.X_LOOP + T.X_DESC, T.TH_DESC0, 2 * math.pi, 140)]
    bm = bmesh.new()
    for h in halves:
        for (u, v) in ((-1.66, -0.345), (1.66, -0.345)):
            sweep(bm, h, tube_prof(u, v - 0.45, 0.45, 8))
    ob = mesh("LoopReflGlow", bm, [m], coll)
    for attr in ("visible_camera", "visible_diffuse", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
        try: setattr(ob, attr, False)
        except Exception: pass
    FT = T.FRAME_T; c, o = chase.outputs[0], on.outputs[0]
    for f in range(1, T.FRAMES + 1):
        t = FT[f - 1]; c.default_value = 4.0 * t; o.default_value = 1.0 - ss(ev["t_pass"] - 0.2, ev["t_pass"] + 0.3, t)
        c.keyframe_insert("default_value", frame=f); o.keyframe_insert("default_value", frame=f)

def build_paint_cards(coll):
    """reflection-only warm light cards (as on a car-commercial set) on an arc left/behind the waiting car: the flank and the
    rear quarter mirror them, the camera never sees them; bands chase along the arc so warm highlights run over the paint.
    Off right after the pass-by."""
    ev = T.EV; ss = T.sstep; sx, sy = T.START
    m, nt = M.new("PaintCardGlow")
    try: m.cycles.emission_sampling = "NONE"
    except Exception: pass
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    az = M.math(nt, "ARCTAN2", M.math(nt, "SUBTRACT", sep.outputs["X"], sx), M.math(nt, "SUBTRACT", sep.outputs["Y"], sy))
    chase = M.N(nt, "ShaderNodeValue"); on = M.N(nt, "ShaderNodeValue")
    wave = M.math(nt, "SINE", M.math(nt, "SUBTRACT", M.math(nt, "MULTIPLY", az, 7.0), chase.outputs[0]))
    k = M.math(nt, "ADD", M.math(nt, "MULTIPLY", wave, 0.5), 0.5)
    lp = M.N(nt, "ShaderNodeLightPath")
    st = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", k, lp.outputs["Is Glossy Ray"]), M.math(nt, "MULTIPLY", on.outputs[0], 20.0))
    em = M.N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.55, 0.22, 1); M.S(nt, em.inputs["Strength"], st)
    tr = M.N(nt, "ShaderNodeBsdfTransparent"); ad = M.N(nt, "ShaderNodeAddShader")
    nt.links.new(em.outputs[0], ad.inputs[0]); nt.links.new(tr.outputs[0], ad.inputs[1]); M.out(nt, ad.outputs[0])
    bm = bmesh.new(); RR = 12.0; n = 48
    for (z0, hgt) in ((0.3, 0.3), (0.85, 0.3), (1.45, 0.4), (2.4, 0.5)):
        ring = []
        for i in range(n + 1):
            a = math.radians(-165 + 100 * i / n)
            x, y = sx + RR * math.sin(a), sy + RR * math.cos(a)
            ring.append((bm.verts.new((x, y, z0)), bm.verts.new((x, y, z0 + hgt))))
        for (a0, a1), (b0, b1) in zip(ring, ring[1:]): bm.faces.new((a0, b0, b1, a1))
    ob = mesh("PaintCards", bm, [m], coll)
    for attr in ("visible_camera", "visible_diffuse", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
        try: setattr(ob, attr, False)
        except Exception: pass
    FT = T.FRAME_T; c, o = chase.outputs[0], on.outputs[0]
    for f in range(1, T.FRAMES + 1):
        t = FT[f - 1]; c.default_value = 3.0 * t; o.default_value = 1.0 - ss(ev["t_pass"] - 0.15, ev["t_pass"] + 0.3, t)
        c.keyframe_insert("default_value", frame=f); o.keyframe_insert("default_value", frame=f)
