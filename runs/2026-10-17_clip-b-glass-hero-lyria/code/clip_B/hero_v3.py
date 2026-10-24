"""clip_B hero v3: the sleeping-statue MPFB (CC0) figure (v3/hero_v3_face.blend) in frosted glass for the clip.
Glass 0.30-0.40 rough + fine noise, thin film 500 nm, a little dispersion (R/G/B glass lobes; Blender 4.5 has no Dispersion input), IOR 1.45,
light and slightly cold. Inside: a neutral absorbing volume (no back wall through the face). Amber #FF8A3D only inside: the chest core is the
brightest point (hot centre + soft halo), thin filaments run deep inside (arms, torso, neck, the back of the head - never under the face),
dimmer than the core, a slow pulse running along them. Fingertips / feet dissolve into particles; dissolve / assemble as in hero.py.
Same hero dict + show / set_state contract as hero.py (dissolve 0 whole .. 1.1 gone, glow = the voice-driven strength)."""
import bpy, bmesh, math, json
import numpy as np
from mathutils import Vector, Matrix, Quaternion
import hero as H
V3 = "/content/drive/MyDrive/renders/clip_B/v3"
GLOW = (1.0, 0.254, 0.047)                        # #FF8A3D in scene-linear
GLOW_NOM = 1.0
CORE_E, CORE_HOT, FIL_E, LIGHT_W = 26.0, 9.0, 3.2, 45.0
RIM_COL = (0.70, 0.83, 1.0)                       # cold white-blue back light on every hero shot
CORE_C = Vector((0.0, -0.040, 1.330))            # rest pose, armature space: the chest core, ~5 cm under the sternum
HEAD_C = Vector((0.0, -0.035, 1.610))            # rest pose: head centre
MOCAP = json.load(open(f"{V3}/mocap.json"))       # CMU micro-motion: zero-mean yaw / pitch / roll (deg) per part at 24 fps
MO_LIM = {"torso": 4.0, "neck": 6.0, "head": 8.0}  # a calm figure: small, clamped
def mocap_rot(clip, frame, k=0.5):
    """{part: 3x3} in hero armature space (yaw about Z, pitch about X, roll about Y) for a clip frame, scaled and clamped"""
    m = MOCAP[clip]; i = int(frame) % int(m["frames"]); out = {}
    for part in ("torso", "neck", "head"):
        y, p, r = (math.radians(max(-MO_LIM[part], min(MO_LIM[part], a * k))) for a in m[part][i])
        out[part] = Matrix.Rotation(y, 3, "Z") @ Matrix.Rotation(p, 3, "X") @ Matrix.Rotation(r, 3, "Y")
    return out
def _frac(M, w): return Quaternion().slerp(M.to_quaternion(), w).to_matrix()
def _torso_mo(rot, mo):
    if mo: rot["spine02"] = _frac(mo["torso"], 0.5) @ rot["spine02"]; rot["spine01"] = mo["torso"] @ rot["spine01"]

def _append(coll, name):
    with bpy.data.libraries.load(f"{V3}/hero_v3_face.blend", link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("HeroV3", "HeroV3.rig")]
    rig = next(o for o in dst.objects if o.type == "ARMATURE"); shell = next(o for o in dst.objects if o.type == "MESH")
    for o in (rig, shell): coll.objects.link(o)
    rig.name, shell.name = name + "_Rig", name + "_Shell"; shell.data.name = name + "_ShellMesh"
    for m in list(shell.modifiers):
        if m.type == "ARMATURE": m.object = rig; m.use_deform_preserve_volume = True
        else: shell.modifiers.remove(m)
    sub = shell.modifiers.new("subdivision", "SUBSURF"); sub.levels = 0; sub.render_levels = 2
    return rig, shell

def _tip_attr(shell, rig):
    """1 at the fingertips (last ~16 mm) and over the front of the feet, 0 elsewhere (rest pose)"""
    me = shell.data; P = np.array([v.co for v in me.vertices]); B = rig.data.bones
    tips = np.array([B[b].tail_local for b in B.keys() if b.startswith("finger") and b.endswith(("-3.L", "-3.R"))])
    d = np.min(np.linalg.norm(P[:, None, :] - tips[None, :, :], axis=2), axis=1)
    ft = np.clip(1 - d / 0.016, 0, 1); ft = ft * ft * (3 - 2 * ft); fo = np.zeros(len(P))
    for s in ("L", "R"):
        ank = np.array(B["foot." + s].head_local); toe = np.array(B["foot." + s].tail_local); ax = (toe - ank) / np.linalg.norm(toe - ank)
        along = (P - ank) @ ax; near = (np.linalg.norm(P - ank, axis=1) < 0.25) & (P[:, 2] < 0.13)
        fo = np.maximum(fo, np.where(near, np.clip((along - 0.02) / 0.10, 0, 1), 0))
    tip = np.maximum(ft, 0.85 * fo)
    a = me.attributes.get("tip") or me.attributes.new("tip", "FLOAT", "POINT"); a.data.foreach_set("value", tip.astype(np.float32))
    return float((tip > 0.3).mean())

