"""clip_B hero v4: ONE smooth sculpted mesh (hero_shape.py, rest A-pose) posed by an armature (automatic weights, preserve volume).
Shell = frosted glass (Principled, transmission 1, roughness 0.40, IOR 1.45); inside it a 0.85 copy on the same skeleton emitting
#FF8A5B (~2700 K). Dissolve/assemble via one value 'dissolve' (0 = whole, 1.1 = gone) shared by the shader mask and the GN particles.
Poses: pose_standing(...) contrapposto with torso/head turn, pose_seated(variant) -- bone targets in hero space (facing -Y)."""
import bpy, math, json, os
import numpy as np
from mathutils import Vector, Matrix

GLOW = (1.0, 0.254, 0.047)        # #FF8A5B in scene-linear
GLOW_NOM = 1.0                    # nominal glow multiplier; the vocal envelope pulses around it
NOISE_SCALE = 6.0

def V(*a): return Vector(a if len(a) == 3 else a[0])

# ---------------- mesh + armature ----------------
def load_mesh(path, name):
    """npz from hero_shape.py -> smooth-shaded mesh; returns (mesh, bones list)"""
    d = np.load(path); v = d["verts"]
    if "faces" in d: f = d["faces"]; lv, ls, lt = f.ravel(), np.arange(0, f.size, 3, dtype=np.int32), np.full(len(f), 3, np.int32)   # raw triangles
    else: lv, ls, lt = d["loops"], d["loop_start"], d["loop_total"]                                                       # baked polygons
    me = bpy.data.meshes.new(name); me.vertices.add(len(v)); me.vertices.foreach_set("co", v.ravel())
    me.loops.add(len(lv)); me.loops.foreach_set("vertex_index", lv)
    me.polygons.add(len(ls)); me.polygons.foreach_set("loop_start", ls); me.polygons.foreach_set("loop_total", lt)
    me.polygons.foreach_set("use_smooth", np.ones(len(ls), bool)); me.update(); me.validate()
    return me, json.loads(str(d["bones"]))

def build_rig(coll, B, name):
    ad = bpy.data.armatures.new(name + "_Rig"); arm = bpy.data.objects.new(name, ad); coll.objects.link(arm)
    vl = bpy.context.view_layer; vl.objects.active = arm
    for o in vl.objects: o.select_set(o == arm)
    bpy.ops.object.mode_set(mode="EDIT")
    for b in B:
        eb = ad.edit_bones.new(b["name"]); eb.head = V(b["head"]); eb.tail = V(b["tail"]); eb.roll = 0.0
    for b in B:
        if b["parent"]: eb = ad.edit_bones[b["name"]]; eb.parent = ad.edit_bones[b["parent"]]; eb.use_connect = b["connect"]
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm

def bind(mesh_ob, arm):
    """automatic (bone heat) weights; a vertex left without weights falls back to its nearest bone"""
    vl = bpy.context.view_layer
    for o in vl.objects: o.select_set(o in (mesh_ob, arm))
    vl.objects.active = arm
    with bpy.context.temp_override(active_object=arm, object=arm, selected_objects=[mesh_ob, arm], selected_editable_objects=[mesh_ob, arm]):
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    mod = next(m for m in mesh_ob.modifiers if m.type == "ARMATURE"); mod.use_deform_preserve_volume = True
    me = mesh_ob.data; tot = np.zeros(len(me.vertices))
    for v in me.vertices: tot[v.index] = sum(g.weight for g in v.groups)
    bad = np.where(tot < 1e-4)[0]
    if len(bad):
        segs = [(vg, arm.data.bones[vg.name]) for vg in mesh_ob.vertex_groups if vg.name in arm.data.bones]
        for i in bad:
            p = me.vertices[i].co; best = None
            for vg, bn in segs:
                a, c = bn.head_local, bn.tail_local; t = max(0.0, min(1.0, (p - a).dot(c - a) / (c - a).length_squared)); dd = (a + (c - a) * t - p).length
                if best is None or dd < best[0]: best = (dd, vg)
            best[1].add([int(i)], 1.0, "REPLACE")
    mesh_ob.parent = arm
    return len(bad)

