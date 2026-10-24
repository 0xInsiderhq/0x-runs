# clip_B hero v3: the head (or the bust down to the chest) as a closed watertight solid with clean flat cuts, for review renders:
#   clay  - studio clay, front / 3/4 / profile
#   glass - the v3 glass on a grey backdrop
#   glow  - the v3 glass (frosted 0.30-0.40, light and slightly cold at the edges) over a neutral absorbing inner volume; amber #FF8A3D only
#           inside: the chest core and 25-40 thin branching optical-fibre filaments from the core up the neck, fanned over the whole head,
#           dim, a slow pulse running along them; clip light: dark strip with markers, ground fog, key from above-side, cold rim from behind
# usage: blender -b --python v3_bust.py -- <blend> <tag> <clay|glass|glow> <views: front,three_quarter,profile,eye,chest> [head|chest]
#        -> v3/face/<tag>_<mode>_<view>.png
import bpy, bmesh, sys, os, math, random
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--") + 1:]; BLEND, TAG, MODE, VIEWS = a[0], a[1], a[2], a[3].split(","); KIND = a[4] if len(a) > 4 else "head"
OUT = "/content/drive/MyDrive/renders/clip_B/v3/face"; os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene; src = bpy.data.objects["HeroV3"]
for m in src.modifiers: m.show_viewport = m.show_render = m.type != "ARMATURE"
ss = src.modifiers.new("ss", "SUBSURF"); ss.levels = ss.render_levels = 2
me = bpy.data.meshes.new_from_object(src.evaluated_get(bpy.context.evaluated_depsgraph_get())); me.transform(src.matrix_world)
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)
bm = bmesh.new(); bm.from_mesh(me); bvh_full = BVHTree.FromBMesh(bm)
def mid_y(z, x=0.0):
    # front and back surface of the body at height z (rays along y)
    f_ = bvh_full.ray_cast(Vector((x, -0.6, z)), Vector((0, 1, 0)))[0]; b_ = bvh_full.ray_cast(Vector((x, 0.6, z)), Vector((0, -1, 0)))[0]
    return (f_.y, b_.y) if f_ and b_ else (-0.1, 0.1)
fy_, by_ = mid_y(1.33); CORE = Vector((0.0, fy_ + 0.30 * (by_ - fy_), 1.33))       # the chest core, ~5 cm under the sternum
NECK = [Vector((0.0, sum(mid_y(z)) / 2 + dy_, z)) for z, dy_ in ((1.42, 0.0), (1.47, 0.014), (1.53, 0.016))]   # the bundle runs up the back of the neck (no glow through the jaw)
CUTS = [((0, 0, 1.47), (0, 0, 1))] if KIND == "head" else [((0, 0, 1.20), (0, 0, 1)), ((0.185, 0, 0), (-1, 0, 0)), ((-0.185, 0, 0), (1, 0, 0))]
for co_, no_ in CUTS:
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7, plane_co=co_, plane_no=no_, clear_inner=True)
bm.verts.ensure_lookup_table(); top = max(bm.verts, key=lambda v: v.co.z); seen = {top}; st = [top]
while st:                                                                       # the one island with the head (no loose inner shells, no arm stubs)
    v = st.pop()
    for e in v.link_edges:
        w = e.other_vert(v)
        if w not in seen: seen.add(w); st.append(w)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v not in seen], context="VERTS")
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
for f in bm.faces: f.smooth = True
bm.edges.ensure_lookup_table(); rim = [e for e in bm.edges if e.is_boundary]
cap = bmesh.ops.holes_fill(bm, edges=rim, sides=0)["faces"]
cap = bmesh.ops.triangulate(bm, faces=cap, quad_method="BEAUTY", ngon_method="BEAUTY")["faces"]
for f in cap: f.smooth = False                                                  # the cuts: flat planes, crisp edges
for e in rim: e.smooth = False
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])                            # one consistent winding ...
if bm.calc_volume(signed=True) < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])   # ... pointing outward
bm.edges.ensure_lookup_table()
nb_ = sum(e.is_boundary for e in bm.edges); nm_ = sum((not e.is_manifold) and (not e.is_boundary) for e in bm.edges)
print("SOLID %s closed=%s boundary=%d nonmanifold=%d volume=%.1f cm3 faces=%d cap=%d core=%s" % (KIND, nb_ == 0, nb_, nm_, 1e6 * bm.calc_volume(signed=True), len(bm.faces), len(cap),
      tuple(round(x, 3) for x in CORE)), flush=True)
