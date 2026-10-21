// Standalone test for Project360Math.h (no Nuke needed):  g++ -std=c++17 test_project360_math.cpp && ./a.out
#include "Project360Math.h"

#include <cstdio>
#include <cstdlib>

static int failures = 0;

static void check(const char* what, double got, double want)
{
  if (std::fabs(got - want) > 1e-9) {
    std::printf("FAIL %s: got %.12f want %.12f\n", what, got, want);
    ++failures;
  }
}

int main()
{
  using project360::direction_to_latlong;

  // Cardinal directions, Nuke camera convention.
  check("front u", direction_to_latlong(0, 0, -1, 0, false).u, 0.5);
  check("front v", direction_to_latlong(0, 0, -1, 0, false).v, 0.5);
  check("right u", direction_to_latlong(1, 0, 0, 0, false).u, 0.75);
  check("left u", direction_to_latlong(-1, 0, 0, 0, false).u, 0.25);
  check("back u", direction_to_latlong(0, 0, 1, 0, false).u, 0.0);
  check("up v", direction_to_latlong(0, 1, 0, 0, false).v, 1.0);
  check("down v", direction_to_latlong(0, -1, 0, 0, false).v, 0.0);
  check("45 up v", direction_to_latlong(0, 1, -1, 0, false).v, 0.75);

  // Scale invariance (dome radius does not matter).
  check("scaled u", direction_to_latlong(1e6, 3e5, -2e6, 0, false).u, direction_to_latlong(1, 0.3, -2, 0, false).u);
  check("scaled v", direction_to_latlong(1e6, 3e5, -2e6, 0, false).v, direction_to_latlong(1, 0.3, -2, 0, false).v);

  // Heading and mirror.
  check("heading 90", direction_to_latlong(0, 0, -1, 90, false).u, 0.75);
  check("heading -180 wraps", direction_to_latlong(0, 0, -1, -180, false).u, 0.0);
  check("mirror right", direction_to_latlong(1, 0, 0, 0, true).u, 0.25);

  // Seam handling for filter footprints.
  check("delta across seam", project360::wrapped_delta(0.999, 0.001), 0.002);
  check("delta across seam back", project360::wrapped_delta(0.001, 0.999), -0.002);
  check("delta normal", project360::wrapped_delta(0.2, 0.3), 0.1);

  // Degenerate point at the projector centre.
  check("origin u", direction_to_latlong(0, 0, 0, 0, false).u, 0.5);

  // Round trip against the inverse mapping over the whole sphere.
  for (int i = 0; i < 1000; ++i) {
    const double u = (i % 37 + 0.5) / 37.0, v = (i / 37 % 27 + 0.5) / 27.0;
    const double lon = (u - 0.5) * 2 * project360::kPi, lat = (v - 0.5) * project360::kPi;
    const double x = std::cos(lat) * std::sin(lon), y = std::sin(lat), z = -std::cos(lat) * std::cos(lon);
    const project360::UV r = direction_to_latlong(x, y, z, 0, false);
    check("round trip u", r.u, u);
    check("round trip v", r.v, v);
  }

  std::printf(failures ? "%d failures\n" : "all passed\n", failures);
  return failures ? EXIT_FAILURE : EXIT_SUCCESS;
}