# ---------------- posing: bone directions (+ optional twist reference) in hero space ----------------
def _basis(d, r):
    d = d.normalized(); r = (r - r.dot(d) * d).normalized(); return Matrix((d, r, d.cross(r))).transposed()

REST_REF = {"upperarm": V(0, -1, 0), "forearm": V(0, -1, 0), "hand": V(0, -1, 0), "thigh": V(0, -1, 0), "shin": V(0, -1, 0),
            "hips": V(1, 0, 0), "spine": V(1, 0, 0), "chest": V(1, 0, 0), "neck": V(1, 0, 0), "head": V(1, 0, 0), "foot": V(1, 0, 0)}

def apply_pose(arm, T, hips_head=None):
    """T: bone -> (dir, ref or None) in hero space. Bones are set parent-first; bones not in T keep their rest relation to the parent"""
    for pb in arm.pose.bones: pb.rotation_mode = "QUATERNION"; pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    order = []
    def walk(b):
        order.append(b.name)
        for c in b.children: walk(c)
    for b in arm.data.bones:
        if b.parent is None: walk(b)
    for name in order:
        if name not in T: bpy.context.view_layer.update(); continue
        pb = arm.pose.bones[name]; bn = pb.bone; rest = bn.matrix_local
        d_rest = (bn.tail_local - bn.head_local).normalized(); d_t, r_t = T[name]; d_t = V(d_t).normalized()
        r_rest = REST_REF.get(name.split(".")[0])
        if r_t is None or r_rest is None: R = d_rest.rotation_difference(d_t).to_matrix()
        else: R = _basis(d_t, V(r_t)) @ _basis(d_rest, r_rest).transposed()
        if bn.parent is None: head = V(hips_head) if hips_head is not None else bn.head_local
        else:
            pp = arm.pose.bones[bn.parent.name]; head = pp.matrix @ bn.parent.matrix_local.inverted() @ bn.head_local
        pb.matrix = Matrix.Translation(head) @ (R @ rest.to_3x3()).to_4x4()
        bpy.context.view_layer.update()

def posed(arm, bone, end="head"):
    pb = arm.pose.bones[bone]; return (pb.head if end == "head" else pb.tail).copy()

def _ik(a, b, la, lb, pole):
    d = b - a; L = min(d.length, la + lb - 1e-4); u = d.normalized()
    x = (la * la - lb * lb + L * L) / (2 * L); h = math.sqrt(max(la * la - x * x, 0.0)); p = (pole - pole.dot(u) * u).normalized()
    return a + u * x + p * h, d.length > la + lb

def _rz(v, ang): return Matrix.Rotation(ang, 3, "Z") @ V(v)

def pose_standing(arm, torso_yaw=0.0, head_yaw=0.0):
    """contrapposto: weight on the right leg (-X), right hip up / right shoulder down, relaxed left knee, arms hanging. yaw > 0 turns left"""
    up = lambda v: _rz(v, torso_yaw)
    T = {"hips": ((0, 0, 1), (1, 0, -0.07)), "spine": ((0.035, 0, 1), (1, 0, -0.02)),
         "chest": (up((-0.01, 0.025, 1)), up((1, 0, 0.07))), "neck": (up((0, -0.10, 1)), up((1, 0, 0))),
         "upperarm.R": (up((-0.12, 0.05, -1)), up((0, -1, 0))), "forearm.R": (up((-0.05, -0.10, -1)), up((0, -1, 0.10))), "hand.R": (up((0.02, -0.05, -1)), up((0.10, -1, 0))),
         "upperarm.L": (up((0.10, 0.06, -1)), up((0, -1, 0))), "forearm.L": (up((0.07, -0.28, -1)), up((0, -1, 0.28))), "hand.L": (up((0.02, -0.22, -1)), up((-0.10, -1, 0.20))),
         "thigh.R": ((0.03, -0.01, -1), (0, -1, 0)), "shin.R": ((-0.005, 0.03, -1), (0, -1, 0)), "foot.R": ((-0.02, -1, -0.40), None),
         "thigh.L": ((0.0, -0.16, -1), (0.15, -1, -0.16)), "shin.L": ((0.07, 0.07, -1), (0.15, -1, 0)), "foot.L": ((0.28, -1, -0.38), None)}
    nd = up((0, -0.10, 1)).normalized(); T["head"] = (Matrix.Rotation(head_yaw, 3, nd) @ up((0, -0.03, 1)), Matrix.Rotation(head_yaw, 3, nd) @ up((1, 0, 0)))
    apply_pose(arm, T, hips_head=(-0.018, 0.0, 0.928))
    return T

