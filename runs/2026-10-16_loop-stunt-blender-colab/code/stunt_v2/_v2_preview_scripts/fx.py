"""v2 FX: crisp compressed-air jets (bright core cone 1-1.5 m + light volumetric trail) and compact landing dust."""
import bpy, bmesh, math, random
from mathutils import Vector
import materials as M, traj as T, car_wheels as CW

def jet_core_material():
    """bright white core near the nozzle, fading along the cone; edges transparent"""
    m, nt = M.new("AirJetCore")
    if not nt: return m
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    pw = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="pw").outputs["Fac"]
    along = M.math(nt, "POWER", M.maprange(nt, sep.outputs["Z"], 0.0, 1.0, 1.0, 0.0), 1.8)
    lw = M.N(nt, "ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.25
    core = M.math(nt, "POWER", M.math(nt, "SUBTRACT", 1.0, lw.outputs["Facing"]), 3.0)
    n = M.noise(nt, M.vmath(nt, "MULTIPLY", co, (10.0, 10.0, 3.0)), 2.5, 2.0, 0.5, dims="4D", w=M.math(nt, "MULTIPLY", pw, 7.0))
    fac = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", along, core), M.math(nt, "MULTIPLY", M.math(nt, "MINIMUM", pw, 1.0), M.maprange(nt, n.outputs["Fac"], 0.3, 0.7, 0.75, 1.0)), clamp=True)
    em = M.N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (0.94, 0.97, 1.0, 1); em.inputs["Strength"].default_value = 160.0
    tr = M.N(nt, "ShaderNodeBsdfTransparent")
    mx = M.N(nt, "ShaderNodeMixShader"); M.S(nt, mx.inputs[0], fac); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    M.out(nt, mx.outputs[0]); return m

def jet_trail_material():
    """light volumetric wake around and behind the core"""
    m, nt = M.new("AirJetTrail")
    if not nt: return m
    m.cycles.volume_step_rate = 0.5
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    tr = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="trail").outputs["Fac"]
    rad = M.vmath(nt, "LENGTH", M.vmath(nt, "MULTIPLY", co, (1.0, 1.0, 0.0)))
    along = M.maprange(nt, sep.outputs["Z"], 0.0, 1.0, 1.0, 0.15)
    radial = M.maprange(nt, M.math(nt, "DIVIDE", rad, M.math(nt, "ADD", M.math(nt, "MULTIPLY", sep.outputs["Z"], 0.30), 0.03)), 0.2, 1.0, 1.0, 0.0)
    n = M.noise(nt, M.vmath(nt, "MULTIPLY", co, (6.0, 6.0, 2.0)), 3.0, 4.0, 0.6, dims="4D", w=M.math(nt, "MULTIPLY", tr, 5.0))
    d = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", along, radial), M.maprange(nt, n.outputs["Fac"], 0.35, 0.7, 0.0, 1.0)), M.math(nt, "MULTIPLY", tr, 2.2))
    v = M.N(nt, "ShaderNodeVolumePrincipled"); M.S(nt, v.inputs["Density"], d)
    v.inputs["Color"].default_value = (0.92, 0.94, 0.97, 1); v.inputs["Anisotropy"].default_value = 0.4
    M.S(nt, v.inputs["Emission Strength"], M.math(nt, "MULTIPLY", d, 0.6)); v.inputs["Emission Color"].default_value = (0.9, 0.95, 1.0, 1)
    M.out(nt, None, v.outputs[0]); return m

def _cone(name, r1, r2, mat, coll, rig, p, d):
    bm = bmesh.new()
    c = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r1, radius2=r2, depth=1.0)
    for v in c["verts"]: v.co.z += 0.5
    ob = CW.mesh_obj(name, bm, [mat], coll, rig)
    ob.location = Vector(p) + Vector(d) * 0.07
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = Vector(d).to_track_quat("Z", "Y")
    ob.visible_shadow = False
    return ob