bm.to_mesh(me); bvh = BVHTree.FromBMesh(bm); bm.free()
bust = bpy.data.objects.new("Bust", me); sc.collection.objects.link(bust)
sc.render.engine = "CYCLES"; sc.cycles.device = "GPU"
pr = bpy.context.preferences.addons["cycles"].preferences; pr.compute_device_type = "OPTIX"; pr.get_devices()
for d in pr.devices: d.use = d.type == "OPTIX"
sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"; sc.cycles.use_adaptive_sampling = True
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = {"clay": "AgX - Medium High Contrast", "glass": "None", "glow": "AgX - Base Contrast"}[MODE]
sc.render.resolution_x, sc.render.resolution_y = 700, 800
if MODE == "glow": sc.view_settings.exposure = -0.3
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.006, 0.012, 1) if MODE == "glow" else (0.022, 0.024, 0.03, 1)
GLOW = (1.0, 0.254, 0.047)                                                       # #FF8A3D in linear RGB
COLD = (0.72, 0.85, 1.0)
def N(nt, t, **kw):
    x = nt.nodes.new(t)
    for k, v in kw.items(): setattr(x, k, v)
    return x
def maprange(nt, v, a_, b_, c_, d_, smooth=False):
    x = N(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP" if smooth else "LINEAR")
    x.inputs["From Min"].default_value, x.inputs["From Max"].default_value, x.inputs["To Min"].default_value, x.inputs["To Max"].default_value = a_, b_, c_, d_
    nt.links.new(v, x.inputs["Value"]); return x.outputs["Result"]
def math_(nt, op, a_, b_=None):
    x = N(nt, "ShaderNodeMath", operation=op)
    for i, v in enumerate((a_, b_)):
        if v is None: continue
        if isinstance(v, (int, float)): x.inputs[i].default_value = v
        else: nt.links.new(v, x.inputs[i])
    return x.outputs[0]
mat = bpy.data.materials.new("M"); mat.use_nodes = True; nt = mat.node_tree; p = nt.nodes["Principled BSDF"]; mo = nt.nodes["Material Output"]
if MODE == "clay":
    p.inputs["Base Color"].default_value = (0.60, 0.58, 0.55, 1); p.inputs["Roughness"].default_value = 0.6
    sc.cycles.samples = 96; sc.cycles.adaptive_threshold = 0.02
else:                                                                            # the v3 glass: frosted + fine noise, thin film 500 nm, dispersion, IOR 1.45
    for k, v in (("Base Color", (0.93, 0.95, 0.97, 1)), ("IOR", 1.45), ("Transmission Weight", 1.0), ("Coat Weight", 0.25), ("Coat Roughness", 0.05),
                 ("Thin Film Thickness", 500.0), ("Thin Film IOR", 1.38)):
        p.inputs[k].default_value = v
    # a little dispersion (no Dispersion input in 4.5): three glass lobes, R / G / B with IOR 1.440 / 1.450 / 1.462, mixed into the principled shell
    gls = []
    for col_, ior_ in (((0.93, 0, 0, 1), 1.440), ((0, 0.95, 0, 1), 1.450), ((0, 0, 0.97, 1), 1.462)):
        g_ = nt.nodes.new("ShaderNodeBsdfGlass"); g_.inputs["IOR"].default_value = ior_; g_.inputs["Color"].default_value = col_; gls.append(g_)
    ad1 = nt.nodes.new("ShaderNodeAddShader"); ad2 = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(gls[0].outputs[0], ad1.inputs[0]); nt.links.new(gls[1].outputs[0], ad1.inputs[1]); nt.links.new(ad1.outputs[0], ad2.inputs[0]); nt.links.new(gls[2].outputs[0], ad2.inputs[1])
    mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs[0].default_value = 0.35
    nt.links.new(p.outputs[0], mx.inputs[1]); nt.links.new(ad2.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], mo.inputs["Surface"])
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 38.0; nz.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rough = maprange(nt, nz.outputs["Fac"], 0.3, 0.7, *((0.30, 0.40) if MODE == "glow" else (0.25, 0.35)))
    nt.links.new(rough, p.inputs["Roughness"])
    for g_ in gls: nt.links.new(rough, g_.inputs["Roughness"])
    sc.cycles.samples = 384 if MODE == "glass" else 640; sc.cycles.adaptive_threshold = 0.01
    sc.cycles.max_bounces = 16; sc.cycles.transmission_bounces = 12; sc.cycles.glossy_bounces = 4; sc.cycles.transparent_max_bounces = 16
    sc.cycles.volume_bounces = 2
