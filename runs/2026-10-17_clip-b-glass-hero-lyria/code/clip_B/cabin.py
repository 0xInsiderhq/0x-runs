"""clip_B cabin: see-through tinted windows, dark interior (back faces of the skin, tub, single central seat, dash, steering wheel).
Works on the stunt_v2 scene (stunt.blend) without touching the stunt files."""
import bpy, bmesh, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

def _mat(name, col, rough=0.6, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*col, 1); p.inputs["Roughness"].default_value = rough; p.inputs["Metallic"].default_value = metal
    return m

def tint_glass():
    m = bpy.data.materials.new("TintGlass"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); tr = nt.nodes.new("ShaderNodeBsdfTransparent"); tr.inputs["Color"].default_value = (0.50, 0.52, 0.55, 1)   # ~50 % tint
    gl = nt.nodes.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.02; gl.inputs["Color"].default_value = (0.9, 0.93, 0.96, 1)
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.12
    mx = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(lw.outputs["Fresnel"], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(gl.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], o.inputs["Surface"]); return m

def _box(bm, c, s, M=None):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]:
        v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2])) + Vector(c)
        if M is not None: v.co = M @ v.co
    return r

def _ob(name, bm, mat, parent, coll, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    me.materials.append(mat); ob = bpy.data.objects.new(name, me); coll.objects.link(ob); ob.parent = parent; return ob

def build_cabin(coll, seat):
    """seat: rig-space hips (posed hips bone head), knees, cushion top z_c, recline (deg), hero scale. Sports-car seat + wheel + dash"""
    body, glass = bpy.data.objects["Body"], bpy.data.objects["Glass"]; rig = body.parent
    opening = bpy.data.materials.new("CabinOpening"); opening.use_nodes = True; nt = opening.node_tree; nt.nodes.clear()
    nt.links.new(nt.nodes.new("ShaderNodeBsdfTransparent").outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    body.material_slots[1].link = "OBJECT"; body.material_slots[1].material = opening            # only the body's window panels open up
    glass.material_slots[0].link = "OBJECT"; glass.material_slots[0].material = tint_glass()
    paint = body.material_slots[0].material; nt = paint.node_tree                                  # inside of the skin is dark trim, not white paint
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"); src = out.inputs["Surface"].links[0].from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry"); dark = nt.nodes.new("ShaderNodeBsdfPrincipled")
    dark.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1); dark.inputs["Roughness"].default_value = 0.7
    mx = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(geo.outputs["Backfacing"], mx.inputs[0]); nt.links.new(src, mx.inputs[1]); nt.links.new(dark.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    ML = body.matrix_local; me = body.data
    wv = [ML @ me.vertices[i].co for p in me.polygons if p.material_index == 1 for i in p.vertices]
    cab = dict(y=(min(v.y for v in wv), max(v.y for v in wv)))
    trim = _mat("CabinTrim", (0.02, 0.02, 0.022), 0.55); seat_m = _mat("SeatLeather", (0.045, 0.04, 0.038), 0.45)
    hp, kn, z_c, rc, sc = Vector(seat["hips"]), Vector(seat["knee"]), seat["z_c"], math.radians(seat["recline"]), seat["scale"]
    bm = bmesh.new(); yc = 0.5 * (cab["y"][0] + cab["y"][1]); _box(bm, (0, yc, 0.07), (1.30, cab["y"][1] - cab["y"][0] + 0.6, 0.104)); floor = _ob("CabinTub", bm, trim, rig, coll)
    bm = bmesh.new(); _box(bm, (0, hp.y + 0.05, 0.5 * (0.12 + z_c)), (0.52, 0.50, max(z_c - 0.12, 0.012) + 0.004))
    off = (0.15 + 0.11 * math.sin(rc)) / math.cos(rc) * sc                                      # backrest front face touches the back
    rec = Matrix.Translation((0, hp.y - off, z_c)) @ Matrix.Rotation(rc, 4, "X") @ Matrix.Translation((0, 0, 0.36))
    _box(bm, (0, 0, 0), (0.50, 0.10, 0.74), rec); seat_ob = _ob("CabinSeat", bm, seat_m, rig, coll)
    wc = Vector((0, kn.y + 0.13, kn.z + 0.25)); tilt = math.radians(-20); nrm = Vector((0, math.cos(tilt), math.sin(tilt)))   # wheel above the knees, top leans forward
    bm = bmesh.new(); y_dash = kn.y + 0.42; _box(bm, (0, y_dash, 0.53), (1.25, 0.30, 0.22)); dash = _ob("CabinDash", bm, trim, rig, coll)
    bm = bmesh.new()
    for k in range(40):                                                               # torus rim
        a0, a1 = 2 * math.pi * k / 40, 2 * math.pi * (k + 1) / 40
        c = bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=0.016, radius2=0.016, depth=0.16 * (a1 - a0) * 1.04)
        Mk = Matrix.Rotation((a0 + a1) / 2, 4, "Y") @ Matrix.Translation((0.16, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X")
        bmesh.ops.transform(bm, matrix=Mk, verts=c["verts"])
    for a in (0.0, 2.2, 4.1):                                                          # three spokes + hub
        c = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.012, radius2=0.012, depth=0.15)
        bmesh.ops.transform(bm, matrix=Matrix.Rotation(a, 4, "Y") @ Matrix.Translation((0.075, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Y"), verts=c["verts"])
    c = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.035, radius2=0.035, depth=0.04); bmesh.ops.transform(bm, matrix=Matrix.Rotation(math.pi / 2, 4, "X"), verts=c["verts"])
    col_len = max(0.05, (y_dash - 0.15 - wc.y) / max(nrm.y, 0.3))                       # steering column from the hub into the dash
    c = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.022, radius2=0.022, depth=col_len)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0, col_len / 2, 0)) @ Matrix.Rotation(-math.pi / 2, 4, "X"), verts=c["verts"])
    wheel = _ob("SteeringWheel", bm, _mat("WheelGrip", (0.03, 0.03, 0.032), 0.5), rig, coll, smooth=True)
    wheel.location = wc; wheel.rotation_mode = "XYZ"; wheel.rotation_euler = (tilt, 0, 0)
    for ob in (floor, seat_ob, dash, wheel): ob.visible_shadow = True
    print("cabin:", dict(window_y=tuple(round(x, 3) for x in cab["y"]), cushion=round(z_c, 3), hips=tuple(round(x, 3) for x in hp), wheel=tuple(round(x, 3) for x in wc), dash_y=round(y_dash, 3)), flush=True)
    return dict(wheel=wheel, rig=rig)
