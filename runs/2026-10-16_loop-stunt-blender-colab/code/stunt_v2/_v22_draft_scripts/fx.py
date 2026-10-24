"""v2.1 FX: gas jets (narrow hot core + widening, fast-fading turbulent plume), compact landing dust. Keys follow the story clock."""
import bpy, bmesh, math, random
from mathutils import Vector
import materials as M, traj as T, car_wheels as CW

def jet_core_material():
    m, nt = M.new("AirJetCore")
    if not nt: return m
    pw = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="pw").outputs["Fac"]
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    lw = M.N(nt, "ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.4
    soft = M.math(nt, "POWER", M.math(nt, "SUBTRACT", 1.0, lw.outputs["Facing"]), 2.0)
    fac = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", soft, M.maprange(nt, sep.outputs["Z"], 0.0, 1.0, 1.0, 0.0)), M.math(nt, "MINIMUM", pw, 1.0), clamp=True)
    em = M.N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (0.96, 0.98, 1.0, 1); em.inputs["Strength"].default_value = 140.0
    tr = M.N(nt, "ShaderNodeBsdfTransparent")
    mx = M.N(nt, "ShaderNodeMixShader"); M.S(nt, mx.inputs[0], fac); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    M.out(nt, mx.outputs[0]); return m

def jet_plume_material():
    """gas: widening cone, density and glow fall off fast along the jet, turbulent ragged edges"""
    m, nt = M.new("AirJetPlume")
    if not nt: return m
    m.cycles.volume_step_rate = 0.08
    co = M.coords(nt); sep = M.N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    gas = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="gas").outputs["Fac"]
    seed = M.N(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="seed").outputs["Fac"]
    z = sep.outputs["Z"]
    r = M.vmath(nt, "LENGTH", M.vmath(nt, "MULTIPLY", co, (1.0, 1.0, 0.0)))
    width = M.math(nt, "ADD", M.math(nt, "MULTIPLY", z, 0.32), 0.02)
    radial = M.math(nt, "POWER", M.maprange(nt, M.math(nt, "DIVIDE", r, width), 0.0, 1.0, 1.0, 0.0), 2.0)
    along = M.math(nt, "POWER", M.maprange(nt, z, 0.0, 1.0, 1.0, 0.0), 3.0)
    n = M.noise(nt, M.vmath(nt, "MULTIPLY", co, (7.0, 7.0, 2.5)), 2.0, 5.0, 0.65, dims="4D", w=M.math(nt, "ADD", M.math(nt, "MULTIPLY", gas, 3.0), seed))
    turb = M.maprange(nt, n.outputs["Fac"], 0.32, 0.72, 0.0, 1.6)
    d = M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", M.math(nt, "MULTIPLY", radial, along), turb), M.math(nt, "MULTIPLY", gas, 14.0))
    v = M.N(nt, "ShaderNodeVolumePrincipled"); M.S(nt, v.inputs["Density"], d)
    v.inputs["Color"].default_value = (0.93, 0.95, 0.98, 1); v.inputs["Anisotropy"].default_value = 0.3
    M.S(nt, v.inputs["Emission Strength"], M.math(nt, "MULTIPLY", d, 1.6)); v.inputs["Emission Color"].default_value = (0.92, 0.96, 1.0, 1)
    M.out(nt, None, v.outputs[0]); return m

def _cone(name, r1, r2, mat, coll, rig, p, d):
    bm = bmesh.new()
    c = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r1, radius2=r2, depth=1.0)
    for v in c["verts"]: v.co.z += 0.5
    ob = CW.mesh_obj(name, bm, [mat], coll, rig)
    ob.location = Vector(p) + Vector(d) * 0.06
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = Vector(d).to_track_quat("Z", "Y")
    ob.visible_shadow = False
    return ob