if MODE == "glow":
    # inner volume: neutral, slightly cold, absorbing more than scattering (hides the back wall, no tint on the surface);
    # emission only in the chest core: a bright ball fading out within ~6 cm
    pv = N(nt, "ShaderNodeVolumePrincipled"); pv.inputs["Color"].default_value = (0.30, 0.33, 0.37, 1); pv.inputs["Anisotropy"].default_value = 0.3
    pv.inputs["Emission Color"].default_value = (*GLOW, 1)
    oc = tc.outputs["Object"]
    dv = N(nt, "ShaderNodeVectorMath", operation="DISTANCE"); nt.links.new(oc, dv.inputs[0]); dv.inputs[1].default_value = CORE
    fall = math_(nt, "POWER", maprange(nt, dv.outputs["Value"], 0.0, 0.08, 1.0, 0.0, smooth=True), 2.0)
    nt.links.new(math_(nt, "MULTIPLY", fall, 16.0), pv.inputs["Emission Strength"])
    mat.cycles.volume_step_rate = 0.25                                           # fine steps inside the bust (the fog keeps coarse ones)
    if KIND == "chest":                                                          # the hot centre of the core (inside the chest bust only)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.015, location=CORE, segments=24, ring_count=12); core_ob = bpy.context.active_object
        cm_ = bpy.data.materials.new("CoreHot"); cm_.use_nodes = True; ct_ = cm_.node_tree; ct_.nodes.clear(); ce_ = N(ct_, "ShaderNodeEmission")
        ce_.inputs["Color"].default_value = (*GLOW, 1); ce_.inputs["Strength"].default_value = 8.0; ct_.links.new(ce_.outputs[0], N(ct_, "ShaderNodeOutputMaterial").inputs["Surface"])
        core_ob.data.materials.append(cm_); core_ob.visible_shadow = False
    vn = N(nt, "ShaderNodeTexNoise"); vn.inputs["Scale"].default_value = 18.0; vn.inputs["Detail"].default_value = 2.0; nt.links.new(oc, vn.inputs["Vector"])
    zs_ = N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(oc, zs_.inputs[0])                # the torso clearer than the head: the core light spreads
    nt.links.new(math_(nt, "MULTIPLY", maprange(nt, vn.outputs["Fac"], 0.3, 0.7, 9.0, 15.0), maprange(nt, zs_.outputs["Z"], 1.40, 1.50, 0.35, 1.0, smooth=True)), pv.inputs["Density"])
    nt.links.new(pv.outputs[0], mo.inputs["Volume"])