def _breath_key(shell):
    """'breath' shape key: the rib cage grows ~1.3 % (radially round the spine axis), falling off to the belly and the shoulders"""
    me = shell.data
    if not me.shape_keys: shell.shape_key_add(name="Basis", from_mix=False)
    k = shell.shape_key_add(name="breath", from_mix=False)
    P = np.array([v.co for v in me.vertices]); z = P[:, 2]
    wz = np.clip(1 - np.abs(z - 1.27) / 0.16, 0, 1); wz = wz * wz * (3 - 2 * wz)
    rad = np.hypot(P[:, 0], P[:, 1]); wr = np.clip(1 - (rad - 0.10) / 0.10, 0, 1) * (rad < 0.22)
    off = np.zeros_like(P); off[:, 0] = P[:, 0] * 0.013 * wz * wr; off[:, 1] = P[:, 1] * 0.013 * wz * wr; off[:, 2] = (z - 1.15) * 0.004 * wz * wr
    k.data.foreach_set("co", (P + off).astype(np.float32).ravel()); k.value = 0.0
    return k

def _N(nt, t, **kw):
    x = nt.nodes.new(t)
    for kk, v in kw.items(): setattr(x, kk, v)
    return x
def _m(nt, op, a, b=0.0, clamp=False):
    x = _N(nt, "ShaderNodeMath", operation=op, use_clamp=clamp)
    for i, v in enumerate((a, b)):
        if hasattr(v, "is_output"): nt.links.new(v, x.inputs[i])
        else: x.inputs[i].default_value = v
    return x.outputs[0]
def _val(nt, name, v):
    x = _N(nt, "ShaderNodeValue", name=name); x.outputs[0].default_value = v; return x.outputs[0]
def _tc(nt, ob):
    t = _N(nt, "ShaderNodeTexCoord"); t.object = ob; return t.outputs["Object"]