def build_jets(coll, rig, S, ev):
    core_m, plume_m = jet_core_material(), jet_plume_material(); jets = {}; rnd = random.Random(3)
    for name, (p, d) in T.JETS.items():
        core = _cone("Jet_" + name, 0.006, 0.022, core_m, coll, rig, p, d)
        plume = _cone("JetPlume_" + name, 0.02, 0.38, plume_m, coll, rig, p, d); plume["seed"] = rnd.uniform(0, 50)
        ld = bpy.data.lights.new("JetLight_" + name, "POINT"); ld.color = (0.9, 0.95, 1.0); ld.shadow_soft_size = 0.05
        lo = bpy.data.objects.new("JetLight_" + name, ld); coll.objects.link(lo); lo.parent = rig
        lo.location = Vector(p) + Vector(d) * 0.25
        jets[name] = (core, plume, lo)
    FT = ev["frame_t"]; gas = {k: 0.0 for k in jets}
    for f in range(1, T.FRAMES + 1):
        t = FT[f - 1]; hw = 0.25 / T.FPS * T.speed_at(t, ev)               # half a shutter, in story time
        dt = (FT[f - 1] - FT[f - 2]) if f > 1 else 0.0
        for name, (core, plume, lo) in jets.items():
            pw = max(T.vjet(ev, name, t + hw * u) for u in (-1.0, -0.5, 0.0, 0.5, 1.0))
            gas[name] = max(pw, gas[name] * math.exp(-dt / (0.45 if t > ev["t_stop"] else 0.15)))   # gas lingers after the valve closes (final exhale: longer)
            g = gas[name] if gas[name] > 0.01 else 0.0
            core["pw"] = pw; core.keyframe_insert('["pw"]', frame=f)
            core.scale = (1.0, 1.0, 0.22 * min(pw, 1.0) ** 0.5 if pw > 0.01 else 0.005); core.keyframe_insert("scale", frame=f)
            plume["gas"] = g; plume.keyframe_insert('["gas"]', frame=f)
            L = (1.0 + 0.5 * max(0.0, min(g, 1.3) - 1.0) / 0.3) * (0.35 + 0.65 * min(g, 1.0) ** 0.5) if g > 0 else 0.01
            plume.scale = (1.0, 1.0, L); plume.keyframe_insert("scale", frame=f)            # 1.0-1.5 m
            lo.data.energy = 150.0 * pw; lo.data.keyframe_insert("energy", frame=f)
    for ob in bpy.data.objects:
        if ob.name.startswith(("Jet_", "JetPlume_")) and ob.animation_data and ob.animation_data.action:
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
    """compact clouds at the wheels, gone in ~1.5-2 s of story time"""
    mat = dust_material(); rnd = random.Random(7); puffs = []; FT = ev["frame_t"]
    def sample(t): return S[min(len(S) - 1, int(round(t / T.DT)))]
    spawns = []
    tr = ev.get("t_retro", ev["t_land"] - 0.5)
    for k in range(3):
        t = tr + 0.25 + 0.1 * k; s = sample(t)
        if s["cg"][2] < 4.0:
            c = s["cg"]; spawns.append((t, (c[0] + rnd.uniform(-0.5, 0.5), c[1] + rnd.uniform(-0.6, 0.6), 0.2), 0.3, 1.5, 0.9, (0, 0, 0.3)))
    s = sample(ev["t_land"])
    for side in (-1, 1):
        for ay in (T.AXLE_F, T.AXLE_R):
            p = Vector(s["pos"]) + Vector(s["X"]) * side * 0.9 + Vector(s["Y"]) * ay
            spawns.append((ev["t_land"] + rnd.uniform(0, 0.03), (p.x, p.y, 0.15), 0.25, 1.3, 1.4, (side * 1.0, -1.5, 0.3)))
    for i, (t, hub, sp) in enumerate(ev["trail"]):
        if i % 2: continue
        spawns.append((t, (hub[0], hub[1], 0.15), 0.2, 0.55 + 0.04 * sp, 0.45 + 0.03 * sp, (0, 0, 0.2)))
    for n, (t0, pos, r0, r1, dmax, vel) in enumerate(spawns):
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        ob = CW.mesh_obj(f"Dust{n:02d}", bm, [mat], coll, None, smooth=False)
        ob.visible_shadow = False; ob["seed"] = rnd.uniform(0, 100)
        f0 = T.first_frame_at(ev, t0)
        for f in range(max(1, f0 - 1), T.FRAMES + 1):
            tau = FT[f - 1] - t0
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
