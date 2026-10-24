"""Procedural materials (no image textures)."""
import bpy

def new(name):
    m = bpy.data.materials.get(name)
    if m: return m, None
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    return m, nt

def N(nt, typ, **props):
    n = nt.nodes.new(typ)
    for k, v in props.items(): setattr(n, k, v)
    return n

def S(nt, sock, val):
    """connect an output socket or set a default value"""
    if hasattr(val, "is_output"): nt.links.new(val, sock)
    else: sock.default_value = val

def P(nt, n, **inputs):
    for k, v in inputs.items(): S(nt, n.inputs[k.replace("_", " ")], v)
    return n

def mix(nt, fac, a, b, kind="RGBA"):
    m = N(nt, "ShaderNodeMix", data_type=kind)
    S(nt, m.inputs[0], fac)
    ins = [s for s in m.inputs if s.type == ("RGBA" if kind == "RGBA" else "VALUE") and s.name in ("A", "B")]
    S(nt, ins[0], a); S(nt, ins[1], b)
    return [s for s in m.outputs if s.type == ("RGBA" if kind == "RGBA" else "VALUE")][0]

def math(nt, op, a, b=0.0, clamp=False):
    m = N(nt, "ShaderNodeMath", operation=op, use_clamp=clamp)
    S(nt, m.inputs[0], a); S(nt, m.inputs[1], b); return m.outputs[0]

def vmath(nt, op, a, b=(0, 0, 0), scale=None):
    m = N(nt, "ShaderNodeVectorMath", operation=op)
    S(nt, m.inputs[0], a); S(nt, m.inputs[1], b)
    if scale is not None: m.inputs["Scale"].default_value = scale
    return m.outputs["Value" if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else "Vector"]

def maprange(nt, val, a, b, c, d, clamp=True):
    m = N(nt, "ShaderNodeMapRange", clamp=clamp)
    S(nt, m.inputs["Value"], val)
    for k, v in zip(("From Min", "From Max", "To Min", "To Max"), (a, b, c, d)): m.inputs[k].default_value = v
    return m.outputs["Result"]

def noise(nt, vec, scale, detail=4.0, rough=0.5, dims="3D", w=None):
    n = N(nt, "ShaderNodeTexNoise", noise_dimensions=dims)
    S(nt, n.inputs["Vector"], vec); n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail; n.inputs["Roughness"].default_value = rough
    if w is not None: S(nt, n.inputs["W"], w)
    return n

def coords(nt, kind="Object"):
    return N(nt, "ShaderNodeTexCoord").outputs[kind]

def out(nt, shader, volume=None):
    o = N(nt, "ShaderNodeOutputMaterial")
    if shader is not None: nt.links.new(shader, o.inputs["Surface"])
    if volume is not None: nt.links.new(volume, o.inputs["Volume"])
    return o

def principled(nt, **kw):
    p = N(nt, "ShaderNodeBsdfPrincipled")
    return P(nt, p, **kw)

def bump(nt, height, strength, distance=0.01, normal=None):
    b = N(nt, "ShaderNodeBump"); S(nt, b.inputs["Height"], height)
    b.inputs["Strength"].default_value = strength; b.inputs["Distance"].default_value = distance
    if normal is not None: S(nt, b.inputs["Normal"], normal)
    return b.outputs["Normal"]

def zmask(nt, z0, z1):
    """1 below z0 fading to 0 at z1 (object space)"""
    sep = N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(coords(nt), sep.inputs[0])
    return maprange(nt, sep.outputs["Z"], z0, z1, 1.0, 0.0)

# ---------------- car materials ----------------
def car_paint():
    """glossy white enamel under clear coat (coat 1.0, coat roughness 0.03), faint flake, light dust at the sills"""
    m, nt = new("CarPaint")
    if not nt: return m
    co = coords(nt)
    vor = N(nt, "ShaderNodeTexVoronoi"); nt.links.new(co, vor.inputs["Vector"]); vor.inputs["Scale"].default_value = 900
    flake = vmath(nt, "SCALE", vmath(nt, "SUBTRACT", vor.outputs["Color"], (0.5, 0.5, 0.5)), scale=0.05)
    geo = N(nt, "ShaderNodeNewGeometry")
    fn = vmath(nt, "NORMALIZE", vmath(nt, "ADD", geo.outputs["Normal"], flake))
    dust_n = noise(nt, co, 7.0, 8.0, 0.6)
    dust = math(nt, "MULTIPLY", zmask(nt, 0.13, 0.26), maprange(nt, dust_n.outputs["Fac"], 0.4, 0.7, 0.0, 0.5), clamp=True)
    col = mix(nt, dust, (0.90, 0.905, 0.91, 1), (0.45, 0.42, 0.38, 1))
    rough = mix(nt, dust, 0.22, 0.7, "FLOAT"); coat = mix(nt, dust, 1.0, 0.7, "FLOAT")
    p = principled(nt, Base_Color=col, Metallic=0.05, Roughness=rough, Normal=fn, Coat_Weight=coat,
                   Coat_Roughness=0.03, Coat_IOR=1.5)
    p.inputs["Specular IOR Level"].default_value = 0.5
    out(nt, p.outputs[0]); return m

