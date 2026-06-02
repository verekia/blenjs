"""Z-up Transform conversion (spec §6.6).

The game is **Z-up right-handed**, the same world frame as Blender: X right, Y
depth (forward), Z up. Position and scale are therefore *identical* on both
sides — they pass through untouched. The only thing that still differs is the
Euler *order* the two engines use for the same ``'XYZ'`` triple:

* **Three.js** ``THREE.Euler('XYZ')`` builds ``R = Rx·Ry·Rz``.
* **Blender** ``Euler('XYZ')`` builds ``R = Rz·Ry·Rx``.

Those are different rotations for the same three numbers, so rotation is still
converted by building the matrix with one convention and decoding it with the
other — never copied verbatim. Everything else is the identity.

    pos_blender   = pos_game
    scale_blender = scale_game
    rot_blender   = decode_blender( build_three(rot_game) )

and exactly the inverse on save. This module is pure Python (no ``bpy`` /
``mathutils``) so the data path stays unit-testable in CI and byte-stable; the
conventions are pinned to three.js / mathutils in ``blender/tests/test_transform.py``.
"""

from __future__ import annotations

import math


# --------------------------------------------------------------------------- #
# Tiny 3x3 linear algebra
# --------------------------------------------------------------------------- #
def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _rx(t):
    c, s = math.cos(t), math.sin(t)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def _ry(t):
    c, s = math.cos(t), math.sin(t)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


def _rz(t):
    c, s = math.cos(t), math.sin(t)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def _clamp(x):
    return -1.0 if x < -1.0 else (1.0 if x > 1.0 else x)


# --------------------------------------------------------------------------- #
# Euler <-> matrix, per engine convention
# --------------------------------------------------------------------------- #
def euler_three_to_mat(x, y, z):
    """THREE.Euler('XYZ') -> matrix: R = Rx·Ry·Rz."""
    return _matmul(_rx(x), _matmul(_ry(y), _rz(z)))


def euler_blender_to_mat(x, y, z):
    """Blender Euler('XYZ') -> matrix: R = Rz·Ry·Rx."""
    return _matmul(_rz(z), _matmul(_ry(y), _rx(x)))


def mat_to_euler_three(m):
    """Inverse of euler_three_to_mat — matches THREE.Euler.setFromRotationMatrix('XYZ')."""
    y = math.asin(_clamp(m[0][2]))
    if abs(m[0][2]) < 0.9999999:
        x = math.atan2(-m[1][2], m[2][2])
        z = math.atan2(-m[0][1], m[0][0])
    else:  # gimbal lock
        x = math.atan2(m[2][1], m[1][1])
        z = 0.0
    return [x, y, z]


def mat_to_euler_blender(m):
    """Inverse of euler_blender_to_mat — matches mathutils' Matrix.to_euler('XYZ')."""
    cy = math.hypot(m[0][0], m[1][0])
    y = math.atan2(-m[2][0], cy)
    if cy > 1e-7:
        x = math.atan2(m[2][1], m[2][2])
        z = math.atan2(m[1][0], m[0][0])
    else:  # gimbal lock
        x = math.atan2(-m[1][2], m[1][1])
        z = 0.0
    return [x, y, z]


def _vec3(v, default):
    seq = list(v) if isinstance(v, (list, tuple)) else list(default)
    seq = [float(x) for x in (seq + list(default))[:3]]
    return seq


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def game_to_blender(pos, rot, scale):
    """YAML (Z-up, three.js euler) -> Blender (Z-up, Blender euler).

    Both frames are Z-up, so position and scale are identical; only the Euler
    order is reconciled (three.js Rx·Ry·Rz -> Blender Rz·Ry·Rx).
    """
    pos = _vec3(pos, (0.0, 0.0, 0.0))
    rot = _vec3(rot, (0.0, 0.0, 0.0))
    scale = _vec3(scale, (1.0, 1.0, 1.0))
    return pos, mat_to_euler_blender(euler_three_to_mat(*rot)), scale


def blender_to_game(pos, rot, scale):
    """Blender (Z-up, Blender euler) -> YAML (Z-up, three.js euler)."""
    pos = _vec3(pos, (0.0, 0.0, 0.0))
    rot = _vec3(rot, (0.0, 0.0, 0.0))
    scale = _vec3(scale, (1.0, 1.0, 1.0))
    return pos, mat_to_euler_three(euler_blender_to_mat(*rot)), scale