def build_jets(coll, rig, S):
    core_m, trail_m = jet_core_material(), jet_trail_material(); jets = {}
    for name, (p, d) in T.JETS.items():
        core = _cone("Jet_" + name, 0.014, 0.075, core_m, coll, rig, p, d)
        trail = _cone("JetTrail_" + name, 0.03, 0.30, trail_m, coll, rig, p, d)
        ld = bpy.data.lights.new("JetLight_" + name, "POINT"); ld.color = (0.9, 0.95, 1.0); ld.shadow_soft_size = 0.05
        lo = bpy.data.objects.new("JetLight_" + name, ld); coll.objects.link(lo); lo.parent = rig
        lo.location = Vector(p) + Vector(d) * 0.25
        jets[name] = (core, trail, lo)
    trail_state = {k: 0.0 for k in jets}
    for f in range(1, T.FRAMES + 1):
        k0 = max(0, (f - 1) * T.SUB - T.SUB // 2); k1 = min(len(S), (f - 1) * T.SUB + T.SUB // 2)
        for name, (core, trail, lo) in jets.items():
            pw = min(max([S[k]["jets"].get(name, 0.0) for k in range(k0, k1)] + [0.0]), 1.8)
            trail_state[name] = max(pw, trail_state[name] * math.exp(-(1.0 / T.FPS) / 0.25))
            L = 0.25 + (1.0 if pw <= 1.05 else 1.25) * min(pw, 1.0) ** 0.5          # 1.25 m, retro bursts 1.5 m
            core["pw"] = pw; core.keyframe_insert('["pw"]', frame=f)
            core.scale = (1.0, 1.0, L if pw > 0.01 else 0.01); core.keyframe_insert("scale", frame=f)
            tr = trail_state[name] if trail_state[name] > 0.01 else 0.0
            trail["trail"] = tr; trail.keyframe_insert('["trail"]', frame=f)
            trail.scale = (1.0, 1.0, (0.4 + 1.5 * min(tr, 1.0) ** 0.5) if tr > 0 else 0.01); trail.keyframe_insert("scale", frame=f)
            lo.data.energy = 150.0 * pw; lo.data.keyframe_insert("energy", frame=f)
    for ob in bpy.data.objects:
        if ob.name.startswith(("Jet_", "JetTrail_")) and ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    return jets

def dust_material():
    m, nt = M.new("Dust")
    if not nt: return m
    m.cycles.volume_step_rate = 0.5
    co = M.coords(nt)
    at = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="dens")
    sd = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="seed")
    shape = M.maprange(nt, M.vmath(nt, "LENGTH", co), 0.25, 1.0, 1.0, 0.0)
    n = M.noise(nt, co, 2.4, 5.0, 0.62, dims="4D", w=sd.outputs["Fac"])
    d = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", shape, M.maprange(nt, n.outputs["Fac"], 0.42, 0.7, 0.0, 1.0)), at.outputs["Fac"])
    v = M.N(nt, "ShaderNodeVolumePrincipled"); M.S(nt, v.inputs["Density"], d)
    v.inputs["Color"].default_value = (0.60, 0.57, 0.52, 1); v.inputs["Anisotropy"].default_value = 0.3
    M.out(nt, None, v.outputs[0]); return m

def build_dust(coll, S, ev):
    """v2: compact clouds at the wheels, gone in ~1.5-2 s"""
    mat = dust_material(); rnd = random.Random(7); puffs = []
    def frame_of(t): return int(round(t * T.FPS)) + 1
    def sample(t): return S[min(len(S) - 1, int(round(t / T.DT)))]
    spawns = []
    tr = ev.get("t_retro", ev["t_land"] - 0.5)
    for k in range(3):                                     # retro jets hitting the ground (small, low)
        t = tr + 0.25 + 0.1 * k; s = sample(t)
        if s["cg"][2] < 4.0:
            c = s["cg"]; spawns.append((t, (c[0] + rnd.uniform(-0.5, 0.5), c[1] + rnd.uniform(-0.6, 0.6), 0.2), 0.3, 1.5, 0.9, (0, 0, 0.3)))
    s = sample(ev["t_land"])                               # touchdown, at the four wheels
    for side in (-1, 1):
        for ay in (T.AXLE_F, T.AXLE_R):
            p = Vector(s["pos"]) + Vector(s["X"]) * side * 0.9 + Vector(s["Y"]) * ay
            spawns.append((ev["t_land"] + rnd.uniform(0, 0.03), (p.x, p.y, 0.15), 0.25, 1.3, 1.4, (side * 1.0, -1.5, 0.3)))
    for i, (t, hub, sp) in enumerate(ev["trail"]):         # slide trail (rear wheels), short-lived
        if i % 2: continue
        spawns.append((t, (hub[0], hub[1], 0.15), 0.2, 0.55 + 0.04 * sp, 0.45 + 0.03 * sp, (0, 0, 0.2)))
    for n, (t0, pos, r0, r1, dmax, vel) in enumerate(spawns):
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        ob = CW.mesh_obj(f"Dust{n:02d}", bm, [mat], coll, None, smooth=False)
        ob.visible_shadow = False; ob["seed"] = rnd.uniform(0, 100)
        f0 = frame_of(t0)
        for f in range(max(1, f0 - 1), T.FRAMES + 1):
            tau = (f - 1) / T.FPS - t0
            if tau < 0:
                ob.location = pos; ob.scale = (0.001,) * 3; ob["dens"] = 0.0
            else:
                r = r0 + (r1 - r0) * (1 - math.exp(-tau / 0.35))
                drift = Vector(vel) * (0.5 * (1 - math.exp(-tau / 0.5))) + Vector((0.25, 0.08, 0.10)) * tau
                ob.location = Vector(pos) + drift + Vector((0, 0, 0.3 * r))
                ob.scale = (r, r, r * 0.5)
                ob["dens"] = dmax * min(1.0, tau / 0.05) * math.exp(-tau / 0.55)
            ob.keyframe_insert("location", frame=f); ob.keyframe_insert("scale", frame=f); ob.keyframe_insert('["dens"]', frame=f)
        if f0 > 2:
            ob.location = pos; ob.scale = (0.001,) * 3; ob["dens"] = 0.0
            for k in ("location", "scale"): ob.keyframe_insert(k, frame=1)
            ob.keyframe_insert('["dens"]', frame=1)
        puffs.append(ob)
    print("dust puffs:", len(puffs), flush=True)
    return puffs
