"""Dome projection bake in Nuke using only 3D projection (no STMap, no expressions on pixels).

A LatLong image cannot be projected with a single Project3D: a 4x4 camera matrix is linear and the
equirectangular mapping is not. Spherical cameras in Project3D are buggy with ScanlineRender, so this
script replaces the one spherical camera with six ordinary perspective cameras (a cube rig) placed at the
position of the panorama camera.

Pipeline the script builds:

1. Sphere (native UV == LatLong) textured with the HDR, centered on the camera position.
2. Six 92-degree cameras (+-X, +-Y, +-Z) render the inside of the sphere -> six cube faces.
3. Six Project3D nodes project those faces back from the same six cameras onto the dome.
4. MergeMat (over) combines them, ApplyMaterial puts the result on the dome.
5. ScanlineRender in "uv" projection mode bakes the dome into a square UV texture -> Write EXR.

The cameras overlap by 2 degrees on each edge; the overlapping pixels are identical, so no seam.

Usage: select Camera1 (panorama camera), ReadGeo1 (dome) and the Read of the LatLong HDR, then in the
Script Editor run:

    exec(open(r"/path/to/cube_projection_bake.py").read())

Every node it creates starts with "CubeBake_". One Ctrl+Z removes them all.
"""

import math
import os

import nuke

UV_SIZE = 4096  # baked texture resolution (square)
FACE_SIZE = 2048  # resolution of each cube face (6260 px LatLong -> ~1565 px per 90 degrees)
FACE_FOV = 92.0  # degrees; >90 so neighbouring faces overlap
SPHERE_SEGMENTS = (128, 256)  # rows, columns of the LatLong sphere
PREFIX = "CubeBake_"

# name, rotate (x, y, z). Nuke cameras look down -Z; rotation is about the camera's own position.
FACES = [
    ("Front", (0.0, 0.0, 0.0)),  # -Z
    ("Back", (0.0, 180.0, 0.0)),  # +Z
    ("Left", (0.0, 90.0, 0.0)),  # -X
    ("Right", (0.0, -90.0, 0.0)),  # +X
    ("Up", (90.0, 0.0, 0.0)),  # +Y
    ("Down", (-90.0, 0.0, 0.0)),  # -Y
]


def make(classes, name, **knobs):
    """Create the first node class that exists in this Nuke version (e.g. Camera3 -> Camera2 -> Camera)."""
    for cls in classes:
        try:
            node = getattr(nuke.nodes, cls)()
        except (AttributeError, RuntimeError):
            continue
        node.setName(PREFIX + name)
        for knob, value in knobs.items():
            set_knob(node, knob, value)
        return node
    raise RuntimeError("None of these node classes exist: %s" % ", ".join(classes))


def set_knob(node, knob, value):
    if knob not in node.knobs():
        print("WARNING: %s has no knob '%s', set it by hand" % (node.name(), knob))
        return
    try:
        node[knob].setValue(value)
    except (TypeError, ValueError) as error:
        print("WARNING: %s.%s = %r failed (%s), set it by hand" % (node.name(), knob, value, error))


def connect(node, labels, source):
    """Connect `source` to the input whose label is in `labels` ('' means the unlabelled input)."""
    for i in range(node.maxInputs()):
        if node.inputLabel(i) in labels:
            node.setInput(i, source)
            return
    print("WARNING: %s has no input %s, connect it by hand" % (node.name(), " / ".join(repr(x) for x in labels)))


def format_named(name, size):
    if name not in [f.name() for f in nuke.formats()]:
        nuke.addFormat("%d %d 1.0 %s" % (size, size, name))
    return name


def link_to_camera_position(node, camera):
    """Drive translate from the panorama camera's world position (works even if it is parented in an FBX)."""
    for channel, index in enumerate((3, 7, 11)):
        node["translate"].setExpression("%s.world_matrix.%d" % (camera.name(), index), channel)


def place(node, x, y):
    node.setXYpos(int(x), int(y))


def pick_selection():
    camera = geo = image = None
    for node in nuke.selectedNodes():
        cls = node.Class()
        if cls.startswith("Camera"):
            camera = node
        elif cls.startswith("ReadGeo"):
            geo = node
        elif cls == "Read":
            image = node
    missing = [label for label, node in (("Camera", camera), ("ReadGeo", geo), ("Read (LatLong HDR)", image)) if node is None]
    if missing:
        raise RuntimeError("Select the panorama camera, the dome ReadGeo and the LatLong Read. Missing: " + ", ".join(missing))
    return camera, geo, image


