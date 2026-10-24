"""Wheels: treaded tyre (11 cm sidewall), concave spoked rim with polished lip, brake disc + hat, caliper.
Wheel space: X = axle (outboard +X), Y fwd, Z up."""
import bpy, bmesh, math
from mathutils import Vector
import materials as M

R_TYRE, R_RIM = 0.35, 0.240

def revolve(bm, prof, seg, closed_profile=False, disp=None):
    """prof: list of (u, r); revolve around X. disp(u, phi, r) -> r"""
    rows = []
    for k in range(seg):
        phi = 2 * math.pi * k / seg; c, s = math.cos(phi), math.sin(phi)
        row = []
        for (u, r) in prof:
            rr = disp(u, phi, r) if disp else r
            row.append(bm.verts.new((u, rr * c, rr * s)))
        rows.append(row)
    n = len(prof)
    for k in range(seg):
        a, b = rows[k], rows[(k + 1) % seg]
        for i in range(n if closed_profile else n - 1):
            i2 = (i + 1) % n
            bm.faces.new((a[i], a[i2], b[i2], b[i]))
    return rows

def tyre_profile(W):
    h = W / 2
    p = [(-h + 0.014, R_RIM), (-h + 0.001, R_RIM + 0.012), (-h - 0.005, R_RIM + 0.040), (-h - 0.007, R_RIM + 0.065),
         (-h - 0.003, 0.322), (-h + 0.008, 0.340), (-h + 0.022, R_TYRE)]
    tread = [(-h + 0.022 + (W - 0.044) * i / 39, R_TYRE) for i in range(1, 39)]
    right = [(-u, r) for (u, r) in reversed(p)]
    return p + tread + right

def tread_disp(W):
    h = W / 2; grooves = (-0.3 * W, 0.0, 0.3 * W); NB = 48
    def f(u, phi, r):
        if r < R_TYRE - 1e-4 or abs(u) > h - 0.02: return r
        g = max(max(0.0, 1 - abs(u - c) / 0.007) for c in grooves)
        if abs(u) > 0.06 * W:
            ph = phi * NB / (2 * math.pi) + 2.2 * abs(u) / W
            fr = ph - math.floor(ph); g = max(g, max(0.0, 1 - abs(fr - 0.5) / 0.09))
        return r - 0.008 * min(1.0, g * 1.6)
    return f

def mesh_obj(name, bm, mats, coll, parent=None, smooth=True, sharp=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.normal_update(); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    if smooth: me.shade_smooth()
    if sharp: me.set_sharp_from_angle(angle=math.radians(sharp))
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    if parent: ob.parent = parent
    return ob

def spoke(bm, a_in, a_out, u_in, u_out, w_in, w_out, t_in, t_out, r0=0.085, r1=0.222):
    secs = []
    for k in range(6):
        s = k / 5; r = r0 + (r1 - r0) * s; ang = a_in + (a_out - a_in) * s
        u = u_in + (u_out - u_in) * (s ** 0.7); w = w_in + (w_out - w_in) * s; t = t_in + (t_out - t_in) * s
        c, sn = math.cos(ang), math.sin(ang); radial = Vector((0, c, sn)); tang = Vector((0, -sn, c))
        base = Vector((u, 0, 0)) + radial * r
        secs.append([bm.verts.new(base + tang * dw + Vector((du, 0, 0))) for dw, du in ((-w / 2, t / 2), (w / 2, t / 2), (w / 2, -t / 2), (-w / 2, -t / 2))])
    for a, b in zip(secs, secs[1:]):
        for i in range(4): bm.faces.new((a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i]))
    bm.faces.new(secs[0][::-1]); bm.faces.new(secs[-1])

def _axial(bm, res, du):
    for v in res["verts"]: x, y, z = v.co; v.co = Vector((z + du, y, x))