SEATED = {   # recline of the back (deg), pelvis tilt (deg), thigh rise (deg), knee angle (deg)
    "req": dict(recline=3, pelvis=6, thigh=0, knee=90),         # as asked: thighs horizontal, knees 90, back on the backrest
    "fit": dict(recline=25, pelvis=20, thigh=12, knee=155)}     # what fits the 1.1 m tall stunt car (inner floor 0.12, roof 1.10)

def pose_seated(arm, variant="fit", head_yaw=0.0, head_pitch=0.0):
    """seated on a cushion whose top is z = 0, back against the backrest, hands resting on the knees"""
    P = SEATED[variant]; rc, pv, th, kn = (math.radians(P[k]) for k in ("recline", "pelvis", "thigh", "knee"))
    back = V(0, math.sin(rc), math.cos(rc)); shin_a = th - (math.pi - kn)                      # shin angle from horizontal (negative = down)
    T = {"hips": ((0, math.sin(pv), math.cos(pv)), (1, 0, 0)), "spine": (back, (1, 0, 0)), "chest": (back, (1, 0, 0)),
         "neck": ((0, -0.02, 1), (1, 0, 0))}
    Rh = Matrix.Rotation(head_yaw, 3, V(0, -0.02, 1).normalized()) @ Matrix.Rotation(-head_pitch, 3, "X")       # pitch > 0 looks up
    T["head"] = (Rh @ V(0, -0.04, 1), Rh @ V(1, 0, 0))
    for s, sx in (("L", 1), ("R", -1)):
        T["thigh." + s] = ((0.06 * sx, -math.cos(th), math.sin(th)), (0, math.sin(th), math.cos(th)))    # kneecap up/forward
        T["shin." + s] = ((0, -math.cos(shin_a), math.sin(shin_a)), (0, -1, 0))
        T["foot." + s] = ((0, -0.92, 0.38 if variant == "fit" else -0.35), None)
    hip_off = (arm.data.bones["thigh.L"].head_local - arm.data.bones["hips"].head_local)       # hip joints sit 0.085 above the cushion
    tilt = Matrix.Rotation(-pv, 3, "X"); hj = tilt @ hip_off                                      # the hips bone tilts back (+Y)
    apply_pose(arm, T, hips_head=(0, -hj.y, 0.085 - hj.z))
    # shoulders slightly forward (reaching to the knees), then arms: palms on the knees, thumbs inward (two-bone IK)
    pc = arm.pose.bones["chest"]; Rc = pc.matrix.to_3x3() @ pc.bone.matrix_local.to_3x3().inverted()
    for s, sx in (("L", 1), ("R", -1)):
        b = arm.data.bones["shoulder." + s]; T["shoulder." + s] = (Rc @ (Matrix.Rotation(-0.32 * sx, 3, "Z") @ (b.tail_local - b.head_local)), None)
    apply_pose(arm, T, hips_head=(0, -hj.y, 0.085 - hj.z))
    la = arm.data.bones["upperarm.L"].length; lb = arm.data.bones["forearm.L"].length; warn = []
    for s, sx in (("L", 1), ("R", -1)):
        kn_p = posed(arm, "shin." + s); thd = (kn_p - posed(arm, "thigh." + s)).normalized(); sh = posed(arm, "upperarm." + s)
        upv = (V(0, 0, 1) - thd * thd.z).normalized()                                       # thigh's top side
        for back in [0.06 + 0.02 * i for i in range(20)]:                                   # palm on the knee, or as far forward as the arm reaches
            wr = kn_p - thd * back + upv * 0.082 + V(0.01 * sx, 0, 0)
            if (wr - sh).length <= 0.985 * (la + lb): break
        el, far = _ik(sh, wr, la, lb, V(sx, 0.6, -0.4)); warn.append(f"{s}: wrist {back:.2f} m behind the knee")
        T["upperarm." + s] = (el - sh, (wr - el)); T["forearm." + s] = (wr - el, V(-sx, 0, 0)); T["hand." + s] = (thd + V(0, 0, -0.25), V(-sx, 0, 0))
    apply_pose(arm, T, hips_head=(0, -hj.y, 0.085 - hj.z))
    print(f"seated {variant}:", "; ".join(warn), flush=True)
    return T

