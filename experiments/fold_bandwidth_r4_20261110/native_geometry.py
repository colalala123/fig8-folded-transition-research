# Derived from installed folded_transition.py sha256 66c6f116954687f5a9473ec8c9c58375a2a71e1cdc9583b43796c11a978f3763
# Standalone geometry-only copy; 17 significant digits preserve frozen operands.
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


GROUND_X_MIN = -15.0
GROUND_X_MAX = 15.0
GROUND_Y_MIN = -25.0
GROUND_Y_MAX = 25.0
TOP_GROUND_Z = 0.0
BOTTOM_GROUND_Z = -0.035
COPPER_THICKNESS = 0.035


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mm(value: float) -> str:
    return f"{value:.17g}mm"


def folded_slot_rectangles(
    ls1: float, ls2: float, ls3: float, ws: float
) -> list[dict[str, Any]]:
    half_l = ls1 / 2.0
    half_w = ws / 2.0
    outer_y = -(ls2 - half_w)
    leg_y = outer_y + ws
    inner_x = half_l - ls3
    connector_length = ls2 - ws
    leg_length = ls3 - ws
    if min(ls1, ls2, ls3, ws, connector_length, leg_length, inner_x) <= 0:
        raise ValueError("folded-slot dimensions do not form a valid aperture")
    return [
        {"name": "main", "origin_xy": [-half_l, -half_w], "size_xy": [ls1, ws]},
        {
            "name": "right_connector",
            "origin_xy": [half_l - ws, outer_y],
            "size_xy": [ws, connector_length],
        },
        {
            "name": "right_leg",
            "origin_xy": [inner_x, leg_y - ws],
            "size_xy": [leg_length, ws],
        },
        {
            "name": "left_connector",
            "origin_xy": [-half_l, outer_y],
            "size_xy": [ws, connector_length],
        },
        {
            "name": "left_leg",
            "origin_xy": [-half_l + ws, leg_y - ws],
            "size_xy": [leg_length, ws],
        },
    ]


def _create_box_native(
    app: Any,
    name: str,
    origin: list[float],
    sizes: list[float],
    material: str,
    *,
    color: str,
    transparency: float,
    solve_inside: bool,
) -> Any:
    app.oeditor.CreateBox(
        [
            "NAME:BoxParameters",
            "XPosition:=",
            _mm(origin[0]),
            "YPosition:=",
            _mm(origin[1]),
            "ZPosition:=",
            _mm(origin[2]),
            "XSize:=",
            _mm(sizes[0]),
            "YSize:=",
            _mm(sizes[1]),
            "ZSize:=",
            _mm(sizes[2]),
        ],
        [
            "NAME:Attributes",
            "Name:=",
            name,
            "Flags:=",
            "",
            "Color:=",
            color,
            "Transparency:=",
            transparency,
            "PartCoordinateSystem:=",
            "Global",
            "UDMId:=",
            "",
            "MaterialValue:=",
            f'"{material}"',
            "SurfaceMaterialValue:=",
            '""',
            "SolveInside:=",
            solve_inside,
            "ShellElement:=",
            False,
            "ShellElementThickness:=",
            "0mm",
            "IsMaterialEditable:=",
            True,
            "UseMaterialAppearance:=",
            False,
            "IsLightweight:=",
            False,
        ],
    )
    app.modeler.refresh()
    return app.modeler.get_object_from_name(name)


def apply_folded_geometry(
    app: Any,
    *,
    wm: float,
    lm: float,
    ls1: float,
    ls2: float,
    ls3: float,
    ws: float,
) -> dict[str, Any]:
    geometry = {"Wm": wm, "Lm": lm, "Ls1": ls1, "Ls2": ls2, "Ls3": ls3, "Ws": ws}
    if any(not math.isfinite(value) or value <= 0 for value in geometry.values()):
        raise ValueError("all folded-transition dimensions must be positive finite values")
    rectangles = folded_slot_rectangles(ls1, ls2, ls3, ws)

    editor = app.oeditor
    x_position = f"(-{_mm(wm)}/2)"
    for object_name in ("Substrate_3", "Substrate_18"):
        node = editor.GetChildObject(object_name).GetChildObject("CreateBox:1")
        node.SetPropValue("XSize", _mm(wm))
        node.SetPropValue("Position/X", x_position)
    editor.GetChildObject("Substrate_3").GetChildObject("CreateBox:1").SetPropValue(
        "YSize", _mm(lm)
    )
    editor.GetChildObject("Substrate_18").GetChildObject("CreateBox:1").SetPropValue(
        "YSize", f"-{_mm(lm)}"
    )

    deleted = app.modeler.delete(["Substrate_7", "Substrate_9"])
    app.modeler.refresh()
    layers = (
        ("top", "Substrate_7", TOP_GROUND_Z, TOP_GROUND_Z - 0.01),
        ("bottom", "Substrate_9", BOTTOM_GROUND_Z, BOTTOM_GROUND_Z - 0.01),
    )
    layer_reports: dict[str, Any] = {}
    for layer, ground_name, ground_z, cut_z in layers:
        ground = _create_box_native(
            app,
            ground_name,
            [GROUND_X_MIN, GROUND_Y_MIN, ground_z],
            [GROUND_X_MAX - GROUND_X_MIN, GROUND_Y_MAX - GROUND_Y_MIN, COPPER_THICKNESS],
            "copper",
            color="(255 128 64)",
            transparency=0.85,
            solve_inside=False,
        )
        if ground is None:
            raise RuntimeError(f"failed to create {ground_name}")
        operations = []
        for rectangle in rectangles:
            x, y = rectangle["origin_xy"]
            dx, dy = rectangle["size_xy"]
            cut_name = f"StructureBSlot_{layer}_{rectangle['name']}"
            cut = _create_box_native(
                app,
                cut_name,
                [x, y, cut_z],
                [dx, dy, COPPER_THICKNESS + 0.02],
                "vacuum",
                color="(132 132 193)",
                transparency=0.8,
                solve_inside=True,
            )
            if cut is None:
                raise RuntimeError(f"failed to create {cut_name}")
            result = app.modeler.subtract([ground_name], [cut], keep_originals=False)
            if result is not True:
                raise RuntimeError(f"subtract failed for {cut_name}: {result!r}")
            operations.append({"tool": cut_name, **rectangle})
        layer_reports[layer] = {"ground": ground_name, "operations": operations}

    app.modeler.refresh()
    saved = bool(app.save_project())
    if not saved:
        raise RuntimeError("AEDT did not save the folded-transition project")
    return {
        "requested_geometry_mm": geometry,
        "slot_rectangles_mm": rectangles,
        "deleted_original_ground": deleted,
        "layers": layer_reports,
        "setup_names": [str(item) for item in app.get_setups()],
        "saved": saved,
    }

