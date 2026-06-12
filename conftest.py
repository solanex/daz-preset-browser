# The addon root is a Python package whose __init__.py imports bpy, which
# only exists inside Blender. Keep pytest away from it; only tests/ matters.
collect_ignore = ["__init__.py"]