me.materials.append(mat)
H = Vector((0.0, -0.03, 1.585))
if MODE == "glow":
    # optical-fibre filaments: a loose bundle from the core up the neck, branching at hubs in the lower head, fanned to endpoints 1 cm under the
    # surface all over the head (front, sides, back, crown); a few go to the shoulders. radius 0.35 -> 0.18 mm, dim, fading to the ends,
    # a slow pulse = a soft band at a per-fibre phase (attribute ph; in the clip ph runs with time)
    rnd = random.Random(7)
    def inside(q, margin):
        loc, nrm, idx, dist = bvh.find_nearest(q)
        return loc is not None and (q - loc).dot(nrm) < 0 and dist > margin
    H0 = Vector((0.0, -0.035, 1.61)); ends = []
    for i in range(160):
        zz = 1 - 2 * (i + 0.5) / 160; rr = math.sqrt(max(0, 1 - zz * zz)); ph_ = i * math.pi * (3 - math.sqrt(5))
        d = Vector((rr * math.cos(ph_), rr * math.sin(ph_), zz))
        if d.z < -0.25 or len(ends) >= 36: continue
        if i % 3: continue
        d = (d + Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), rnd.uniform(-0.05, 0.05)))).normalized()
        up_t = (Vector((0, 0, 1)) - d * d.z).normalized() if abs(d.z) < 0.97 else Vector((0, 1, 0))       # along the meridian, toward the crown
        d2 = (d + up_t * rnd.uniform(0.16, 0.34)).normalized(); h1 = bvh_full.ray_cast(H0, d); h2 = bvh_full.ray_cast(H0, d2)
        if h1[0] and h2[0]: ends.append((h1[0] - h1[1] * 0.013, h1[0] - h1[1] * 0.005, h2[0] - h2[1] * 0.004))   # approach, under the skin, run 2-3 cm
    HUBS = [H0 + Vector((0.022 * math.cos(k * math.pi / 3), 0.022 * math.sin(k * math.pi / 3), -0.045 + 0.01 * (k % 2))) for k in range(6)]
    paths = []
    for e_ in ends:
        hub = min(HUBS, key=lambda h: ((e_[0] - H0).normalized() - (h - H0 + Vector((0, 0, 0.045))).normalized()).length)
        j = lambda s_: Vector((rnd.uniform(-s_, s_), rnd.uniform(-s_, s_), rnd.uniform(-s_ * 0.3, s_ * 0.3)))
        paths.append([CORE + j(0.012), NECK[0] + j(0.010), NECK[1] + j(0.009), NECK[2] + j(0.008), hub + j(0.004), e_[0], e_[1], e_[2]])
    for sx in (1, -1):                                                         # to the shoulders / arms
        for k in range(3):
            j = lambda s_: Vector((rnd.uniform(-s_, s_), rnd.uniform(-s_, s_), rnd.uniform(-s_, s_)))
            paths.append([CORE + j(0.01), CORE + Vector((sx * 0.06, 0.0, 0.05)) + j(0.012), Vector((sx * 0.13, CORE.y + 0.01, 1.41)) + j(0.01), Vector((sx * 0.178, CORE.y, 1.37 - 0.03 * k))])
    def catmull(P, n):
        P = [P[0]] + P + [P[-1]]; out = []
        for s_ in range(1, len(P) - 2):
            p0, p1, p2, p3 = P[s_ - 1], P[s_], P[s_ + 1], P[s_ + 2]
            for i in range(n):
                t = i / n; t2, t3 = t * t, t * t * t
                out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
        out.append(P[-2]); return out
    fme = bpy.data.meshes.new("Filaments"); verts, faces, us, phs = [], [], [], []; SIDES = 5; kept = 0
    for k, P in enumerate(paths):
        pts = [q for q in catmull(P, 14) if inside(q, 0.002)]                  # only what lies inside the solid (the head bust starts at the neck cut)
        if len(pts) < 8: continue
        kept += 1; ph = rnd.random(); L = len(pts) - 1; b0 = len(verts)
        for i, q in enumerate(pts):
            tg = (pts[min(i + 1, L)] - pts[max(i - 1, 0)]).normalized(); n1 = tg.cross(Vector((0.3, 0.2, 0.93))).normalized(); n2 = tg.cross(n1)
            rad = 0.00035 - 0.00017 * i / L
            for s_ in range(SIDES):
                ang = 2 * math.pi * s_ / SIDES; verts.append(q + (n1 * math.cos(ang) + n2 * math.sin(ang)) * rad); us.append(i / L); phs.append(ph)
        for i in range(L):
            for s_ in range(SIDES):
                a0 = b0 + i * SIDES + s_; a1 = b0 + i * SIDES + (s_ + 1) % SIDES; faces.append((a0, a1, a1 + SIDES, a0 + SIDES))
    fme.from_pydata([tuple(v) for v in verts], [], faces); fme.update()
    fme.attributes.new("u", "FLOAT", "POINT").data.foreach_set("value", us); fme.attributes.new("ph", "FLOAT", "POINT").data.foreach_set("value", phs)
    fob = bpy.data.objects.new("Filaments", fme); sc.collection.objects.link(fob); fob.visible_shadow = False
    fm = bpy.data.materials.new("Filament"); fm.use_nodes = True; ft = fm.node_tree; ft.nodes.clear()
    fo = N(ft, "ShaderNodeOutputMaterial"); em = N(ft, "ShaderNodeEmission"); em.inputs["Color"].default_value = (*GLOW, 1)
    u_ = N(ft, "ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="u").outputs["Fac"]
    ph_ = N(ft, "ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="ph").outputs["Fac"]
    fade = math_(ft, "SUBTRACT", 1.0, math_(ft, "MULTIPLY", u_, 0.55))
    v_ = math_(ft, "FRACT", math_(ft, "SUBTRACT", u_, ph_)); d_ = math_(ft, "DIVIDE", math_(ft, "SUBTRACT", v_, 0.5), 0.07)
    pulse = math_(ft, "EXPONENT", math_(ft, "MULTIPLY", math_(ft, "MULTIPLY", d_, d_), -1.0))
    ft.links.new(math_(ft, "MULTIPLY", math_(ft, "MULTIPLY", fade, math_(ft, "ADD", 0.35, math_(ft, "MULTIPLY", pulse, 0.65))), 22.0), em.inputs["Strength"])
    ft.links.new(em.outputs[0], fo.inputs["Surface"]); fme.materials.append(fm)
    print("FILAMENTS", kept, "fibres of", len(paths), "(", len(ends), "head endpoints )", len(verts), "verts", flush=True)
    # the clip set: dark strip (asphalt) with marker lights along its edges, ground fog, moon-dark sky
    gm = bpy.data.meshes.new("Ground"); gm.from_pydata([(-300, -300, 0), (300, -300, 0), (300, 300, 0), (-300, 300, 0)], [], [(0, 1, 2, 3)])
    gob = bpy.data.objects.new("Ground", gm); sc.collection.objects.link(gob); gmat = bpy.data.materials.new("Asphalt"); gmat.use_nodes = True
    gp = gmat.node_tree.nodes["Principled BSDF"]; gp.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1); gp.inputs["Roughness"].default_value = 0.45; gm.materials.append(gmat)
    fgm = bpy.data.meshes.new("Fog"); bmf = bmesh.new(); bmesh.ops.create_cube(bmf, size=1.0); bmf.to_mesh(fgm); bmf.free()
    fog = bpy.data.objects.new("Fog", fgm); sc.collection.objects.link(fog); fog.scale = (240, 240, 24); fog.location = (0, 0, 11.9)
    fmat = bpy.data.materials.new("FogV"); fmat.use_nodes = True; fnt = fmat.node_tree; fnt.nodes.clear(); fout = N(fnt, "ShaderNodeOutputMaterial")
    fv = N(fnt, "ShaderNodeVolumePrincipled"); fv.inputs["Color"].default_value = (0.55, 0.60, 0.70, 1); fv.inputs["Anisotropy"].default_value = 0.6
    fsp = N(fnt, "ShaderNodeSeparateXYZ"); fnt.links.new(N(fnt, "ShaderNodeTexCoord").outputs["Generated"], fsp.inputs[0])
    fnt.links.new(math_(fnt, "MULTIPLY", math_(fnt, "EXPONENT", math_(fnt, "MULTIPLY", fsp.outputs["Z"], -8.0)), 0.006), fv.inputs["Density"])
    fnt.links.new(fv.outputs[0], fout.inputs["Volume"]); fgm.materials.append(fmat); fog.visible_shadow = False
    fmat.cycles.volume_step_rate = 4.0
cd = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam; cam.rotation_mode = "QUATERNION"; cd.lens = 85
rig_objs = []
def light(name, loc, aim, e, size, col=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = e; ld.size = size; ld.color = col
    if MODE == "glow": ld.shape = "DISK"                                        # round soft highlights on the glass (square ones read as panels)
    lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo); lo.location = loc; lo.rotation_mode = "QUATERNION"
    lo.rotation_quaternion = (aim - loc).to_track_quat("-Z", "Y"); rig_objs.append(lo); return lo
def backdrop(loc, aim):
    bpy.ops.mesh.primitive_plane_add(size=2.6, location=loc); bd = bpy.context.active_object; bd.rotation_mode = "QUATERNION"
    bd.rotation_quaternion = (aim - loc).to_track_quat("Z", "Y"); bm_ = bpy.data.materials.new("BD"); bm_.use_nodes = True; t = bm_.node_tree; t.nodes.clear()
    o = t.nodes.new("ShaderNodeOutputMaterial"); em = t.nodes.new("ShaderNodeEmission"); gc = t.nodes.new("ShaderNodeTexCoord"); sp = t.nodes.new("ShaderNodeSeparateXYZ")
    mr = t.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1.3; mr.inputs["From Max"].default_value = 1.3
    mr.inputs["To Min"].default_value = 0.02; mr.inputs["To Max"].default_value = 0.55; em.inputs["Color"].default_value = (0.80, 0.86, 1.0, 1)
    t.links.new(gc.outputs["Object"], sp.inputs[0]); t.links.new(sp.outputs["Y"], mr.inputs["Value"]); t.links.new(mr.outputs["Result"], em.inputs["Strength"])
    t.links.new(em.outputs[0], o.inputs["Surface"]); bd.data.materials.append(bm_); bd.visible_shadow = False; rig_objs.append(bd)
mk_mat = bpy.data.materials.new("Marker"); mk_mat.use_nodes = True; mt_ = mk_mat.node_tree; mt_.nodes.clear()
mke = N(mt_, "ShaderNodeEmission"); mke.inputs["Color"].default_value = (1.0, 0.78, 0.50, 1); mke.inputs["Strength"].default_value = 12.0
mt_.links.new(mke.outputs[0], N(mt_, "ShaderNodeOutputMaterial").inputs["Surface"])
def markers(f, aim):
    # marker lights along both edges of the strip, receding behind the subject
    fh = Vector((f.x, f.y, 0)).normalized(); rh = fh.cross(Vector((0, 0, 1))); base = Vector((aim.x, aim.y, 0.12))
    for side in (-1, 1):
        for k in range(14):
            q = base + fh * (5.0 + 5.0 * k) + rh * side * 4.0
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, location=q, segments=12, ring_count=6); o = bpy.context.active_object
            o.data.materials.append(mk_mat); o.visible_shadow = False; rig_objs.append(o)
