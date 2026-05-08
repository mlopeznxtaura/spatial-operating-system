"""
scene/usd_loader.py
Load and compose .usda/.usdc/.usdz scenes via OpenUSD Python bindings.
Exposes a clean interface for the Omniverse streaming server and API layer.
"""

from pxr import Usd, UsdGeom, UsdShade, Sdf, UsdSkel
from pathlib import Path
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)


class USDSceneLoader:
    """
    Loads and traverses OpenUSD scenes.
    Extracts geometry, materials, transforms, and skeletal animation
    from the safe web-renderable subset:
      - UsdGeomMesh
      - UsdGeomXform
      - UsdPreviewSurface (-> PBR metallic-roughness)
      - UsdGeomSubset (multi-material)
      - Basic UsdSkel
      - Xform animations (time-sampled)
    """

    # USD features NOT safe for web rendering — skip silently
    UNSUPPORTED = {
        "MaterialX",
        "UsdLux",          # LightsAPI
        "UsdPhysics",      # Physics schemas
        "PointInstancer",  # Point instancing
    }

    def __init__(self, scene_path: str | Path):
        self.path = Path(scene_path)
        self.stage: Optional[Usd.Stage] = None
        self._scene_data: dict = {}

    def load(self) -> "USDSceneLoader":
        """Open the USD stage and validate it's loadable."""
        if not self.path.exists():
            raise FileNotFoundError(f"USD file not found: {self.path}")

        logger.info(f"Loading USD stage: {self.path}")
        self.stage = Usd.Stage.Open(str(self.path))
        if not self.stage:
            raise RuntimeError(f"Failed to open USD stage: {self.path}")

        self._scene_data = {
            "path": str(self.path),
            "up_axis": UsdGeom.GetStageUpAxis(self.stage),
            "meters_per_unit": UsdGeom.GetStageMetersPerUnit(self.stage),
            "start_time": self.stage.GetStartTimeCode(),
            "end_time": self.stage.GetEndTimeCode(),
            "meshes": [],
            "xforms": [],
            "materials": [],
            "skeletons": [],
        }

        self._traverse()
        logger.info(
            f"Stage loaded: {len(self._scene_data['meshes'])} meshes, "
            f"{len(self._scene_data['materials'])} materials"
        )
        return self

    def _traverse(self):
        """Walk the prim tree and extract renderable data."""
        for prim in self.stage.Traverse():
            type_name = prim.GetTypeName()

            # Skip unsupported schemas
            if any(u in type_name for u in self.UNSUPPORTED):
                logger.debug(f"Skipping unsupported prim type: {type_name} at {prim.GetPath()}")
                continue

            if type_name == "Mesh":
                self._extract_mesh(prim)
            elif type_name == "Xform":
                self._extract_xform(prim)
            elif type_name == "Material":
                self._extract_material(prim)
            elif type_name == "Skeleton":
                self._extract_skeleton(prim)

    def _extract_mesh(self, prim):
        mesh = UsdGeom.Mesh(prim)
        path = str(prim.GetPath())

        points_attr = mesh.GetPointsAttr()
        points = points_attr.Get() if points_attr else None
        face_counts = mesh.GetFaceVertexCountsAttr().Get()
        face_indices = mesh.GetFaceVertexIndicesAttr().Get()

        # Get world transform at default time
        xformable = UsdGeom.Xformable(prim)
        transform = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())

        self._scene_data["meshes"].append({
            "path": path,
            "name": prim.GetName(),
            "vertex_count": len(points) if points else 0,
            "face_count": len(face_counts) if face_counts else 0,
            "transform": list(transform),
            "has_normals": mesh.GetNormalsAttr().HasValue(),
            "has_uvs": bool(prim.GetAttribute("primvars:st").IsValid()),
        })

    def _extract_xform(self, prim):
        xformable = UsdGeom.Xformable(prim)
        transform = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        self._scene_data["xforms"].append({
            "path": str(prim.GetPath()),
            "name": prim.GetName(),
            "transform": list(transform),
            "has_time_samples": prim.GetAttribute("xformOp:transform").GetNumTimeSamples() > 0
            if prim.GetAttribute("xformOp:transform").IsValid() else False,
        })

    def _extract_material(self, prim):
        material = UsdShade.Material(prim)
        surface_output = material.GetSurfaceOutput()
        shader_path = None

        if surface_output and surface_output.HasConnectedSource():
            connected = surface_output.GetConnectedSources()
            if connected:
                shader_path = str(connected[0][0].source.GetPath())

        self._scene_data["materials"].append({
            "path": str(prim.GetPath()),
            "name": prim.GetName(),
            "shader_path": shader_path,
        })

    def _extract_skeleton(self, prim):
        skeleton = UsdSkel.Skeleton(prim)
        joints = skeleton.GetJointsAttr().Get()
        self._scene_data["skeletons"].append({
            "path": str(prim.GetPath()),
            "name": prim.GetName(),
            "joint_count": len(joints) if joints else 0,
        })

    def get_scene_data(self) -> dict:
        """Return extracted scene data as a dict (JSON-serializable)."""
        return self._scene_data

    def to_json(self) -> str:
        return json.dumps(self._scene_data, default=str, indent=2)

    def get_prim_at_path(self, path: str) -> Optional[Usd.Prim]:
        if not self.stage:
            return None
        prim = self.stage.GetPrimAtPath(path)
        return prim if prim.IsValid() else None

    def list_variants(self, prim_path: str) -> dict[str, list[str]]:
        """List all variant sets and their options for a prim."""
        prim = self.get_prim_at_path(prim_path)
        if not prim:
            return {}
        variant_sets = prim.GetVariantSets()
        result = {}
        for vs_name in variant_sets.GetNames():
            vs = variant_sets.GetVariantSet(vs_name)
            result[vs_name] = vs.GetVariantNames()
        return result


def load_scene(path: str | Path) -> USDSceneLoader:
    """Convenience function: load a USD scene and return the loader."""
    return USDSceneLoader(path).load()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python usd_loader.py <path_to.usda>")
        sys.exit(1)

    loader = load_scene(sys.argv[1])
    print(loader.to_json())