def _range(nt, v, a, b, c, d, smooth=True):
    x = _N(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP" if smooth else "LINEAR")
    x.inputs["From Min"].default_value, x.inputs["From Max"].default_value, x.inputs["To Min"].default_value, x.inputs["To Max"].default_value = a, b, c, d
    nt.links.new(v, x.inputs["Value"]); return x.outputs["Result"]
def _dist(nt, ob):
    x = _N(nt, "ShaderNodeVectorMath", operation="LENGTH"); nt.links.new(_tc(nt, ob), x.inputs[0]); return x.outputs["Value"]

def _materials(name, rig, core_ref, head_ref):
    # ---- glass shell + inner volume ----
    g = bpy.data.materials.new(name + "_GlassV3"); g.use_nodes = True; nt = g.node_tree; nt.nodes.clear(); g.cycles.volume_step_rate = 0.5
    o = _N(nt, "ShaderNodeOutputMaterial"); p = _N(nt, "ShaderNodeBsdfPrincipled", name="Principled BSDF")
    for k, v in (("Base Color", (0.93, 0.95, 0.97, 1)), ("IOR", 1.45), ("Transmission Weight", 1.0), ("Coat Weight", 0.25), ("Coat Roughness", 0.05),
                 ("Specular IOR Level", 0.5), ("Thin Film Thickness", 500.0), ("Thin Film IOR", 1.38)):
        p.inputs[k].default_value = v
    gls = []
    for col, ior in (((0.93, 0, 0, 1), 1.440), ((0, 0.95, 0, 1), 1.450), ((0, 0, 0.97, 1), 1.462)):
        gb = _N(nt, "ShaderNodeBsdfGlass"); gb.inputs["IOR"].default_value = ior; gb.inputs["Color"].default_value = col; gls.append(gb)
    a1 = _N(nt, "ShaderNodeAddShader"); a2 = _N(nt, "ShaderNodeAddShader")
    nt.links.new(gls[0].outputs[0], a1.inputs[0]); nt.links.new(gls[1].outputs[0], a1.inputs[1]); nt.links.new(a1.outputs[0], a2.inputs[0]); nt.links.new(gls[2].outputs[0], a2.inputs[1])
    gm = _N(nt, "ShaderNodeMixShader"); gm.inputs[0].default_value = 0.35; nt.links.new(p.outputs[0], gm.inputs[1]); nt.links.new(a2.outputs[0], gm.inputs[2])
    co = _tc(nt, rig)
    nz = _N(nt, "ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 38.0; nz.inputs["Detail"].default_value = 3.0; nt.links.new(co, nz.inputs["Vector"])
    rough = _range(nt, nz.outputs["Fac"], 0.3, 0.7, 0.30, 0.40, smooth=False); nt.links.new(rough, p.inputs["Roughness"])
    for gb in gls: nt.links.new(rough, gb.inputs["Roughness"])
    d_v, gl_v, t_v = _val(nt, "dissolve_v", 0.0), _val(nt, "glow_v", GLOW_NOM), _val(nt, "t_v", 0.0)
    vis = H._mask(nt, co, d_v)
    tip = _N(nt, "ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="tip").outputs["Fac"]
    tn = _N(nt, "ShaderNodeTexNoise", noise_dimensions="4D"); tn.inputs["Scale"].default_value = 26.0; nt.links.new(co, tn.inputs["Vector"]); nt.links.new(_m(nt, "MULTIPLY", t_v, 0.3), tn.inputs["W"])
    tipn = _m(nt, "ADD", tip, _m(nt, "MULTIPLY", _m(nt, "SUBTRACT", tn.outputs["Fac"], 0.5), 0.5))
    vis2 = _m(nt, "MULTIPLY", vis, _m(nt, "SUBTRACT", 1.0, _range(nt, tipn, 0.45, 0.95, 0.0, 1.0)))
    tr = _N(nt, "ShaderNodeBsdfTransparent"); mx = _N(nt, "ShaderNodeMixShader")
    nt.links.new(vis2, mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(gm.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], o.inputs["Surface"])
    H._aov(nt, _m(nt, "MULTIPLY", vis2, gl_v), GLOW, 0.06)
    # inner volume: neutral, slightly cold, absorbing (denser in the head: no back wall through the face); emission only in the chest core halo
    pv = _N(nt, "ShaderNodeVolumePrincipled"); pv.inputs["Color"].default_value = (0.30, 0.33, 0.37, 1); pv.inputs["Anisotropy"].default_value = 0.3
    pv.inputs["Emission Color"].default_value = (*GLOW, 1)
    vn = _N(nt, "ShaderNodeTexNoise"); vn.inputs["Scale"].default_value = 18.0; vn.inputs["Detail"].default_value = 2.0; nt.links.new(co, vn.inputs["Vector"])
    headw = _range(nt, _dist(nt, head_ref), 0.07, 0.13, 1.0, 0.0)
    dens = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", _m(nt, "ADD", 4.0, _m(nt, "MULTIPLY", headw, 8.0)), _range(nt, vn.outputs["Fac"], 0.3, 0.7, 0.8, 1.2, smooth=False)), vis)
    nt.links.new(dens, pv.inputs["Density"])
    halo = _m(nt, "POWER", _range(nt, _dist(nt, core_ref), 0.0, 0.10, 1.0, 0.0), 2.0)
    nt.links.new(_m(nt, "MULTIPLY", _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", halo, CORE_E), gl_v), vis), pv.inputs["Emission Strength"])
    nt.links.new(pv.outputs[0], o.inputs["Volume"])
    # ---- the hot centre of the core (a small emitter) ----
    c = bpy.data.materials.new(name + "_CoreHotV3"); c.use_nodes = True; nt = c.node_tree; nt.nodes.clear()
    o = _N(nt, "ShaderNodeOutputMaterial"); em = _N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (*GLOW, 1)
    cd_v, cg_v = _val(nt, "dissolve_v", 0.0), _val(nt, "glow_v", GLOW_NOM)
    cvis = _m(nt, "SUBTRACT", 1.0, _range(nt, cd_v, 0.25, 0.75, 0.0, 1.0))
    s = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", cg_v, CORE_HOT), cvis); nt.links.new(s, em.inputs["Strength"])
    tr = _N(nt, "ShaderNodeBsdfTransparent"); mx = _N(nt, "ShaderNodeMixShader"); nt.links.new(cvis, mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], o.inputs["Surface"]); H._aov(nt, _m(nt, "MULTIPLY", s, 0.08), GLOW, 1.0)
    # ---- filaments: dim, fading from the core outward, a slow band of light running along them ----
    fm = bpy.data.materials.new(name + "_FilamentV3"); fm.use_nodes = True; nt = fm.node_tree; nt.nodes.clear()
    o = _N(nt, "ShaderNodeOutputMaterial"); em = _N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (*GLOW, 1)
    fd_v, fg_v, ft_v = _val(nt, "dissolve_v", 0.0), _val(nt, "glow_v", GLOW_NOM), _val(nt, "t_v", 0.0)
    u = _N(nt, "ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="u").outputs["Fac"]
    ph = _N(nt, "ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="ph").outputs["Fac"]
    fade = _m(nt, "SUBTRACT", 1.0, _m(nt, "MULTIPLY", u, 0.6))
    v_ = _m(nt, "FRACT", _m(nt, "SUBTRACT", _m(nt, "SUBTRACT", u, _m(nt, "MULTIPLY", ft_v, 0.12)), ph))      # the band runs outward ~0.12 of a fibre per second
    dd = _m(nt, "DIVIDE", _m(nt, "SUBTRACT", v_, 0.5), 0.08); band = _m(nt, "EXPONENT", _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", dd, dd), -1.0))
    fvis = H._mask(nt, _tc(nt, rig), fd_v)
    s = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", fade, _m(nt, "ADD", 0.4, _m(nt, "MULTIPLY", band, 0.6))), _m(nt, "MULTIPLY", fg_v, FIL_E)), fvis)
    nt.links.new(s, em.inputs["Strength"])
    tr = _N(nt, "ShaderNodeBsdfTransparent"); mx = _N(nt, "ShaderNodeMixShader"); nt.links.new(fvis, mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], o.inputs["Surface"]); H._aov(nt, _m(nt, "MULTIPLY", s, 0.04), GLOW, 1.0)
    # ---- particles (dissolve + fingertips / feet): the inner light's colour ----
    pm = bpy.data.materials.new(name + "_ParticleV3"); pm.use_nodes = True; nt = pm.node_tree; nt.nodes.clear()
    o = _N(nt, "ShaderNodeOutputMaterial"); em = _N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (*GLOW, 1)
    br = _N(nt, "ShaderNodeAttribute", attribute_type="INSTANCER", attribute_name="bright").outputs["Fac"]; nt.links.new(br, em.inputs["Strength"])
    nt.links.new(em.outputs[0], o.inputs["Surface"]); H._aov(nt, br, GLOW, 1.0)
    return g, c, fm, pm

def _catmull(P, step=0.004):
    P = [Vector(p) for p in P]; P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]; out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]; n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            t = k / n; t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2]); return out

def _filament_mesh(name, rig):
    """thin tubes deep inside (rest pose): core -> both arms to the wrists, core -> the torso (belly, flanks, back), core -> up the neck
    (a loose bundle) -> the head centre -> branches to the back and the crown of the head (>= 10 cm behind the face)"""
    B = rig.data.bones; bh = lambda n: Vector(B[n].head_local); bt = lambda n: Vector(B[n].tail_local)
    paths = []                                                                                    # (points, u0, u1, strands, spread)
    for s in ("L", "R"):
        sx = 1.0 if s == "L" else -1.0; w = bt("wrist." + s); wd = (w - bh("wrist." + s)).normalized()
        P = [CORE_C, Vector((0.03 * sx, -0.02, 1.36)), bh("clavicle." + s) + Vector((0, 0.0, -0.01)), bt("clavicle." + s) + Vector((0, 0, -0.015)),
             bt("shoulder01." + s) + Vector((0, 0, -0.02)), bt("upperarm01." + s), bt("upperarm02." + s), bt("lowerarm01." + s), bt("lowerarm02." + s), w + wd * 0.015,
             bh("finger3-1." + s) - (bh("finger3-1." + s) - w) * 0.35, bh("finger3-1." + s)]             # on through the palm to the knuckles: the hands glow softly
        paths.append((P, 0.0, 1.0, 4, 0.005))
    for tgt in (Vector((0.0, -0.02, 1.06)), Vector((0.09, -0.005, 1.20)), Vector((-0.09, -0.005, 1.20)), Vector((0.0, 0.055, 1.24))):
        paths.append(([CORE_C, CORE_C.lerp(tgt, 0.5) + Vector((0, 0.01, 0)), tgt], 0.0, 0.85, 2, 0.006))
    hc = Vector((0.0, -0.01, 1.605))
    paths.append(([CORE_C, Vector((0, -0.01, 1.40)), bh("neck01") + Vector((0, 0.008, 0)), bh("neck02") + Vector((0, 0.008, 0)), bh("neck03") + Vector((0, 0.006, 0)), hc],
                  0.0, 0.70, 6, 0.006))
    for tgt in (Vector((0, 0.035, 1.665)), Vector((0.032, 0.028, 1.635)), Vector((-0.032, 0.028, 1.635)), Vector((0, 0.008, 1.690)),
                Vector((0.022, 0.050, 1.590)), Vector((-0.022, 0.050, 1.590)), Vector((0.040, 0.010, 1.600)), Vector((-0.040, 0.010, 1.600))):
        paths.append(([hc, hc.lerp(tgt, 0.5) + Vector((0, 0, 0.006)), tgt], 0.70, 1.0, 1, 0.0))
    verts, faces, U, PH = [], [], [], []; rng = np.random.default_rng(4); RING = 5
    for P, u0, u1, ns, spread in paths:
        C = _catmull(P); L = [0.0]
        for i in range(1, len(C)): L.append(L[-1] + (C[i] - C[i - 1]).length)
        for sidx in range(ns):
            phase = float(rng.uniform(0, 1)); th0 = sidx * 2 * math.pi / max(1, ns); nrm = None; base = len(verts)
            for i, c in enumerate(C):
                tg = (C[min(i + 1, len(C) - 1)] - C[max(i - 1, 0)]).normalized()
                if nrm is None: nrm = tg.orthogonal().normalized()
                nrm = (nrm - tg * nrm.dot(tg)).normalized(); bnm = tg.cross(nrm)
                uu = u0 + (u1 - u0) * L[i] / max(L[-1], 1e-6); th = th0 + 22.0 * L[i]
                ctr = c + (nrm * math.cos(th) + bnm * math.sin(th)) * spread * min(1.0, L[i] / 0.03)
                r = 0.0011 * (1 - uu) + 0.0004 * uu
                for k in range(RING):
                    a = 2 * math.pi * k / RING; verts.append(ctr + (nrm * math.cos(a) + bnm * math.sin(a)) * r); U.append(uu); PH.append(phase)
                if i:
                    for k in range(RING):
                        a0, a1 = base + (i - 1) * RING + k, base + (i - 1) * RING + (k + 1) % RING
                        faces.append((a0, a1, a1 + RING, a0 + RING))
    me = bpy.data.meshes.new(name + "_FilamentMesh"); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    for nm, vals in (("u", U), ("ph", PH)):
        a = me.attributes.new(nm, "FLOAT", "POINT"); a.data.foreach_set("value", np.array(vals, np.float32))
    for p in me.polygons: p.use_smooth = True
    return me

def _tip_particles(src, part_mat):
    """a soft, continuous trickle of amber particles leaving the fingertips and the front of the feet"""
    ng = bpy.data.node_groups.new(src.name + "_TipGN", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"); ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    def put(s, v):
        if hasattr(v, "is_output"): L.new(v, s)
        else: s.default_value = v
    def m(op, a, b=0.0):
        x = N.new("ShaderNodeMath"); x.operation = op; put(x.inputs[0], a); put(x.inputs[1], b); return x.outputs[0]
    def vm(op, a, b=None, scale=None):
        x = N.new("ShaderNodeVectorMath"); x.operation = op; put(x.inputs[0], a)
        if b is not None: put(x.inputs[1], b)
        if scale is not None: put(x.inputs["Scale"], scale)
        return x.outputs["Vector"]
    go = N.new("NodeGroupOutput"); oi = N.new("GeometryNodeObjectInfo"); oi.inputs["Object"].default_value = src; oi.transform_space = "RELATIVE"
    tip = N.new("GeometryNodeInputNamedAttribute"); tip.data_type = "FLOAT"; tip.inputs["Name"].default_value = "tip"
    sel = N.new("FunctionNodeCompare"); sel.data_type = "FLOAT"; sel.operation = "GREATER_THAN"; L.new(tip.outputs["Attribute"], sel.inputs["A"]); sel.inputs["B"].default_value = 0.35
    dist = N.new("GeometryNodeDistributePointsOnFaces"); dist.distribute_method = "RANDOM"; dist.inputs["Density"].default_value = 14000.0
    L.new(oi.outputs["Geometry"], dist.inputs["Mesh"]); L.new(sel.outputs["Result"], dist.inputs["Selection"])
    tv = N.new("ShaderNodeValue"); tv.name = "t"; dval = N.new("ShaderNodeValue"); dval.name = "dissolve"
    rnd = N.new("FunctionNodeRandomValue"); rnd.data_type = "FLOAT"
    phase = m("FRACT", m("ADD", m("MULTIPLY", tv.outputs[0], 0.32), rnd.outputs[1]))
    pos = N.new("GeometryNodeInputPosition").outputs[0]
    sw = N.new("ShaderNodeTexNoise"); sw.noise_dimensions = "4D"; sw.inputs["Scale"].default_value = 9.0; L.new(pos, sw.inputs["Vector"]); L.new(tv.outputs[0], sw.inputs["W"])
    drift = vm("ADD", vm("SCALE", dist.outputs["Normal"], scale=0.010), vm("ADD", (0.0, 0.0, 0.022), vm("SCALE", vm("SUBTRACT", sw.outputs["Color"], (0.5, 0.5, 0.5)), scale=0.03)))
    sp = N.new("GeometryNodeSetPosition"); L.new(dist.outputs["Points"], sp.inputs["Geometry"]); L.new(vm("SCALE", drift, scale=phase), sp.inputs["Offset"])
    ico = N.new("GeometryNodeMeshIcoSphere"); ico.inputs["Radius"].default_value = 1.0; ico.inputs["Subdivisions"].default_value = 1
    inst = N.new("GeometryNodeInstanceOnPoints"); L.new(sp.outputs[0], inst.inputs["Points"]); L.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    rs = N.new("FunctionNodeRandomValue"); rs.data_type = "FLOAT"; rs.inputs[2].default_value = 0.0018; rs.inputs[3].default_value = 0.0038
    alive = m("SUBTRACT", 1.0, m("MINIMUM", m("MULTIPLY", dval.outputs[0], 3.0), 1.0))          # gone once the whole body dissolves
    L.new(m("MULTIPLY", m("MULTIPLY", rs.outputs[1], m("SUBTRACT", 1.0, m("MULTIPLY", phase, 0.7))), alive), inst.inputs["Scale"])
    br = N.new("GeometryNodeStoreNamedAttribute"); br.data_type = "FLOAT"; br.domain = "INSTANCE"; br.inputs["Name"].default_value = "bright"
    L.new(inst.outputs[0], br.inputs["Geometry"]); L.new(m("MULTIPLY", m("ADD", m("MULTIPLY", m("SUBTRACT", 1.0, phase), 1.2), 0.25), alive), br.inputs["Value"])
    smat = N.new("GeometryNodeSetMaterial"); smat.inputs["Material"].default_value = part_mat; L.new(br.outputs[0], smat.inputs["Geometry"]); L.new(smat.outputs[0], go.inputs[0])
    return ng

def _transfer_weights(dst, src):
    dt = dst.modifiers.new("dt", "DATA_TRANSFER"); dt.object = src; dt.use_vert_data = True; dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"; dt.layers_vgroup_select_src = "ALL"; dt.layers_vgroup_select_dst = "NAME"
    with bpy.context.temp_override(object=dst, active_object=dst, selected_objects=[dst]):
        bpy.ops.object.datalayout_transfer(modifier="dt"); bpy.ops.object.modifier_apply(modifier="dt")

def _bone_empty(coll, name, rig, bone, point):
    e = bpy.data.objects.new(name, None); coll.objects.link(e); e.parent = rig; e.parent_type = "BONE"; e.parent_bone = bone
    bpy.context.view_layer.update(); e.matrix_world = rig.matrix_world @ Matrix.Translation(point); return e

def build_hero(coll, name="HeroV3", scale=1.0):
    rig, shell = _append(coll, name); rig.scale = (scale,) * 3
    tipf = _tip_attr(shell, rig); _breath_key(shell)
    core_ref = _bone_empty(coll, name + "_CoreRef", rig, "spine02", CORE_C); head_ref = _bone_empty(coll, name + "_HeadRef", rig, "head", HEAD_C)
    glass, hot_m, fil_m, part_m = _materials(name, rig, core_ref, head_ref)
    shell.data.materials.clear(); shell.data.materials.append(glass)
    hm = bpy.data.meshes.new(name + "_CoreHotMesh"); bmc = bmesh.new(); bmesh.ops.create_icosphere(bmc, subdivisions=3, radius=0.014); bmc.to_mesh(hm); bmc.free()
    hot = bpy.data.objects.new(name + "_CoreHot", hm); coll.objects.link(hot); hot.parent = core_ref; hot.data.materials.append(hot_m)
    for p in hm.polygons: p.use_smooth = True
    fme = _filament_mesh(name, rig); fil = bpy.data.objects.new(name + "_Filaments", fme); coll.objects.link(fil); fil.parent = rig; fme.materials.append(fil_m)
    _transfer_weights(fil, shell)
    am = fil.modifiers.new("Armature", "ARMATURE"); am.object = rig
    for ob in (shell, hot, fil): ob.visible_shadow = False
    ld = bpy.data.lights.new(name + "_Light", "POINT"); ld.color = GLOW; ld.energy = LIGHT_W; ld.shadow_soft_size = 0.25
    lo = bpy.data.objects.new(name + "_Light", ld); coll.objects.link(lo); lo.parent = core_ref; lo.location = (0, -0.02, 0); lo["base"] = LIGHT_W
    pme = bpy.data.meshes.new(name + "_PartsMesh"); parts = bpy.data.objects.new(name + "_Particles", pme); coll.objects.link(parts); parts.parent = rig
    mod = parts.modifiers.new("particles", "NODES"); mod.node_group = H._particle_tree(shell, part_m); parts.visible_shadow = False
    tme = bpy.data.meshes.new(name + "_TipMesh"); tips = bpy.data.objects.new(name + "_TipParticles", tme); coll.objects.link(tips); tips.parent = rig
    tmod = tips.modifiers.new("tips", "NODES"); tmod.node_group = _tip_particles(shell, part_m); tips.visible_shadow = False
    H._exclude_from_light(lo, (shell, hot, fil, parts, tips), name + "_LightExcl")
    hero = dict(root=rig, shell=shell, core=hot, fil=fil, parts=parts, tips=tips, lights=[lo], ng=mod.node_group, tng=tmod.node_group, scale=scale, v3=True,
                mats=(glass, hot_m, fil_m), breath=shell.data.shape_keys.key_blocks["breath"], core_ref=core_ref, head_ref=head_ref)
    set_state(hero, dissolve=0.0, glow=GLOW_NOM)
    print(f"hero v3 {name}: shell {len(shell.data.polygons)} faces, filaments {len(fme.polygons)} faces, tip area {tipf:.3f}", flush=True)
    return hero

def set_state(hero, dissolve, glow, t=None, breath=None):
    """dissolve: 0 whole .. 1.1 gone; glow: voice-driven strength of the core + filaments (light follows); t: seconds (filament pulse, tip trickle)"""
    for mat in hero["mats"]:
        nd = mat.node_tree.nodes
        nd["dissolve_v"].outputs[0].default_value = dissolve; nd["glow_v"].outputs[0].default_value = glow
        if t is not None and "t_v" in nd: nd["t_v"].outputs[0].default_value = t
    hero["ng"].nodes["dissolve"].outputs[0].default_value = dissolve; hero["tng"].nodes["dissolve"].outputs[0].default_value = dissolve
    if t is not None: hero["tng"].nodes["t"].outputs[0].default_value = t
    if breath is not None: hero["breath"].value = breath
    vis = max(0.0, min(1.0, 1.0 - dissolve))
    for lo in hero["lights"]: lo.data.energy = lo["base"] * glow / GLOW_NOM * vis

def lowest_z(hero):
    dg = bpy.context.evaluated_depsgraph_get(); ev = hero["shell"].evaluated_get(dg); me = ev.to_mesh()
    z = min(v.co.z for v in me.vertices); ev.to_mesh_clear(); return z

# ---------------- posing: analytic forward kinematics (bone matrices in armature space) ----------------
def _rest(rig):
    return {b.name: b.matrix_local.copy() for b in rig.data.bones}
def apply_pose(rig, rot, root_loc=None):
    """rot: {bone: 3x3 armature-space orientation (absolute)}; other bones follow their parent rigidly. Sets matrix_basis directly."""
    R = _rest(rig); posed = {}
    def walk(b):
        rest = R[b.name]
        if b.parent is None:
            M = rest.copy()
            if root_loc is not None: M.translation = rest.translation + Vector(root_loc)
        else:
            M = posed[b.parent.name] @ R[b.parent.name].inverted() @ rest
        if b.name in rot:
            T = M.translation.copy(); M = rot[b.name].to_4x4(); M.translation = T
        posed[b.name] = M
        pb = rig.pose.bones[b.name]; pb.rotation_mode = "QUATERNION"
        if b.parent is None: pb.matrix_basis = rest.inverted() @ M
        else: pb.matrix_basis = (posed[b.parent.name] @ R[b.parent.name].inverted() @ rest).inverted() @ M
        for c in b.children: walk(c)
    for b in rig.data.bones:
        if b.parent is None: walk(b)
    return posed
def _dir_rot(rig, name, d, base=None):
    """orientation: the bone's rest orientation (or base) turned so that its Y axis points along d (minimal twist)"""
    r = (base if base is not None else rig.data.bones[name].matrix_local.to_3x3())
    q = r.col[1].normalized().rotation_difference(Vector(d).normalized()); return q.to_matrix() @ r
def _ik2(a, b_len, c_len, target, pole):
    d = target - a; L = min(d.length, b_len + c_len - 1e-4); dn = d.normalized()
    x = (b_len * b_len - c_len * c_len + L * L) / (2 * L); h = math.sqrt(max(0.0, b_len * b_len - x * x))
    pn = (pole - pole.dot(dn) * dn).normalized(); return a + dn * x + pn * h
def _tail(rig, posed, n): return posed[n] @ Vector((0, rig.data.bones[n].length, 0))
def look_rot(rig, posed, target_arm, weight=1.0):
    """armature-space rotation turning the face (rest -Y) toward target_arm, partial by weight"""
    hb = posed["head"]; hc = hb @ Vector((0, 0.06, 0.0))
    fwd = (hb.to_3x3() @ rig.data.bones["head"].matrix_local.to_3x3().inverted() @ Vector((0, -1, 0))).normalized()
    want = (Vector(target_arm) - hc).normalized(); q = fwd.rotation_difference(want)
    return Quaternion().slerp(q, weight)
def _finger_rots(rig, posed, k):
    out = {}
    for b in rig.data.bones:
        if b.name.startswith("finger") and b.parent is not None and "-" in b.name:
            seg = int(b.name.split("-")[1][0]); ang = math.radians((10, 18, 14)[min(seg, 3) - 1] * k / 0.28) * (0.6 if b.name.startswith("finger1") else 1.0)
            out[b.name] = posed[b.name].to_3x3() @ Matrix.Rotation(ang, 3, "X")
    return out
def _look(rig, rot, root_loc, look_arm, limit=55.0, mo=None):
    posed = apply_pose(rig, rot, root_loc); q = look_rot(rig, posed, look_arm)
    ang = math.degrees(q.angle)
    if ang > limit: q = Quaternion().slerp(q, limit / ang)                      # a calm turn, never past ~55 deg
    rot2 = dict(rot)                                                            # cumulative share of the turn down the chain (absolute orientations)
    for n, w in (("spine02", 0.06), ("spine01", 0.16), ("neck01", 0.28), ("neck02", 0.46), ("neck03", 0.68), ("head", 1.0)):
        rot2[n] = Quaternion().slerp(q, w).to_matrix() @ posed[n].to_3x3()
    if mo:                                                                      # micro-motion of the neck and head on top of the look
        for n, M in (("neck01", _frac(mo["neck"], 0.33)), ("neck02", _frac(mo["neck"], 0.66)), ("neck03", mo["neck"]), ("head", mo["head"] @ mo["neck"])):
            rot2[n] = M @ rot2[n]
    return rot2, apply_pose(rig, rot2, root_loc)

def pose_standing(rig, look_arm, weight_leg="L", mo=None):
    """relaxed standing, weight on one leg (contrapposto), arms hanging, fingers soft, the head (and a little of the chest) toward look_arm"""
    bones = rig.data.bones; rot = {}; sg = 1.0 if weight_leg == "L" else -1.0
    rot["root"] = Matrix.Rotation(math.radians(3.0) * sg, 3, "Y") @ bones["root"].matrix_local.to_3x3()     # the free side's hip drops
    for s in ("L", "R"):
        sx = 1.0 if s == "L" else -1.0; wl = (s == weight_leg)
        rot["upperleg01." + s] = _dir_rot(rig, "upperleg01." + s, (0.02 * sx, -0.01, -1.0))
        rot["upperleg02." + s] = _dir_rot(rig, "upperleg02." + s, (0.035 * sx if wl else 0.0, -0.01 if wl else -0.09, -1.0))
        rot["lowerleg01." + s] = _dir_rot(rig, "lowerleg01." + s, (0.01 * sx, 0.015 if wl else 0.11, -1.0)); rot["lowerleg02." + s] = _dir_rot(rig, "lowerleg02." + s, (0.01 * sx, 0.015 if wl else 0.11, -1.0))
        rot["foot." + s] = _dir_rot(rig, "foot." + s, (0.12 * sx if wl else 0.2 * sx, -1.0, -0.42))
        rot["upperarm01." + s] = _dir_rot(rig, "upperarm01." + s, (0.16 * sx, 0.02, -1.0)); rot["upperarm02." + s] = _dir_rot(rig, "upperarm02." + s, (0.16 * sx, 0.02, -1.0))
        rot["lowerarm01." + s] = _dir_rot(rig, "lowerarm01." + s, (0.07 * sx, -0.20, -1.0)); rot["lowerarm02." + s] = _dir_rot(rig, "lowerarm02." + s, (0.07 * sx, -0.20, -1.0))
        rot["wrist." + s] = _dir_rot(rig, "wrist." + s, (0.02 * sx, -0.12, -1.0))
    for n in ("spine02", "spine01"): rot[n] = Matrix.Rotation(math.radians(-1.6) * sg, 3, "Y") @ bones[n].matrix_local.to_3x3()
    _torso_mo(rot, mo)
    rl = (0.018 * sg, 0, -0.006); posed = apply_pose(rig, rot, rl); rot.update(_finger_rots(rig, posed, 0.28))
    rot, posed = _look(rig, rot, rl, look_arm, mo=mo); return posed

def pose_seated_from(rig, old, look_arm, mo=None):
    """retarget the old seated hero (hero.py rig in the same parent space, both facing -Y): pelvis / spine / neck turn as the old ones did
    (delta from rest), legs and feet take its directions, hands rest on the knees (two-bone IK), the head turns toward look_arm"""
    O = old.pose.bones; OB = old.data.bones
    d_old = lambda n: (O[n].tail - O[n].head).normalized(); r_old = lambda n: (OB[n].tail_local - OB[n].head_local).normalized()
    delta = lambda n: r_old(n).rotation_difference(d_old(n)).to_matrix()
    B = rig.data.bones; rot = {}
    for n3, no in (("root", "hips"), ("spine05", "spine"), ("spine04", "spine"), ("spine03", "chest"), ("spine02", "chest"), ("spine01", "chest"),
                   ("neck01", "neck"), ("neck02", "neck"), ("neck03", "neck"), ("head", "head")):
        rot[n3] = delta(no) @ B[n3].matrix_local.to_3x3()
    for s in ("L", "R"):
        for n3, no in (("upperleg01.", "thigh."), ("upperleg02.", "thigh."), ("lowerleg01.", "shin."), ("lowerleg02.", "shin."), ("foot.", "foot.")):
            rot[n3 + s] = _dir_rot(rig, n3 + s, d_old(no + s))
    _torso_mo(rot, mo)                                                          # before the hand IK: the hands stay on the knees
    posed = apply_pose(rig, rot)
    for s in ("L", "R"):
        sx = 1.0 if s == "L" else -1.0
        kn = posed["lowerleg01." + s].translation; thd = (kn - posed["upperleg01." + s].translation).normalized()
        upv = (Vector((0, 0, 1)) - thd * thd.z).normalized(); sh = posed["upperarm01." + s].translation
        la = (B["upperarm02." + s].tail_local - B["upperarm01." + s].head_local).length; lb = (B["lowerarm02." + s].tail_local - B["lowerarm01." + s].head_local).length
        for back in [0.05 + 0.02 * i for i in range(20)]:                        # palm on the knee, or as far forward as the arm reaches
            wr = kn - thd * back + upv * 0.075 + Vector((0.01 * sx, 0, 0))
            if (wr - sh).length <= 0.985 * (la + lb): break
        el = _ik2(sh, la, lb, wr, sh + Vector((sx * 0.5, 0.3, -0.4)))
        for n in ("upperarm01.", "upperarm02."): rot[n + s] = _dir_rot(rig, n + s, el - sh)
        for n in ("lowerarm01.", "lowerarm02."): rot[n + s] = _dir_rot(rig, n + s, wr - el)
        rot["wrist." + s] = _dir_rot(rig, "wrist." + s, thd + Vector((0, 0, -0.35)))
    posed = apply_pose(rig, rot); rot.update(_finger_rots(rig, posed, 0.35))
    rot, posed = _look(rig, rot, None, look_arm, mo=mo); return posed
