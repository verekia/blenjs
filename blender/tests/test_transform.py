#!/usr/bin/env python3
"""Z-up Transform conversion checks (pure Python, no Blender required).

Both the game and Blender are Z-up, so position and scale pass through
untouched; only the Euler *order* is reconciled. The checks pin the rotation
conventions to the real engines and prove invertibility:

  A. euler->matrix matches three.js ('XYZ' = Rx·Ry·Rz) and Blender's mathutils
     ('XYZ' = Rz·Ry·Rx) for a reference angle. Golden matrices were captured from
     `THREE.Matrix4().makeRotationFromEuler` and `mathutils.Euler.to_matrix`.
  B. blender_to_game(game_to_blender(x)) == x  (the editor round-trip is exact).
  C. euler->matrix->euler is identity for both conventions (extraction is a true
     inverse).
"""

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.abspath(os.path.join(HERE, "..", "blenjs_addon"))
sys.path.insert(0, ADDON)  # import transform.py directly (no bpy via package __init__)

import transform as T  # noqa: E402

OK = "\033[32m"
FAIL = "\033[31m"
END = "\033[0m"

# Reference matrices for euler (0.1, 0.2, 0.3), row-major, from the real engines.
THREE_XYZ = [
    [0.936293, -0.289629, 0.198669],
    [0.312992, 0.944702, -0.097843],
    [-0.159345, 0.153792, 0.975170],
]
BLENDER_XYZ = [
    [0.936293363571167, -0.2750958502292633, 0.21835066378116608],
    [0.2896294891834259, 0.9564250707626343, -0.03695701062679291],
    [-0.19866932928562164, 0.09784339368343353, 0.9751703143119812],
]


def _close(a, b, tol):
    return abs(a - b) <= tol


def _mat_close(m, ref, tol):
    return all(_close(m[i][j], ref[i][j], tol) for i in range(3) for j in range(3))


def _vec_close(a, b, tol=1e-9):
    return all(_close(a[i], b[i], tol) for i in range(3))


def _orient_err(a, b, to_mat):
    # Orientation distance as the largest matrix-element difference (euler triples
    # are not unique, so compare the rotations they produce, not the raw numbers).
    ma, mb = to_mat(*a), to_mat(*b)
    return max(abs(ma[i][j] - mb[i][j]) for i in range(3) for j in range(3))


def main() -> int:
    random.seed(1234)
    failures = 0

    def check(cond, msg):
        nonlocal failures
        if cond:
            print(f"{OK}PASS{END} {msg}")
        else:
            failures += 1
            print(f"{FAIL}FAIL{END} {msg}")

    # A. conventions pinned to three.js and mathutils
    check(_mat_close(T.euler_three_to_mat(0.1, 0.2, 0.3), THREE_XYZ, 1e-5), "three.js 'XYZ' euler->matrix (Rx·Ry·Rz)")
    check(_mat_close(T.euler_blender_to_mat(0.1, 0.2, 0.3), BLENDER_XYZ, 1e-7), "Blender 'XYZ' euler->matrix (Rz·Ry·Rx)")

    # spot-checks: both frames are Z-up, so position & scale pass through unchanged
    pb, rb, sb = T.game_to_blender([5, 0, 3], [0, 0, 0], [3, 3, 0.5])
    check(_vec_close(pb, [5, 0, 3]) and _vec_close(sb, [3, 3, 0.5]), "game -> blender leaves pos & scale unchanged (Z-up == Z-up)")
    pg, rg, sg = T.blender_to_game([5, 0, 3], [0, 0, 0], [3, 3, 0.5])
    check(_vec_close(pg, [5, 0, 3]) and _vec_close(sg, [3, 3, 0.5]), "blender -> game leaves pos & scale unchanged")

    # B. editor round-trip. Position & scale are algebraically exact; orientation
    #    is exact away from gimbal lock, and bounded at it (Euler extraction is
    #    ill-conditioned exactly at y=±90° — three.js behaves identically there).
    worst_ps = worst_rot = worst_rot_gimbal = 0.0
    for _ in range(5000):
        pos = [random.uniform(-50, 50) for _ in range(3)]
        rot = [random.uniform(-math.pi, math.pi) for _ in range(3)]
        scale = [random.uniform(0.05, 5) for _ in range(3)]
        pb, rb, sb = T.game_to_blender(pos, rot, scale)
        pg, rg, sg = T.blender_to_game(pb, rb, sb)
        worst_ps = max(worst_ps, *(abs(pg[i] - pos[i]) for i in range(3)), *(abs(sg[i] - scale[i]) for i in range(3)))
        err = _orient_err(rg, rot, T.euler_three_to_mat)
        if abs(T.euler_three_to_mat(*rot)[0][2]) > 0.9999:  # near gimbal lock
            worst_rot_gimbal = max(worst_rot_gimbal, err)
        else:
            worst_rot = max(worst_rot, err)
    check(worst_ps < 1e-9, f"pos & scale round-trip is exact (worst {worst_ps:.2e})")
    check(worst_rot < 1e-6, f"rotation round-trip is exact away from gimbal lock (worst {worst_rot:.2e})")
    check(worst_rot_gimbal < 1e-3, f"rotation round-trip stays bounded at gimbal lock (worst {worst_rot_gimbal:.2e})")

    # C. euler->matrix->euler is the identity rotation (extraction inverts construction).
    worst_three = worst_bl = 0.0
    for _ in range(5000):
        e = [random.uniform(-math.pi, math.pi) for _ in range(3)]
        gimbal_three = abs(T.euler_three_to_mat(*e)[0][2]) > 0.9999
        gimbal_bl = abs(T.euler_blender_to_mat(*e)[2][0]) > 0.9999
        if not gimbal_three:
            worst_three = max(worst_three, _orient_err(T.mat_to_euler_three(T.euler_three_to_mat(*e)), e, T.euler_three_to_mat))
        if not gimbal_bl:
            worst_bl = max(worst_bl, _orient_err(T.mat_to_euler_blender(T.euler_blender_to_mat(*e)), e, T.euler_blender_to_mat))
    check(worst_three < 1e-6, f"three.js euler->matrix->euler is identity off-gimbal (worst {worst_three:.2e})")
    check(worst_bl < 1e-6, f"Blender euler->matrix->euler is identity off-gimbal (worst {worst_bl:.2e})")

    print()
    if failures:
        print(f"{FAIL}{failures} check(s) failed{END}")
        return 1
    print(f"{OK}all transform-conversion checks passed{END}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