def simple(name, color, rough, metallic=0.0, coat=0.0, bump_scale=None, bump_str=0.0, aniso=0.0):
    m, nt = new(name)
    if not nt: return m
    kw = dict(Base_Color=(*color, 1), Roughness=rough, Metallic=metallic, Coat_Weight=coat, Coat_Roughness=0.04)
    if bump_scale:
        kw["Normal"] = bump(nt, noise(nt, coords(nt), bump_scale, 6.0, 0.6).outputs["Fac"], bump_str, 0.002)
    p = principled(nt, **kw)
    if aniso:
        p.inputs["Anisotropic"].default_value = aniso
        tg = N(nt, "ShaderNodeTangent", direction_type="RADIAL", axis="X"); nt.links.new(tg.outputs[0], p.inputs["Tangent"])
    out(nt, p.outputs[0]); return m

def window_back(): return simple("WindowBack", (0.008, 0.008, 0.009), 0.12, coat=1.0)
def trim_black(): return simple("TrimBlack", (0.014, 0.014, 0.015), 0.45, bump_scale=400, bump_str=0.05)
def liner(): return simple("Liner", (0.008, 0.008, 0.008), 0.9, bump_scale=120, bump_str=0.2)
def intake_inner(): return simple("IntakeInner", (0.035, 0.035, 0.038), 0.45, metallic=0.3, bump_scale=300, bump_str=0.05)
def intake_fin(): return simple("IntakeFin", (0.10, 0.10, 0.105), 0.32, metallic=0.8, coat=0.5)
def nozzle_metal(): return simple("NozzleMetal", (0.30, 0.30, 0.32), 0.3, metallic=1.0)
def rim_metal(): return simple("RimGraphite", (0.055, 0.055, 0.06), 0.24, metallic=1.0, coat=0.8)
def rim_lip(): return simple("RimLipPolished", (0.80, 0.80, 0.81), 0.07, metallic=1.0)
def disc_metal(): return simple("BrakeDisc", (0.50, 0.50, 0.50), 0.30, metallic=1.0, aniso=0.7)
def caliper(): return simple("Caliper", (0.58, 0.58, 0.60), 0.33, metallic=1.0)
def chrome(): return simple("Chrome", (0.85, 0.85, 0.85), 0.04, metallic=1.0)

def underbody():
    m, nt = new("Underbody")
    if not nt: return m
    n = noise(nt, coords(nt), 5.0, 6.0, 0.6)
    col = mix(nt, n.outputs["Fac"], (0.02, 0.02, 0.02, 1), (0.22, 0.2, 0.18, 1))
    out(nt, principled(nt, Base_Color=col, Roughness=0.8).outputs[0]); return m

def rubber():
    """near-black rubber with micro relief, faint dust"""
    m, nt = new("Rubber")
    if not nt: return m
    co = coords(nt)
    micro = noise(nt, co, 900.0, 3.0, 0.5)
    dustn = noise(nt, co, 9.0, 6.0, 0.6)
    col = mix(nt, maprange(nt, dustn.outputs["Fac"], 0.45, 0.75, 0.0, 0.5), (0.014, 0.014, 0.014, 1), (0.06, 0.056, 0.052, 1))
    p = principled(nt, Base_Color=col, Roughness=0.78, Normal=bump(nt, micro.outputs["Fac"], 0.25, 0.0015))
    out(nt, p.outputs[0]); return m

def glass(name, tint, rough=0.0):
    m, nt = new(name)
    if not nt: return m
    p = principled(nt, Base_Color=(*tint, 1), Roughness=rough, IOR=1.5, Transmission_Weight=1.0)
    out(nt, p.outputs[0]); return m

def emission(name, color, strength):
    m, nt = new(name)
    if not nt: return m
    e = N(nt, "ShaderNodeEmission"); e.inputs["Color"].default_value = (*color, 1); e.inputs["Strength"].default_value = strength
    out(nt, e.outputs[0]); return m
