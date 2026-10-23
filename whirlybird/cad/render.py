"""Off-screen VTK renderer for real CAD geometry (tessellated build123d solids).

Run under a virtual display:  xvfb-run -a python build_all.py
"""
from __future__ import annotations

import math

import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

COLORS = {
    "rotor": (0.93, 0.55, 0.20),       # printed rotating hubs (orange)
    "blade": (0.78, 0.80, 0.83),       # aluminium
    "shaft": (0.45, 0.47, 0.50),
    "hardware": (0.25, 0.25, 0.28),
    "bearing": (0.30, 0.55, 0.85),
    "stator": (0.55, 0.60, 0.66),      # stationary printed parts (grey-blue)
    "adapter": (0.42, 0.46, 0.52),
    "tray": (0.35, 0.65, 0.55),
    "tool": (0.60, 0.40, 0.75),
    "roof": (0.55, 0.42, 0.30),
}


def to_polydata(shape, tol=0.08, ang=0.25) -> vtk.vtkPolyData:
    verts, tris = shape.tessellate(tol, ang)
    pts = np.array([[v.X, v.Y, v.Z] for v in verts], dtype=float)
    tri = np.asarray(tris, dtype=np.int64)
    cells = np.hstack([np.full((len(tri), 1), 3, dtype=np.int64), tri]).ravel()
    pd = vtk.vtkPolyData()
    vp = vtk.vtkPoints()
    vp.SetData(numpy_to_vtk(pts, deep=True))
    pd.SetPoints(vp)
    ca = vtk.vtkCellArray()
    ca.SetCells(len(tri), numpy_to_vtkIdTypeArray(cells, deep=True))
    pd.SetPolys(ca)
    return pd


def _actor(pd, color, opacity=1.0, edges=True):
    nrm = vtk.vtkPolyDataNormals()
    nrm.SetInputData(pd)
    nrm.SetFeatureAngle(35)
    nrm.SplittingOn()
    nrm.ConsistencyOn()
    nrm.AutoOrientNormalsOn()
    nrm.Update()
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(nrm.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetColor(*color)
    p.SetOpacity(opacity)
    p.SetAmbient(0.25)
    p.SetDiffuse(0.75)
    p.SetSpecular(0.25)
    p.SetSpecularPower(25)
    out = [a]
    if edges:
        fe = vtk.vtkFeatureEdges()
        fe.SetInputData(pd)
        fe.BoundaryEdgesOn()
        fe.FeatureEdgesOn()
        fe.SetFeatureAngle(35)
        fe.ManifoldEdgesOff()
        fe.NonManifoldEdgesOff()
        em = vtk.vtkPolyDataMapper()
        em.SetInputConnection(fe.GetOutputPort())
        em.ScalarVisibilityOff()
        ea = vtk.vtkActor()
        ea.SetMapper(em)
        ea.GetProperty().SetColor(0.08, 0.08, 0.1)
        ea.GetProperty().SetLineWidth(1.2)
        ea.GetProperty().SetOpacity(min(1.0, opacity + 0.2))
        out.append(ea)
    return out


VIEWS = {
    # name: (direction from target to camera, view-up)
    "iso": ((1.0, -1.25, 0.85), (0, 0, 1)),
    "iso_low": ((1.0, -1.25, -0.55), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)),
    "bottom": ((0, 0, -1), (0, 1, 0)),
    "front": ((0, -1, 0), (0, 0, 1)),
    "side": ((1, 0, 0), (0, 0, 1)),
    "back": ((0, 1, 0), (0, 0, 1)),
    "section": ((0.35, -1.0, 0.25), (0, 0, 1)),
}


def render(items, path, view="iso", size=(1600, 1200), ortho=None, zoom=1.0, bg=(1, 1, 1),
           edges=True, title=None, focus=None):
    """items: list of (shape, color_key_or_rgb, opacity)."""
    ren = vtk.vtkRenderer()
    ren.SetBackground(*bg)
    for shape, col, op in items:
        rgb = COLORS[col] if isinstance(col, str) else col
        for a in _actor(to_polydata(shape), rgb, op, edges):
            ren.AddActor(a)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(*size)
    win.SetMultiSamples(8)
    win.AddRenderer(ren)
    d, up = VIEWS[view] if isinstance(view, str) else view
    d = np.array(d, float)
    d /= np.linalg.norm(d)
    cam = ren.GetActiveCamera()
    bounds = ren.ComputeVisiblePropBounds()
    bctr = np.array([(bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, (bounds[4] + bounds[5]) / 2])
    diag = math.dist(bounds[0::2], bounds[1::2])
    if ortho is None:
        ortho = view in ("top", "bottom", "front", "side", "back")
    cam.SetParallelProjection(bool(ortho))
    cam.SetFocalPoint(*bctr)
    cam.SetPosition(*(bctr + d * diag * 2.5))
    cam.SetViewUp(*up)
    ren.ResetCamera()                       # fits the whole model along the chosen direction
    if focus is not None:                   # then slide the camera to the requested target, keep framing
        f = np.array(focus, float)
        dist = cam.GetDistance()
        cam.SetFocalPoint(*f)
        cam.SetPosition(*(f + d * dist))
    cam.Zoom(zoom)
    ren.ResetCameraClippingRange()
    light = vtk.vtkLight()
    light.SetLightTypeToCameraLight()
    light.SetPosition(0.3, 0.6, 1)
    light.SetIntensity(0.55)
    ren.AddLight(light)
    if title:
        txt = vtk.vtkTextActor()
        txt.SetInput(title)
        txt.GetTextProperty().SetFontSize(26)
        txt.GetTextProperty().SetColor(0.1, 0.1, 0.1)
        txt.SetDisplayPosition(20, size[1] - 45)
        ren.AddActor2D(txt)
    win.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.SetInputBufferTypeToRGB()
    w2i.ReadFrontBufferOff()
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(str(path))
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()
    return path
