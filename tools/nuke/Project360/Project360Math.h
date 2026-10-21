// LatLong (equirectangular) mapping used by Project360. No Nuke dependency so it can be unit tested.
//
// Directions are in projector space, Nuke camera convention: looks down -Z, +Y is up, +X is right.
//   u = 0.5 + atan2(x, -z) / 2pi   -> 0.5 straight ahead (-Z), increasing to the right (+X)
//   v = 0.5 + asin(y / |d|) / pi   -> 0.5 on the horizon, 1 at the zenith (Nuke images have y up)
#pragma once

#include <algorithm>
#include <cmath>

namespace project360 {

constexpr double kPi = 3.14159265358979323846;

struct UV
{
  double u;
  double v;
};

inline double wrap01(double u)
{
  return u - std::floor(u);
}

// Shortest signed distance from a to b on the wrapping u axis, in [-0.5, 0.5).
inline double wrapped_delta(double a, double b)
{
  const double d = b - a;
  return d - std::floor(d + 0.5);
}

inline UV direction_to_latlong(double x, double y, double z, double heading_deg, bool mirror)
{
  const double len = std::sqrt(x * x + y * y + z * z);
  if (len <= 0.0) {
    return {0.5, 0.5};
  }
  double u = wrap01(0.5 + std::atan2(x, -z) / (2.0 * kPi) + heading_deg / 360.0);
  if (mirror) {
    u = wrap01(1.0 - u);
  }
  const double s = std::max(-1.0, std::min(1.0, y / len));
  return {u, 0.5 + std::asin(s) / kPi};
}

}  // namespace project360
