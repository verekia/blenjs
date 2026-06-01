"""A minimal, faithful fake of the slice of the Blender Python API that
``schema.py`` / ``scenes.py`` / ``uuids.py`` actually use.

This is NOT a general bpy emulator — it implements exactly the behaviours the
add-on's data path relies on (native object transform, dynamic PropertyGroup
slots, the active-set booleans, pointer + collection refs, data collections,
a stub bmesh). It exists so the Blender datablock round-trip can be exercised in
CI without Blender. The authoritative test is still running it inside Blender.
"""

import sys
import types


# --------------------------------------------------------------------------- #
# bpy.props — return descriptor sentinels we interpret ourselves.
# --------------------------------------------------------------------------- #
class _Prop:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.kw = kw
        self.type = kw.get("type")


def FloatProperty(**kw):
    return _Prop("float", **kw)


def IntProperty(**kw):
    return _Prop("int", **kw)


def BoolProperty(**kw):
    return _Prop("bool", **kw)


def StringProperty(**kw):
    return _Prop("string", **kw)


def EnumProperty(**kw):
    return _Prop("enum", **kw)


def FloatVectorProperty(**kw):
    return _Prop("vector", **kw)


def PointerProperty(**kw):
    return _Prop("pointer", **kw)


def CollectionProperty(**kw):
    return _Prop("collection", **kw)


class _Collection(list):
    def __init__(self, item_type):
        super().__init__()
        self._t = item_type

    def add(self):
        it = self._t()
        self.append(it)
        return it

    def clear(self):
        del self[:]

    def remove(self, i):
        del self[i]


def _default_for(prop: _Prop):
    k = prop.kind
    if k == "float":
        return float(prop.kw.get("default", 0.0))
    if k == "int":
        return int(prop.kw.get("default", 0))
    if k == "bool":
        return bool(prop.kw.get("default", False))
    if k == "string":
        return str(prop.kw.get("default", ""))
    if k == "enum":
        if "default" in prop.kw:
            return prop.kw["default"]
        items = prop.kw.get("items", [])
        return items[0][0] if items else ""
    if k == "vector":
        d = prop.kw.get("default")
        return tuple(d) if d is not None else tuple([0.0] * prop.kw.get("size", 3))
    if k == "pointer":
        return None  # object ref
    if k == "collection":
        return _Collection(prop.type)
    return None


# --------------------------------------------------------------------------- #
# bpy.types
# --------------------------------------------------------------------------- #
class PropertyGroup:
    def __init__(self):
        for fname, prop in getattr(type(self), "__annotations__", {}).items():
            object.__setattr__(self, fname, _default_for(prop))


class OperatorFileListElement:
    pass


class _ObjectMeta(type):
    def __setattr__(cls, name, value):
        if isinstance(value, _Prop):
            cls._bjs_props[name] = value
        else:
            super().__setattr__(name, value)


class Object(metaclass=_ObjectMeta):
    _bjs_props: dict = {}

    def __init__(self, name, data=None):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "location", [0.0, 0.0, 0.0])
        object.__setattr__(self, "rotation_euler", [0.0, 0.0, 0.0])
        object.__setattr__(self, "scale", [1.0, 1.0, 1.0])
        object.__setattr__(self, "empty_display_type", "PLAIN_AXES")
        object.__setattr__(self, "empty_display_size", 1.0)
        object.__setattr__(self, "_custom", {})
        object.__setattr__(self, "_pgs", {})

    def get(self, key, default=None):
        return self._custom.get(key, default)

    def __getattr__(self, name):  # only called when normal lookup fails
        props = type(self)._bjs_props
        if name in props:
            p = props[name]
            if p.kind == "pointer" and isinstance(p.type, type) and issubclass(p.type, PropertyGroup):
                if name not in self._pgs:
                    self._pgs[name] = p.type()
                return self._pgs[name]
            return self._custom.get(name, _default_for(p))
        raise AttributeError(name)

    def __setattr__(self, name, value):
        props = type(self)._bjs_props
        if name in props and props[name].kind in ("bool", "string"):
            self._custom[name] = value
        else:
            object.__setattr__(self, name, value)


class _SceneMeta(type):
    def __setattr__(cls, name, value):
        if isinstance(value, _Prop):
            cls._bjs_props[name] = value
        else:
            super().__setattr__(name, value)