def build_wheel(name, W, coll, parent):
    hub = bpy.data.objects.new(name + "_Hub", None); coll.objects.link(hub); hub.parent = parent
    spin = bpy.data.objects.new(name + "_Spin", None); coll.objects.link(spin); spin.parent = hub
    h = W / 2
    # tyre: near-black rubber, visible 11 cm sidewall
    bm = bmesh.new(); revolve(bm, tyre_profile(W), 720, disp=tread_disp(W))
    mesh_obj(name + "_Tyre", bm, [M.rubber()], coll, spin)
    # rim barrel + inner flange (graphite)
    bm = bmesh.new()
    revolve(bm, [(-h + 0.01, 0.224), (h - 0.03, 0.224), (h - 0.03, 0.218), (-h + 0.01, 0.218)], 128, closed_profile=True)
    revolve(bm, [(-h + 0.004, 0.222), (-h + 0.004, 0.244), (-h + 0.014, 0.244), (-h + 0.014, 0.222)], 128, closed_profile=True)
    # 5 twin spokes, concave: 5 cm deeper at the hub than at the lip
    for k in range(5):
        base = 2 * math.pi * k / 5
        for sgn in (-1, 1):
            spoke(bm, base + sgn * math.radians(3.5), base + sgn * math.radians(8.5), h - 0.075, h - 0.026, 0.036, 0.022, 0.034, 0.018)
    _axial(bm, bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.094, radius2=0.090, depth=0.036), h - 0.078)
    _axial(bm, bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.030, radius2=0.026, depth=0.016), h - 0.054)
    rim = mesh_obj(name + "_Rim", bm, [M.rim_metal()], coll, spin, sharp=40)
    bv = rim.modifiers.new("Bevel", "BEVEL"); bv.width = 0.003; bv.segments = 2; bv.limit_method = "ANGLE"; bv.angle_limit = math.radians(35)
    # polished outer lip
    bm = bmesh.new()
    revolve(bm, [(h - 0.035, 0.219), (h - 0.012, 0.226), (h - 0.006, 0.243), (h - 0.014, 0.247), (h - 0.03, 0.238), (h - 0.035, 0.226)], 160, closed_profile=True)
    mesh_obj(name + "_RimLip", bm, [M.rim_lip()], coll, spin)
    # lug nuts
    bm = bmesh.new()
    for k in range(5):
        a = 2 * math.pi * (k + 0.5) / 5
        nut = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.011, radius2=0.011, depth=0.02)
        for v in nut["verts"]: x, y, z = v.co; v.co = Vector((z + h - 0.052, y + 0.058 * math.cos(a), x + 0.058 * math.sin(a)))
    mesh_obj(name + "_Nuts", bm, [M.chrome()], coll, spin, smooth=False)
    # brake disc + hat (spins), visible between the spokes
    bm = bmesh.new()
    revolve(bm, [(-0.036, 0.105), (-0.004, 0.105), (-0.004, 0.190), (-0.036, 0.190)], 96, closed_profile=True)
    revolve(bm, [(-0.012, 0.096), (h - 0.094, 0.096), (h - 0.094, 0.103), (-0.012, 0.103)], 64, closed_profile=True)
    mesh_obj(name + "_Disc", bm, [M.disc_metal()], coll, spin, sharp=40)
    # caliper (fixed to the hub, does not spin)
    bm = bmesh.new(); secs = []
    for k in range(9):
        a = math.radians(100 + 55 * k / 8); c, s = math.cos(a), math.sin(a)
        secs.append([bm.verts.new((u, r * c, r * s)) for (u, r) in ((-0.066, 0.122), (0.024, 0.122), (0.024, 0.206), (-0.066, 0.206))])
    for a_, b_ in zip(secs, secs[1:]):
        for i in range(4): bm.faces.new((a_[i], a_[(i + 1) % 4], b_[(i + 1) % 4], b_[i]))
    bm.faces.new(secs[0][::-1]); bm.faces.new(secs[-1])
    cal = mesh_obj(name + "_Caliper", bm, [M.caliper()], coll, hub, sharp=40)
    bv = cal.modifiers.new("Bevel", "BEVEL"); bv.width = 0.008; bv.segments = 3
    return hub, spin