HC = Vector((0.0, -0.02, 1.45))
VIEW = {"front": (0, 0.85, H, 85), "three_quarter": (38, 0.85, H, 85), "profile": (90, 0.85, H, 85), "eye": (22, 0.30, Vector((0.03, -0.12, 1.605)), 85),
        "chest": (32, 1.62, HC, 85)}
for vname in VIEWS:
    for ob in rig_objs: bpy.data.objects.remove(ob)
    rig_objs.clear()
    ang, dist, aim, lens = VIEW[vname]; t = math.radians(ang); cd.lens = lens
    loc = aim + Vector((math.sin(t) * dist, -math.cos(t) * dist, 0.02 * dist))
    cam.location = loc; cam.rotation_quaternion = (aim - loc).to_track_quat("-Z", "Y")
    f = (aim - loc).normalized(); r = f.cross(Vector((0, 0, 1))).normalized(); u = r.cross(f); sk = dist / 0.85
    cd.dof.use_dof = MODE == "glow"; cd.dof.focus_distance = dist; cd.dof.aperture_fstop = 2.2 * sk
    if MODE == "clay":                                                          # studio rig fixed to the camera: key upper left, soft fill right, rim behind
        light("Key", H - f * 1.1 - r * 1.0 + u * 1.15, H, 120, 0.6); light("Fill", H - f * 1.5 + r * 1.2 + u * 0.1, H, 14, 1.6)
        light("Rim", H + f * 1.1 + r * 0.7 + u * 0.9, H, 70, 0.6)
    elif MODE == "glass":                                                       # glass: soft key, cold white-blue rim from behind, a dim backdrop to refract
        light("Key", H - f * 1.1 - r * 1.0 + u * 1.15, H, 60, 0.8); light("RimC", H + f * 1.0 - r * 0.5 + u * 0.7, H, 160, 0.5, COLD)
        light("RimC2", H + f * 1.0 + r * 0.6 + u * 0.4, H, 90, 0.5, COLD); backdrop(H + f * 1.4, H - f)
    else:                                                                       # clip light: key from above-side grazing the face, cold rims from behind, faint fill
        K = aim if vname == "chest" else H
        light("Key", K - f * 0.25 * sk - r * 0.95 * sk + u * 1.0 * sk, K, 60 * sk * sk, 0.35 * sk, (0.96, 0.98, 1.0))
        light("RimC", K + f * 0.55 * sk - r * 1.05 * sk + u * 0.70 * sk, K, 330 * sk * sk, 0.35 * sk, COLD)
        light("RimC2", K + f * 0.55 * sk + r * 1.10 * sk + u * 0.30 * sk, K, 250 * sk * sk, 0.35 * sk, COLD)
        light("Fill", K - f * 2.0 * sk + r * 0.8 * sk + u * 0.6 * sk, K, 5 * sk * sk, 2.0 * sk, (0.55, 0.65, 0.9)); markers(f, aim)
    sc.render.filepath = f"{OUT}/{TAG}_{MODE}_{vname}.png"; bpy.ops.render.render(write_still=True); print("VIEW_DONE", vname, flush=True)
print("BUST_DONE", flush=True)
