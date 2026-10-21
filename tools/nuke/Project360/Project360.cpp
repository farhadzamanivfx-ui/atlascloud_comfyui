// Project360: spherical (LatLong) projection material for Nuke's classic 3D system.
//
// Works like the spherical / environment projection in 3D packages: for every shaded point P the
// direction from the projector, d = inverse(projector world matrix) * P, is turned into LatLong
// (u, v) and the image is sampled there. Nothing goes through a 4x4 projection matrix, so it has
// none of Project3D's spherical-camera problems (blue dome, cropped half, back points ignored).
//
// Inputs:  img  - LatLong image (2:1)
//          cam  - any Camera or Axis; only its world transform is used (position, optionally rotation)
// Output:  a material. Plug it into a geometry's img input or an ApplyMaterial, then render with
//          ScanlineRender (render camera for a view, projection mode "uv" to bake into UV space).

#include "DDImage/AxisOp.h"
#include "DDImage/Filter.h"
#include "DDImage/Iop.h"
#include "DDImage/Knobs.h"
#include "DDImage/Material.h"
#include "DDImage/Matrix4.h"
#include "DDImage/Pixel.h"
#include "DDImage/Row.h"
#include "DDImage/Vector3.h"
#include "DDImage/VertexContext.h"

#include "Project360Math.h"

#include <algorithm>
#include <cmath>

using namespace DD::Image;

static const char* const CLASS = "Project360";
static const char* const HELP =
    "Projects a LatLong (equirectangular) image onto geometry from the position of the 'cam' input, "
    "the way spherical projection works in 3D packages: each surface point is looked up by its "
    "direction from the projector.\n\n"
    "img: LatLong image.  cam: Camera or Axis (world position, optionally rotation).\n"
    "Use as a material; bake with ScanlineRender projection mode 'uv'.";

class Project360 : public Material
{
  float heading_;
  bool mirror_;
  bool use_rotation_;
  bool alpha_one_;
  Filter filter_;

  Matrix4 world_to_projector_;
  float tex_x_, tex_y_, tex_w_, tex_h_;

  project360::UV lookup(const Vector3& world) const
  {
    const Vector3 d = world_to_projector_.transform(world);
    return project360::direction_to_latlong(d.x, d.y, d.z, heading_, mirror_);
  }

public:
  static const Iop::Description description;

  explicit Project360(Node* node)
    : Material(node)
    , heading_(0.0f)
    , mirror_(false)
    , use_rotation_(true)
    , alpha_one_(true)
    , tex_x_(0.0f)
    , tex_y_(0.0f)
    , tex_w_(1.0f)
    , tex_h_(1.0f)
  {
    world_to_projector_.makeIdentity();
  }

  const char* Class() const override { return CLASS; }
  const char* node_help() const override { return HELP; }

  int minimum_inputs() const override { return 2; }
  int maximum_inputs() const override { return 2; }

  bool test_input(int input, Op* op) const override
  {
    if (input == 1) {
      return dynamic_cast<AxisOp*>(op) != nullptr;
    }
    return Material::test_input(input, op);
  }

  Op* default_input(int input) const override
  {
    if (input == 1) {
      return nullptr;
    }
    return Material::default_input(input);
  }

  const char* input_label(int input, char*) const override
  {
    return input == 1 ? "cam" : "img";
  }

  void knobs(Knob_Callback f) override
  {
    Float_knob(f, &heading_, IRange(-180, 180), "heading", "heading (deg)");
    Tooltip(f, "Rotates the panorama around the projector's vertical axis.");
    Bool_knob(f, &mirror_, "mirror", "mirror horizontally");
    SetFlags(f, Knob::STARTLINE);
    Tooltip(f, "Flip the panorama left/right.");
    Bool_knob(f, &use_rotation_, "use_camera_rotation", "use camera rotation");
    SetFlags(f, Knob::STARTLINE);
    Tooltip(f, "On: the panorama follows the cam input's rotation. Off: only its position is used and "
               "the panorama stays aligned to world axes (-Z = centre of the image).");
    Bool_knob(f, &alpha_one_, "alpha_one", "set alpha to 1");
    SetFlags(f, Knob::STARTLINE);
    Tooltip(f, "HDR files usually have no alpha. On: the projection is fully opaque everywhere.");
    filter_.knobs(f);
  }

  void _validate(bool for_real) override
  {
    input0().validate(for_real);
    copy_info();
    if (alpha_one_) {
      info_.turn_on(Mask_Alpha);
    }
    filter_.initialize();

    world_to_projector_.makeIdentity();
    if (AxisOp* axis = dynamic_cast<AxisOp*>(Op::input(1))) {
      axis->validate(for_real);
      if (use_rotation_) {
        world_to_projector_ = axis->imatrix();
      }
      else {
        const Matrix4& m = axis->matrix();
        world_to_projector_.translation(-m.a03, -m.a13, -m.a23);
      }
    }

    const Format& fmt = input0().format();
    tex_x_ = float(fmt.x());
    tex_y_ = float(fmt.y());
    tex_w_ = float(std::max(1, fmt.w()));
    tex_h_ = float(std::max(1, fmt.h()));
  }

  void _request(int, int, int, int, ChannelMask channels, int count) override
  {
    // A spherical lookup can land anywhere in the panorama.
    input0().request(channels, count);
  }

  // As a 2D image the node passes its input through.
  void engine(int y, int x, int r, ChannelMask channels, Row& out) override
  {
    input0().get(y, x, r, channels, out);
    if (alpha_one_ && channels.contains(Chan_Alpha)) {
      float* alpha = out.writable(Chan_Alpha);
      std::fill(alpha + x, alpha + r, 1.0f);
    }
  }

  void fragment_shader(const VertexContext& vtx, Pixel& out) override
  {
    const Vector3 p = vtx.PW();
    const project360::UV c = lookup(p);
    const project360::UV cx = lookup(p + vtx.dPWdx());
    const project360::UV cy = lookup(p + vtx.dPWdy());

    // Filter footprint from the screen-space derivatives; u wraps, so measure across the seam.
    const double du = std::max(std::fabs(project360::wrapped_delta(c.u, cx.u)), std::fabs(project360::wrapped_delta(c.u, cy.u)));
    const double dv = std::max(std::fabs(cx.v - c.v), std::fabs(cy.v - c.v));
    const float w = std::max(1.0f, float(du) * tex_w_);
    const float h = std::max(1.0f, float(dv) * tex_h_);

    input0().sample(tex_x_ + float(c.u) * tex_w_, tex_y_ + float(c.v) * tex_h_, w, h, &filter_, out);
    if (alpha_one_ && out.channels.contains(Chan_Alpha)) {
      out[Chan_Alpha] = 1.0f;
    }
  }

  // The OpenGL viewer can only map textures linearly; showing the LatLong through the mesh UVs would
  // be wrong, so the viewport draws the geometry untextured. Check results with ScanlineRender.
  bool set_texturemap(ViewerContext*, bool) { return false; }
  void unset_texturemap(ViewerContext*) {}
};

static Iop* build(Node* node)
{
  return new Project360(node);
}

const Iop::Description Project360::description(CLASS, "3D/Project360", build);