def build():
    camera, geo, image = pick_selection()
    x0 = max(n.xpos() for n in (camera, geo, image)) + 300
    y0 = min(n.ypos() for n in (camera, geo, image))

    face_format = format_named("CubeBake_Face_%d" % FACE_SIZE, FACE_SIZE)
    uv_format = format_named("CubeBake_UV_%d" % UV_SIZE, UV_SIZE)

    # Heading / mirror controls, same meaning as the old LatLongUV knobs.
    controls = make(["NoOp"], "Controls")
    tab = nuke.Tab_Knob("cubebake", "Cube Bake")
    heading = nuke.Double_Knob("heading", "heading (deg)")
    heading.setRange(-180, 180)
    mirror = nuke.Boolean_Knob("mirror", "mirror horizontally")
    mirror.setFlag(nuke.STARTLINE)
    for knob in (tab, heading, mirror):
        controls.addKnob(knob)
    mirror.setValue(True)  # a LatLong seen from inside a Nuke Sphere reads mirrored
    place(controls, x0, y0 - 150)

    # 1. LatLong sphere around the camera position. Only the face renders see it, never the dome render.
    sphere = make(["Sphere"], "LatLongSphere", rows=SPHERE_SEGMENTS[0], columns=SPHERE_SEGMENTS[1], radius=1.0)
    sphere.setInput(0, image)
    link_to_camera_position(sphere, camera)
    sphere["rotate"].setExpression("%s.heading" % controls.name(), 1)
    sphere["scaling"].setExpression("%s.mirror ? -1 : 1" % controls.name(), 0)
    place(sphere, x0, y0)

    face_bg = make(["Constant"], "FaceBG", channels="rgba", format=face_format)
    place(face_bg, x0 + 150, y0)
    uv_bg = make(["Constant"], "UVBG", channels="rgba", format=uv_format)

    # Focal for the chosen FOV on a square 24.576 mm film back.
    aperture = 24.576
    focal = aperture / 2.0 / math.tan(math.radians(FACE_FOV) / 2.0)

    material = None
    for i, (face, rotate) in enumerate(FACES):
        x = x0 + i * 150
        cam = make(
            ["Camera3", "Camera2", "Camera"],
            "Cam" + face,
            focal=focal,
            haperture=aperture,
            vaperture=aperture,
            near=0.01,
            far=1.0e8,
        )
        link_to_camera_position(cam, camera)
        cam["rotate"].setValue(list(rotate))
        place(cam, x, y0 + 120)

        # 2. Render the cube face from inside the sphere.
        render = make(["ScanlineRender"], "Render" + face, projection_mode="render camera")
        connect(render, ("bg",), face_bg)
        connect(render, ("obj/scn",), sphere)
        connect(render, ("cam",), cam)
        place(render, x, y0 + 240)

        # 3. Project the face back from the same camera onto the dome.
        project = make(["Project3D2", "Project3D"], "Project" + face, crop=True, project_on="both", occlusion_mode="none")
        connect(project, ("img", ""), render)
        connect(project, ("cam",), cam)
        place(project, x, y0 + 360)

        # 4. Stack the six projections.
        if material is None:
            material = project
        else:
            merge = make(["MergeMat"], "Merge" + face, operation="over")
            connect(merge, ("A",), project)
            connect(merge, ("B",), material)
            place(merge, x, y0 + 480)
            material = merge

    apply_material = make(["ApplyMaterial"], "ApplyMaterial")
    connect(apply_material, ("", "geo"), geo)
    connect(apply_material, ("mat",), material)
    place(apply_material, x0 + 750, y0 + 600)

    # 5. Bake to UV.
    place(uv_bg, x0 + 600, y0 + 720)
    bake = make(["ScanlineRender"], "UVBake", projection_mode="uv")
    connect(bake, ("bg",), uv_bg)
    connect(bake, ("obj/scn",), apply_material)
    connect(bake, ("cam",), camera)
    place(bake, x0 + 750, y0 + 720)

    out_dir = os.path.dirname(image["file"].value()) or os.getcwd()
    write = make(
        ["Write"],
        "Write",
        file=os.path.join(out_dir, "dome_uv_bake.exr").replace("\\", "/"),
        file_type="exr",
        channels="rgba",
    )
    set_knob(write, "datatype", "32 bit float")
    set_knob(write, "colorspace", image["colorspace"].value() if "colorspace" in image.knobs() else "linear")
    write.setInput(0, bake)
    place(write, x0 + 750, y0 + 840)

    print("Built. Render %s; preview the live projection by viewing %s in the 3D viewer." % (write.name(), apply_material.name()))


nuke.Undo.begin("Cube Projection Bake")
try:
    build()
finally:
    nuke.Undo.end()
