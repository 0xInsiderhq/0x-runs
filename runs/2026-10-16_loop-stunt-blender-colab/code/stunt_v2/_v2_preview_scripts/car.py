"""Car assembly: body, glass, LED lamps, tail bar, intake fins, mirrors, diffuser, nozzles, wheels, lights."""
import bpy, bmesh, math
from mathutils import Vector
import materials as M, car_body as CB, car_wheels as CW

def _obj(name, bm, mats, coll, parent, smooth=True, sharp=None):
    return CW.mesh_obj(name, bm, mats, coll, parent, smooth, sharp)

def patch(bvh, x0, x1, y0, y1, nx, ny, off):
    """grid sampled on the body top surface, offset along the surface normal"""
    bm = bmesh.new(); grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx; y = y0 + (y1 - y0) * j / ny
            hit, n, idx, dist = bvh.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))
            if hit is None: hit, n = Vector((x, y, 0.3)), Vector((0, 0, 1))
            row.append(bm.verts.new(hit + n * off))
        grid.append(row)
    for j in range(ny):
        for i in range(nx): bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    return bm

def solid(ob, t, offset=1.0):
    s = ob.modifiers.new("Thick", "SOLIDIFY"); s.thickness = t; s.offset = offset
    CB.bake(ob); ob.data.shade_smooth()

