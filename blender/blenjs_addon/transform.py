"""Y-up (game / three.js) <-> Z-up (Blender) Transform conversion (spec §6.6).

The game is **Y-up**: the runtime feeds ``Transform.rot`` to a ``THREE.Euler`` in
``'XYZ'`` order, whose matrix is ``Rx·Ry·Rz``. Blender is **Z-up** and stores
``rotation_euler`` as a Blender ``Euler('XYZ')``, whose matrix is ``Rz·Ry·Rx``.
Those two ``'XYZ'`` conventions are *different rotations* for the same triple, so
rotation is always converted through a rotation matrix, decoded with whichever
convention belongs to that side.

The world conversion is a fixed +90° rotation about X (``C``), applied to each
object's transform by **conjugation** so an axis-aligned object stays axis-aligned
— only which axis is "up" changes. A Y-up level then stands upright in Blender's
Z-up viewport instead of lying flat along +Y.

    pos_blender    = C · pos_game                      ( = (x, -z, y) )
    linear_blender = C · (R_game · S_game) · Cᵀ        -> decode Blender rot + scale

and exactly the inverse on save. This module is pure Python (no ``bpy`` /
``mathutils``) so the data path stays unit-testable in CI and byte-stable; the
conventions are pinned to three.js / mathutils in ``blender/tests/test_transform.py``.
"""

from __future__ import annotations

import math

# C: game (Y-up) -> blender (Z-up) is +90° about X.
#   C  = [[1,0,0],[0,0,-1],[0,1,0]]   C·(x,y,z)  = (x, -z, y)
#   Cᵀ = [[1,0,0],[0,0,1],[0,-1,0]]   Cᵀ·(x,y,z) = (x, z, -y)
_C = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))
_CT = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))


# --------------------------------------------------------------------------- #
# Tiny 3x3 linear algebra
# --------------------------------------------------------------------------- #
def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _matvec(a, v):
    return [a[i][0] * v[0] + a[i][1] * v[1] + a[i][2] * v[2] for i in range(3)]


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


# --------------------------------------------------------------------------- #
# Linear-part decompose (R · diag(scale), positive scale, no shear/mirror)
# --------------------------------------------------------------------------- #
def _scaled(r, scale):
    return [[r[i][c] * scale[c] for c in range(3)] for i in range(3)]


def _decompose(m):
    scale = [math.sqrt(m[0][c] ** 2 + m[1][c] ** 2 + m[2][c] ** 2) for c in range(3)]
    rot = [[(m[i][c] / scale[c] if scale[c] else float(i == c)) for c in range(3)] for i in range(3)]
    return rot, scale


def _vec3(v, default):
    seq = list(v) if isinstance(v, (list, tuple)) else list(default)
    seq = [float(x) for x in (seq + list(default))[:3]]
    return seq


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def game_to_blender(pos, rot, scale):
    """YAML (Y-up, three.js euler) -> Blender (Z-up, Blender euler)."""
    pos = _vec3(pos, (0.0, 0.0, 0.0))
    rot = _vec3(rot, (0.0, 0.0, 0.0))
    scale = _vec3(scale, (1.0, 1.0, 1.0))
    linear = _matmul(_matmul(_C, _scaled(euler_three_to_mat(*rot), scale)), _CT)
    r_b, s_b = _decompose(linear)
    return _matvec(_C, pos), mat_to_euler_blender(r_b), s_b


def blender_to_game(pos, rot, scale):
    """Blender (Z-up, Blender euler) -> YAML (Y-up, three.js euler)."""
    pos = _vec3(pos, (0.0, 0.0, 0.0))
    rot = _vec3(rot, (0.0, 0.0, 0.0))
    scale = _vec3(scale, (1.0, 1.0, 1.0))
    linear = _matmul(_matmul(_CT, _scaled(euler_blender_to_mat(*rot), scale)), _C)
    r_g, s_g = _decompose(linear)
    return _matvec(_CT, pos), mat_to_euler_three(r_g), s_g
