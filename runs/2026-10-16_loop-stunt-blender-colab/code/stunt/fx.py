"""Compressed-air jets (bright white streaks + lights) and landing / slide / retro dust puffs."""
import bpy, bmesh, math, random
from mathutils import Vector
import materials as M, traj as T, car_wheels as CW

def jet_material():
    m, nt = M.new("AirJet")
    if not nt: return m
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    at = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="pw")
    along = M.math(nt, "POWER", M.maprange(nt, sep.outputs["Z"], 0.0, 1.0, 1.0, 0.0), 2.2)
    lw = M.N(nt, "ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.35
    core = M.math(nt, "POWER", M.math(nt, "SUBTRACT", 1.0, lw.outputs["Facing"]), 2.0)
    n = M.noise(nt, M.vmath(nt, "MULTIPLY", co, (8.0, 8.0, 2.0)), 3.0, 3.0, 0.6, dims="4D", w=at.outputs["Fac"])
    fac = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", along, core), M.math(nt, "MULTIPLY", at.outputs["Fac"], M.maprange(nt, n.outputs["Fac"], 0.3, 0.7, 0.4, 1.0)), clamp=True)
    em = M.N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (0.92, 0.96, 1.0, 1); em.inputs["Strength"].default_value = 70.0
    tr = M.N(nt, "ShaderNodeBsdfTransparent")
    mx = M.N(nt, "ShaderNodeMixShader"); M.S(nt, mx.inputs[0], fac); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    M.out(nt, mx.outputs[0]); return m

def dust_material():
    m, nt = M.new("Dust")
    if not nt: return m
    m.cycles.volume_step_rate = 0.5
    co = M.coords(nt)
    at = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="dens")
    sd = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="seed")
    r = M.vmath(nt, "LENGTH", co)
    shape = M.maprange(nt, r, 0.25, 1.0, 1.0, 0.0)
    n = M.noise(nt, co, 2.4, 5.0, 0.62, dims="4D", w=sd.outputs["Fac"])
    d = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", shape, M.maprange(nt, n.outputs["Fac"], 0.42, 0.7, 0.0, 1.0)), at.outputs["Fac"])
    v = M.N(nt, "ShaderNodeVolumePrincipled"); M.S(nt, v.inputs["Density"], d)
    v.inputs["Color"].default_value = (0.60, 0.57, 0.52, 1); v.inputs["Anisotropy"].default_value = 0.3
    M.out(nt, None, v.outputs[0]); return m

def build_jets(coll, rig, S):
    mat = jet_material(); jets = {}
    for name, (p, d) in T.JETS.items():
        bm = bmesh.new()
        c = bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.022, radius2=0.17, depth=1.0)
        for v in c["verts"]: v.co.z += 0.5
        ob = CW.mesh_obj("Jet_" + name, bm, [mat], coll, rig)
        ob.location = Vector(p) + Vector(d) * 0.06
        ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = Vector(d).to_track_quat("Z", "Y")
        ob.visible_shadow = False
        ld = bpy.data.lights.new("JetLight_" + name, "POINT"); ld.color = (0.9, 0.95, 1.0); ld.shadow_soft_size = 0.15
        lo = bpy.data.objects.new("JetLight_" + name, ld); coll.objects.link(lo); lo.parent = rig
        lo.location = Vector(p) + Vector(d) * 0.35
        jets[name] = (ob, lo)
    # per-frame power = max over the substeps within +-0.5 frame (short pulses must not be missed)
    for f in range(1, T.FRAMES + 1):
        k0 = max(0, (f - 1) * T.SUB - T.SUB // 2); k1 = min(len(S), (f - 1) * T.SUB + T.SUB // 2)
        for name, (ob, lo) in jets.items():
            pw = min(max([S[k]["jets"].get(name, 0.0) for k in range(k0, k1)] + [0.0]), 1.6)
            ob["pw"] = pw; ob.keyframe_insert('["pw"]', frame=f)
            L = 0.15 + 1.5 * min(pw, 1.0) ** 0.6 * (1.25 if pw > 1.05 else 1.0)
            ob.scale = (1.0, 1.0, L); ob.keyframe_insert("scale", frame=f)
            lo.data.energy = 700.0 * pw; lo.data.keyframe_insert("energy", frame=f)
    return jets

def build_dust(coll, S, ev):
    mat = dust_material(); rnd = random.Random(7); puffs = []
    def frame_of(t): return int(round(t * T.FPS)) + 1
    def sample(t): return S[min(len(S) - 1, int(round(t / T.DT)))]
    spawns = []
    tr = ev.get("t_retro", ev["t_land"] - 0.5)
    for k in range(4):                                    # retro jets hitting the ground
        t = tr + 0.12 + 0.11 * k; s = sample(t)
        if s["cg"][2] < 7.5:
            c = s["cg"]; spawns.append((t, (c[0] + rnd.uniform(-0.8, 0.8), c[1] + rnd.uniform(-1, 1), 0.3), 0.5, 3.6, 1.1, (0, 0, 0.6)))
    s = sample(ev["t_land"])                              # touchdown
    for side in (-1, 1):
        for ay in (T.AXLE_F, T.AXLE_R):
            p = Vector(s["pos"]) + Vector(s["X"]) * side * 0.9 + Vector(s["Y"]) * ay
            spawns.append((ev["t_land"] + rnd.uniform(0, 0.04), (p.x, p.y, 0.25), 0.4, 2.6, 1.3, (side * 1.5, -2.0, 0.5)))
    spawns.append((ev["t_land"] + 0.03, (s["pos"][0], s["pos"][1], 0.3), 0.8, 3.4, 0.9, (0, -3.0, 0.4)))
    for i, (t, hub, sp) in enumerate(ev["trail"]):        # slide trail (rear wheels)
        if i % 2: continue
        spawns.append((t, (hub[0], hub[1], 0.25), 0.3, 1.2 + 0.09 * sp, 0.55 + 0.03 * sp, (0, 0, 0.3)))
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
                grow = 1 - math.exp(-tau / 0.45); r = r0 + (r1 - r0) * grow
                drift = Vector(vel) * (0.6 * (1 - math.exp(-tau / 0.6))) + Vector((0.35, 0.1, 0.18)) * tau
                ob.location = Vector(pos) + drift + Vector((0, 0, 0.35 * r))
                ob.scale = (r, r, r * 0.55)
                ob["dens"] = dmax * min(1.0, tau / 0.06) * math.exp(-tau / 1.6)
            ob.keyframe_insert("location", frame=f); ob.keyframe_insert("scale", frame=f); ob.keyframe_insert('["dens"]', frame=f)
        if f0 > 2:
            ob.location = pos; ob.scale = (0.001,) * 3; ob["dens"] = 0.0
            for k in ("location", "scale"): ob.keyframe_insert(k, frame=1)
            ob.keyframe_insert('["dens"]', frame=1)
        puffs.append(ob)
    print("dust puffs:", len(puffs), flush=True)
    return puffs