def build_car(coll):
    root = bpy.data.objects.new("CarRoot", None); coll.objects.link(root)
    rig = bpy.data.objects.new("CarBodyRig", None); coll.objects.link(rig); rig.parent = root
    bpc = bpy.data.collections.new("Blueprint"); coll.children.link(bpc)
    CB.blueprint(bpc)
    body, glass, bvh = CB.build_body(coll)
    body.parent = rig; glass.parent = rig
    led = M.emission("HeadLED", (0.92, 0.96, 1.0), 60.0)
    tail = M.emission("TailLED", (1.0, 0.025, 0.01), 14.0)
    # headlamps: narrow slits on the bonnet with a thin LED line inside
    for s in (1, -1):
        xa, xb = (0.36, 0.80) if s > 0 else (-0.80, -0.36)
        _obj("LampHousing", patch(bvh, xa, xb, 1.94, 2.02, 20, 4, 0.0015), [M.window_back()], coll, rig)
        _obj("LampLED", patch(bvh, xa + 0.01 * s, xb - 0.01 * s, 1.975, 1.988, 20, 1, 0.003), [led], coll, rig)
        lens = _obj("LampLens", patch(bvh, xa, xb, 1.94, 2.02, 20, 4, 0.0032), [M.glass("LampGlass", (0.97, 0.98, 1.0))], coll, rig)
        solid(lens, 0.0022)
    # full-width LED line across the nose face
    hit, n, i, d = bvh.ray_cast(Vector((0, 4.0, 0.30)), Vector((0, -1, 0)))
    yn = hit.y if hit else 2.15
    bm = bmesh.new(); CB.box(bm, (0, yn + 0.002, 0.302), (1.36, 0.008, 0.024), bevel=0.003)
    _obj("NoseBarHousing", bm, [M.window_back()], coll, rig, sharp=40)
    bm = bmesh.new(); CB.box(bm, (0, yn + 0.006, 0.302), (1.30, 0.004, 0.008), bevel=0.0015)
    _obj("NoseBarLED", bm, [led], coll, rig, smooth=False)
    # tail light bar on the low sloping tail
    hit, n, i, d = bvh.ray_cast(Vector((0, -4, 0.62)), Vector((0, 1, 0)))
    yt = hit.y if hit else -2.15
    for name, size, dy, mat in (("TailHousing", (1.58, 0.012, 0.045), -0.004, M.window_back()),
                                ("TailBar", (1.52, 0.004, 0.014), -0.011, tail),
                                ("TailLens", (1.56, 0.006, 0.026), -0.015, M.glass("TailGlass", (0.85, 0.06, 0.05)))):
        bm = bmesh.new(); CB.box(bm, (0, yt + dy, 0.62), size, bevel=min(size) * 0.3)
        _obj(name, bm, [mat], coll, rig, sharp=40)
    # diffuser: low panel on the tail + fins under it
    bm = bmesh.new(); CB.box(bm, (0, yt - 0.002, 0.36), (1.40, 0.012, 0.07), bevel=0.004)
    for k in range(5): CB.box(bm, (-0.5 + 0.25 * k, -1.99, 0.185), (0.008, 0.34, 0.10), bevel=0.002)
    _obj("Diffuser", bm, [M.trim_black()], coll, rig, smooth=False)
    # side intakes: ribs inside the recessed scoop
    bm = bmesh.new()
    for s in (1, -1):
        for y in (-0.84, -0.91, -0.98, -1.04):
            zb = 0.52 + 0.18 * (-0.76 - y) / 0.30 + 0.02; zt = 0.835
            xi = CB.intake_x_in(y); xo = 0.932
            CB.box(bm, (s * (xi + xo) / 2, y, (zb + zt) / 2), (xo - xi, 0.006, zt - zb), bevel=0.0015)
    _obj("IntakeRibs", bm, [M.intake_fin()], coll, rig, sharp=40)
    # mirrors
    for s in (1, -1):
        bm = bmesh.new(); z0 = CB.F("z_belt", 0.52) + 0.04
        CB.box(bm, (s * 0.99, 0.50, z0 - 0.015), (0.10, 0.03, 0.018), bevel=0.006)
        sp = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0)
        for v in sp["verts"]: v.co = Vector((v.co.x * 0.085 + s * 1.05, v.co.y * 0.05 + 0.50, v.co.z * 0.035 + z0))
        _obj("Mirror", bm, [M.car_paint()], coll, rig)
        bm = bmesh.new(); CB.box(bm, (s * 1.05, 0.452, z0), (0.15, 0.004, 0.055), bevel=0.0015)
        _obj("MirrorGlass", bm, [M.chrome()], coll, rig, smooth=False)
    # thruster nozzles (pushed out of the sill so they read)
    import traj
    for k, p in traj.NOZZLES.items():
        bm = bmesh.new(); s = 1 if p[0] > 0 else -1
        for rr, dep, off in ((0.032, 0.05, 0.02), (0.022, 0.06, 0.028)):
            c = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=rr, radius2=rr, depth=dep)
            for v in c["verts"]: x, y, z = v.co; v.co = Vector((s * (z + off) + p[0], y + p[1], x + p[2]))
        _obj("Nozzle_" + k, bm, [M.nozzle_metal()], coll, rig, sharp=40)
    # wheels
    wheels = {}
    for key, (x, y) in CB.WHEELS.items():
        W = 0.255 if key[0] == "F" else 0.305
        hub, spin = CW.build_wheel("W" + key, W, coll, root)
        hub.location = (x, y, CW.R_TYRE)
        if x < 0: hub.scale = (-1, 1, 1)
        wheels[key] = (hub, spin)
    # lights
    lights = []
    for s in (1, -1):
        ld = bpy.data.lights.new("Headlight", "SPOT"); ld.energy = 1800; ld.spot_size = math.radians(42); ld.spot_blend = 0.35
        ld.shadow_soft_size = 0.04; ld.color = (0.9, 0.95, 1.0)
        lo = bpy.data.objects.new("Headlight", ld); coll.objects.link(lo); lo.parent = rig
        lo.location = (s * 0.58, 2.06, 0.38); lo.rotation_euler = (math.radians(86.5), 0, 0); lights.append(lo)
    ld = bpy.data.lights.new("TailGlow", "AREA"); ld.energy = 3; ld.shape = "RECTANGLE"; ld.size = 1.4; ld.size_y = 0.04; ld.color = (1, 0.05, 0.02)
    lo = bpy.data.objects.new("TailGlow", ld); coll.objects.link(lo); lo.parent = rig; lo.visible_camera = False
    lo.location = (0, yt - 0.06, 0.62); lo.rotation_euler = (math.radians(-90), 0, 0); lights.append(lo)
    return dict(root=root, rig=rig, body=body, glass=glass, wheels=wheels, lights=lights)