# ---------------- materials ----------------
def _mask(nt, co, dissolve_socket):
    """visible = smoothstep(dissolve, dissolve + 0.05, m), m = 0.6 * noise + 0.4 * height: the feet go first"""
    def N(t): return nt.nodes.new(t)
    sep = N("ShaderNodeSeparateXYZ"); nt.links.new(co, sep.inputs[0])
    nz = N("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = NOISE_SCALE; nz.inputs["Detail"].default_value = 2.0; nt.links.new(co, nz.inputs["Vector"])
    h = N("ShaderNodeMapRange"); h.inputs["From Min"].default_value = 0.0; h.inputs["From Max"].default_value = 1.8; h.inputs["To Min"].default_value = 0.0; h.inputs["To Max"].default_value = 0.4
    nt.links.new(sep.outputs["Z"], h.inputs["Value"])
    mn = N("ShaderNodeMath"); mn.operation = "MULTIPLY"; mn.inputs[1].default_value = 0.6; nt.links.new(nz.outputs["Fac"], mn.inputs[0])
    m = N("ShaderNodeMath"); m.operation = "ADD"; nt.links.new(mn.outputs[0], m.inputs[0]); nt.links.new(h.outputs["Result"], m.inputs[1])
    a1 = N("ShaderNodeMath"); a1.operation = "ADD"; a1.inputs[1].default_value = 0.05; nt.links.new(dissolve_socket, a1.inputs[0])
    ss = N("ShaderNodeMapRange"); ss.interpolation_type = "SMOOTHSTEP"
    nt.links.new(m.outputs[0], ss.inputs["Value"]); nt.links.new(dissolve_socket, ss.inputs["From Min"]); nt.links.new(a1.outputs[0], ss.inputs["From Max"])
    return ss.outputs["Result"]

def _aov(nt, strength_socket, col, k):
    aov = nt.nodes.new("ShaderNodeOutputAOV"); aov.aov_name = "glow"
    sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; sc.inputs[0].default_value = tuple(c * k for c in col)
    nt.links.new(strength_socket, sc.inputs["Scale"]); nt.links.new(sc.outputs["Vector"], aov.inputs["Color"])

VOL_E = 16.0                       # volume emission per metre at the chest (fog patches x chest falloff): ~4x dimmer than the old surface core
VOL_D = 0.9                       # fog density: thin, the scene shows through the body

def _hero_materials(pre, root, chest, head=None):
    def TC(nt, ob=root):
        t = nt.nodes.new("ShaderNodeTexCoord"); t.object = ob; return t.outputs["Object"]
    def attr(nt, name, kind="OBJECT"):
        a = nt.nodes.new("ShaderNodeAttribute"); a.attribute_type = kind; a.attribute_name = name; return a.outputs["Fac"]
    def mul(nt, a, b):
        x = nt.nodes.new("ShaderNodeMath"); x.operation = "MULTIPLY"; nt.links.new(a, x.inputs[0])
        if isinstance(b, float): x.inputs[1].default_value = b
        else: nt.links.new(b, x.inputs[1])
        return x.outputs[0]
    def mrange(nt, v, a, b, c, d, smooth=True):
        x = nt.nodes.new("ShaderNodeMapRange"); x.interpolation_type = "SMOOTHSTEP" if smooth else "LINEAR"
        for k, val in zip(("From Min", "From Max", "To Min", "To Max"), (a, b, c, d)): x.inputs[k].default_value = val
        nt.links.new(v, x.inputs["Value"]); return x.outputs["Result"]
    # glass shell: Fresnel reflections of the scene lights on the edges, rough transmission
    glass = bpy.data.materials.new(pre + "_Glass"); glass.use_nodes = True; nt = glass.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); p = nt.nodes.new("ShaderNodeBsdfPrincipled"); p.name = "Principled BSDF"
    for k, v in (("Base Color", (0.88, 0.88, 0.88, 1)), ("Roughness", 0.20), ("IOR", 1.45), ("Transmission Weight", 1.0), ("Coat Weight", 0.30),
                 ("Coat Roughness", 0.05), ("Coat IOR", 1.5), ("Specular IOR Level", 0.5), ("Metallic", 0.0), ("Alpha", 1.0)):
        p.inputs[k].default_value = v
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
    vis = _mask(nt, TC(nt), attr(nt, "dissolve"))
    nt.links.new(vis, mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(p.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], o.inputs["Surface"])
    _aov(nt, mul(nt, attr(nt, "glow"), vis), GLOW, 0.12)                       # faint halo for the effects pass
    # glowing fog inside (the 0.85 inner copy has no surface, only this volume): 3-D noise patches, brightest in the chest
    core = bpy.data.materials.new(pre + "_Core"); core.use_nodes = True; nt = core.node_tree; nt.nodes.clear()
    core.cycles.homogeneous_volume = False; core.cycles.volume_step_rate = 0.5
    o = nt.nodes.new("ShaderNodeOutputMaterial"); pv = nt.nodes.new("ShaderNodeVolumePrincipled"); pv.name = "Principled Volume"
    pv.inputs["Color"].default_value = (0.92, 0.92, 0.92, 1); pv.inputs["Emission Color"].default_value = (*GLOW, 1); pv.inputs["Anisotropy"].default_value = 0.3
    def val(name, v):
        x = nt.nodes.new("ShaderNodeValue"); x.name = name; x.outputs[0].default_value = v; return x.outputs[0]
    g_v, d_v, e_v, k_v = val("glow_v", GLOW_NOM), val("dissolve_v", 0.0), val("vol_e", VOL_E), val("vol_d", VOL_D)
    co = TC(nt)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 7.0; nz.inputs["Detail"].default_value = 3.0; nz.inputs["Roughness"].default_value = 0.55
    nt.links.new(co, nz.inputs["Vector"]); m = mrange(nt, nz.outputs["Fac"], 0.35, 0.70, 0.15, 1.0)
    dl = nt.nodes.new("ShaderNodeVectorMath"); dl.operation = "LENGTH"; nt.links.new(TC(nt, chest), dl.inputs[0])
    cf = mrange(nt, dl.outputs["Value"], 0.03, 0.32, 1.0, 0.10)
    if head is not None:                                                         # weak glow in the head (~35 % of the chest) so the whole figure glows
        dh = nt.nodes.new("ShaderNodeVectorMath"); dh.operation = "LENGTH"; nt.links.new(TC(nt, head), dh.inputs[0])
        hf = mrange(nt, dh.outputs["Value"], 0.03, 0.15, 0.35, 0.0)
        mxn = nt.nodes.new("ShaderNodeMath"); mxn.operation = "MAXIMUM"; nt.links.new(cf, mxn.inputs[0]); nt.links.new(hf, mxn.inputs[1]); cf = mxn.outputs[0]
    _cf_dummy = 0                 # a soft warm spot in the chest, fading out toward the head, hands and feet
    vis = _mask(nt, co, d_v)
    e = mul(nt, mul(nt, mul(nt, mul(nt, m, cf), g_v), vis), e_v); nt.links.new(e, pv.inputs["Emission Strength"])
    dd = nt.nodes.new("ShaderNodeMath"); dd.operation = "MULTIPLY_ADD"; dd.inputs[1].default_value = 0.65; dd.inputs[2].default_value = 0.35; nt.links.new(m, dd.inputs[0])
    cd = nt.nodes.new("ShaderNodeMath"); cd.operation = "MULTIPLY_ADD"; cd.inputs[1].default_value = 0.6; cd.inputs[2].default_value = 0.4; nt.links.new(cf, cd.inputs[0])
    dens = mul(nt, mul(nt, mul(nt, dd.outputs[0], cd.outputs[0]), vis), k_v); nt.links.new(dens, pv.inputs["Density"])
    nt.links.new(pv.outputs["Volume"], o.inputs["Volume"])
    # particles: the same colour as the inner light
    part = bpy.data.materials.new(pre + "_Particle"); part.use_nodes = True; nt = part.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*GLOW, 1)
    br = attr(nt, "bright", "INSTANCER"); nt.links.new(br, em.inputs["Strength"]); nt.links.new(em.outputs[0], o.inputs["Surface"])
    _aov(nt, br, GLOW, 1.0)
    return glass, core, part