class _SceneCollection:
    def __init__(self):
        self._objs = []

    @property
    def objects(self):
        return self

    def link(self, obj):
        self._objs.append(obj)

    @property
    def all_objects(self):
        return list(self._objs)


class Scene(metaclass=_SceneMeta):
    _bjs_props: dict = {}

    def __init__(self, name):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "collection", _SceneCollection())
        object.__setattr__(self, "_custom", {})

    def __getattr__(self, name):
        props = type(self)._bjs_props
        if name in props:
            return self._custom.get(name, _default_for(props[name]))
        raise AttributeError(name)

    def __setattr__(self, name, value):
        props = type(self)._bjs_props
        if name in props:
            self._custom[name] = value
        else:
            object.__setattr__(self, name, value)


class Mesh:
    def __init__(self, name):
        self.name = name
        self.users = 0


class Panel:
    pass


class Menu:
    pass


class UIList:
    pass


class Operator:
    pass


class FileHandler:
    pass


class AddonPreferences:
    pass


class WindowManager:
    pass


# --------------------------------------------------------------------------- #
# bpy.data
# --------------------------------------------------------------------------- #
class _MeshData:
    def __init__(self):
        self._d = {}

    def new(self, name):
        m = Mesh(name)
        self._d[name] = m
        return m

    def get(self, name):
        return self._d.get(name)

    def remove(self, mesh):
        self._d.pop(mesh.name, None)


class _ObjectData:
    def __init__(self):
        self._all = []

    def new(self, name, data):
        return Object(name, data)

    def remove(self, obj, do_unlink=True):
        for sc in _data.scenes:
            if obj in sc.collection._objs:
                sc.collection._objs.remove(obj)


class _SceneData:
    def __init__(self):
        self._d = {}

    def new(self, name):
        sc = Scene(name)
        self._d[name] = sc
        return sc

    def get(self, name):
        return self._d.get(name)

    def __iter__(self):
        return iter(self._d.values())


class _Data:
    def __init__(self):
        self.meshes = _MeshData()
        self.objects = _ObjectData()
        self.scenes = _SceneData()


_data = _Data()


# --------------------------------------------------------------------------- #
# bpy.utils / bpy.path / context
# --------------------------------------------------------------------------- #
def register_class(cls):
    pass


def unregister_class(cls):
    pass


def abspath(p):
    return p


class _WM:
    blenjs_filepath = ""

    def fileselect_add(self, op):
        pass


class _Window:
    scene = None


class _Context:
    def __init__(self):
        self.window_manager = _WM()
        self.window = _Window()
        self.area = None
        self.object = None

        class _Prefs:
            addons = {}

        self.preferences = _Prefs()


def install():
    """Inject the fake modules into sys.modules. Call before importing the add-on."""
    bpy = types.ModuleType("bpy")

    props = types.ModuleType("bpy.props")
    for n in (
        "FloatProperty",
        "IntProperty",
        "BoolProperty",
        "StringProperty",
        "EnumProperty",
        "FloatVectorProperty",
        "PointerProperty",
        "CollectionProperty",
    ):
        setattr(props, n, globals()[n])

    bpy_types = types.ModuleType("bpy.types")
    for n in (
        "PropertyGroup",
        "Object",
        "Scene",
        "Mesh",
        "Panel",
        "Menu",
        "UIList",
        "Operator",
        "FileHandler",
        "AddonPreferences",
        "WindowManager",
        "OperatorFileListElement",
    ):
        setattr(bpy_types, n, globals()[n])

    bpy_utils = types.ModuleType("bpy.utils")
    bpy_utils.register_class = register_class
    bpy_utils.unregister_class = unregister_class

    bpy_path = types.ModuleType("bpy.path")
    bpy_path.abspath = abspath

    bpy.props = props
    bpy.types = bpy_types
    bpy.utils = bpy_utils
    bpy.path = bpy_path
    bpy.data = _data
    bpy.context = _Context()

    bmesh = types.ModuleType("bmesh")

    class _BM:
        def to_mesh(self, me):
            pass

        def free(self):
            pass

    bmesh.new = lambda: _BM()
    bmesh.ops = types.SimpleNamespace(create_cube=lambda bm, size=1.0: None)

    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = props
    sys.modules["bpy.types"] = bpy_types
    sys.modules["bpy.utils"] = bpy_utils
    sys.modules["bpy.path"] = bpy_path
    sys.modules["bmesh"] = bmesh
    return bpy