def dump_material(mat):
    """the values the renderer actually gets (unlinked inputs), for the log"""
    for n in mat.node_tree.nodes:
        if n.type in ("BSDF_PRINCIPLED", "PRINCIPLED_VOLUME"):
            vals = []
            for i in n.inputs:
                if not i.enabled or i.type == "SHADER" or i.name == "Weight": continue
                if i.is_linked: vals.append(i.name + "=<linked>"); continue
                v = i.default_value
                if not isinstance(v, str): v = tuple(round(x, 3) for x in v) if hasattr(v, "__len__") else (round(v, 3) if isinstance(v, float) else v)
                vals.append(i.name + "=" + str(v))
            print("MATERIAL " + mat.name + " / " + n.name + ": " + "; ".join(vals), flush=True)

# ---------------- particles (GN): released where the mask is below 'dissolve', drift out and up ----------------
def _particle_tree(src, part_mat):
    ng = bpy.data.node_groups.new(src.name + "_ParticlesGN", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
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
    go = N.new("NodeGroupOutput")
    oi = N.new("GeometryNodeObjectInfo"); oi.inputs["Object"].default_value = src; oi.transform_space = "RELATIVE"
    dist = N.new("GeometryNodeDistributePointsOnFaces"); dist.distribute_method = "RANDOM"; dist.inputs["Density"].default_value = 3000.0
    L.new(oi.outputs["Geometry"], dist.inputs["Mesh"])
    dval = N.new("ShaderNodeValue"); dval.name = "dissolve"
    pos = N.new("GeometryNodeInputPosition").outputs[0]
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = NOISE_SCALE; nz.inputs["Detail"].default_value = 2.0; L.new(pos, nz.inputs["Vector"])
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(pos, sep.inputs[0])
    h = N.new("ShaderNodeMapRange"); h.inputs["From Min"].default_value = 0.0; h.inputs["From Max"].default_value = 1.8; h.inputs["To Min"].default_value = 0.0; h.inputs["To Max"].default_value = 0.4
    L.new(sep.outputs["Z"], h.inputs["Value"])
    mask = m("ADD", m("MULTIPLY", nz.outputs["Fac"], 0.6), h.outputs["Result"])
    r = m("DIVIDE", m("SUBTRACT", dval.outputs[0], mask), 0.28)                     # 0 on release .. 1 gone
    rc = N.new("ShaderNodeClamp"); L.new(r, rc.inputs["Value"]); rc = rc.outputs[0]
    sel = N.new("FunctionNodeCompare"); sel.data_type = "FLOAT"; sel.operation = "GREATER_THAN"; L.new(r, sel.inputs["A"]); sel.inputs["B"].default_value = 0.0
    keep = N.new("GeometryNodeDeleteGeometry"); keep.domain = "POINT"; L.new(dist.outputs["Points"], keep.inputs["Geometry"])
    inv = N.new("FunctionNodeBooleanMath"); inv.operation = "NOT"; L.new(sel.outputs["Result"], inv.inputs[0]); L.new(inv.outputs[0], keep.inputs["Selection"])
    rnd = N.new("FunctionNodeRandomValue"); rnd.data_type = "FLOAT_VECTOR"; rnd.inputs["Min"].default_value = (-0.05, -0.05, 0.7); rnd.inputs["Max"].default_value = (0.05, 0.05, 1.3)
    flow = vm("ADD", vm("SCALE", rnd.outputs["Value"], scale=1.0), (0.0, 0.0, 0.3))   # thin streams rising
    sw = N.new("ShaderNodeTexNoise"); sw.noise_dimensions = "4D"; sw.inputs["Scale"].default_value = 1.5; L.new(pos, sw.inputs["Vector"]); L.new(dval.outputs[0], sw.inputs["W"])
    swv = vm("SCALE", vm("SUBTRACT", sw.outputs["Color"], (0.5, 0.5, 0.5)), scale=0.18)
    off = vm("SCALE", vm("ADD", flow, swv), scale=m("MULTIPLY", m("POWER", rc, 1.3), 1.6))
    sp = N.new("GeometryNodeSetPosition"); L.new(keep.outputs[0], sp.inputs["Geometry"]); L.new(off, sp.inputs["Offset"])
    ico = N.new("GeometryNodeMeshIcoSphere"); ico.inputs["Radius"].default_value = 1.0; ico.inputs["Subdivisions"].default_value = 1
    inst = N.new("GeometryNodeInstanceOnPoints"); L.new(sp.outputs[0], inst.inputs["Points"]); L.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    rs = N.new("FunctionNodeRandomValue"); rs.data_type = "FLOAT"; rs.inputs[2].default_value = 0.003; rs.inputs[3].default_value = 0.007
    L.new(m("MULTIPLY", rs.outputs[1], m("SUBTRACT", 1.0, m("MULTIPLY", rc, 0.8))), inst.inputs["Scale"])
    br = N.new("GeometryNodeStoreNamedAttribute"); br.data_type = "FLOAT"; br.domain = "INSTANCE"; br.inputs["Name"].default_value = "bright"
    L.new(inst.outputs[0], br.inputs["Geometry"]); L.new(m("ADD", m("MULTIPLY", m("SUBTRACT", 1.0, rc), 1.3), 0.35), br.inputs["Value"])  # stays coral under AgX
    smat = N.new("GeometryNodeSetMaterial"); smat.inputs["Material"].default_value = part_mat; L.new(br.outputs[0], smat.inputs["Geometry"])
    L.new(smat.outputs[0], go.inputs[0])
    return ng

def _exclude_from_light(light_ob, objs, tag):
    """the inner light lights the surroundings, not the hero's own glass (no hot spots on the shell)"""
    try:
        rc = bpy.data.collections.new(tag); light_ob.light_linking.receiver_collection = rc
        for ob in objs:
            rc.objects.link(ob); rc.collection_objects[list(rc.objects).index(ob)].light_linking.link_state = "EXCLUDE"
    except Exception as e: print("light linking unavailable:", e, flush=True)

# ---------------- assembly ----------------
def build_hero(coll, mesh_dir, mesh_name, name="Hero", scale=1.0, clay=None):
    """meshes: mesh_dir/mesh_name_shell.npz + _core.npz (hero_shape.py). The armature object is the hero root.
    clay: a material -> clay check (shell only, no core/particles/light). returns dict(root, shell, core, parts, lights, ng)"""
    me_s, B = load_mesh(os.path.join(mesh_dir, mesh_name + "_shell.npz"), name + "_ShellMesh")
    root = build_rig(coll, B, name); root.scale = (scale,) * 3
    shell = bpy.data.objects.new(name + "_Shell", me_s); coll.objects.link(shell)
    nb = bind(shell, root)
    sub = shell.modifiers.new("subdivision", "SUBSURF"); sub.levels = 0; sub.render_levels = 1                     # render only
    hero = dict(root=root, shell=shell, scale=scale, unweighted=nb)
    if clay is not None:
        shell.data.materials.append(clay); print(f"hero {name}: {len(me_s.polygons)} tris, unweighted verts {nb}", flush=True); return hero
    chest = bpy.data.objects.new(name + "_ChestCentre", None); coll.objects.link(chest); chest.parent = root; chest.parent_type = "BONE"; chest.parent_bone = "chest"
    chest.location = (0, -0.10, 0)                                                                   # bone-parented (tail-relative): mid chest
    head_c = bpy.data.objects.new(name + "_HeadCentre", None); coll.objects.link(head_c); head_c.parent = root; head_c.parent_type = "BONE"; head_c.parent_bone = "head"; head_c.location = (0, -0.085, 0)
    glass, core_m, part_m = _hero_materials(name, root, chest, head_c); shell.data.materials.append(glass)
    me_c, _ = load_mesh(os.path.join(mesh_dir, mesh_name + "_core.npz"), name + "_CoreMesh")
    core = bpy.data.objects.new(name + "_Core", me_c); coll.objects.link(core); bind(core, root)
    sub = core.modifiers.new("subdivision", "SUBSURF"); sub.levels = 0; sub.render_levels = 1; core.data.materials.append(core_m)
    for ob in (shell, core): ob.visible_shadow = False                # the inner light reaches the surroundings through the glass
    dump_material(glass); dump_material(core_m)
    ld = bpy.data.lights.new(name + "_Light", "POINT"); ld.color = GLOW; ld.energy = 45.0; ld.shadow_soft_size = 0.25
    lo = bpy.data.objects.new(name + "_Light", ld); coll.objects.link(lo); lo.parent = root; lo.parent_type = "BONE"; lo.parent_bone = "chest"
    lo.location = (0, -0.09, 0); lo["base"] = 45.0                                    # warm spill on the floor and the car                                                   # bone-parented: tail-relative, mid chest
    pm = bpy.data.meshes.new(name + "_PartsMesh"); parts = bpy.data.objects.new(name + "_Particles", pm); coll.objects.link(parts); parts.parent = root
    mod = parts.modifiers.new("particles", "NODES"); mod.node_group = _particle_tree(shell, part_m); parts.visible_shadow = False
    _exclude_from_light(lo, (shell, core, parts), name + "_LightExcl")
    hero.update(core=core, parts=parts, lights=[lo], ng=mod.node_group)
    set_state(hero, dissolve=0.0, glow=GLOW_NOM)
    print(f"hero {name}: shell {len(me_s.polygons)} tris, core {len(me_c.polygons)} tris, unweighted verts {nb}", flush=True)
    return hero

def lowest_z(hero):
    """lowest point of the posed shell in the root's space (to put the feet on the ground / the seat)"""
    dg = bpy.context.evaluated_depsgraph_get(); ev = hero["shell"].evaluated_get(dg); me = ev.to_mesh()
    z = min(v.co.z for v in me.vertices); ev.to_mesh_clear(); return z

def set_state(hero, dissolve, glow, frame=None):
    """dissolve: 0 whole .. 1.1 gone (assemble = the same run backwards); glow: core emission strength (light follows)"""
    for ob in (hero["shell"], hero["core"]):
        ob["dissolve"] = dissolve; ob["glow"] = glow
        if frame is not None: ob.keyframe_insert('["dissolve"]', frame=frame); ob.keyframe_insert('["glow"]', frame=frame)
    dv = hero["ng"].nodes["dissolve"].outputs[0]; dv.default_value = dissolve
    if frame is not None: dv.keyframe_insert("default_value", frame=frame)
    for nm, v in (("glow_v", glow), ("dissolve_v", dissolve)):                     # the inner fog reads Value nodes
        o = hero["core"].data.materials[0].node_tree.nodes[nm].outputs[0]; o.default_value = v
        if frame is not None: o.keyframe_insert("default_value", frame=frame)
    vis = max(0.0, min(1.0, 1.0 - dissolve))
    for lo in hero["lights"]:
        lo.data.energy = lo["base"] * glow / GLOW_NOM * vis
        if frame is not None: lo.data.keyframe_insert("energy", frame=frame)
