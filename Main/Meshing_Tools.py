#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 19 11:06:42 2021

@author: ppycb3

Environment - fenics2019

Tools to produce and modify meshes to be used in simulations.

Notes -
    May want to compare algorithms e.g.
    gmsh.option.setNumber('Mesh.Algorithm3D', 10) is very slow compared
    to default.
"""
import gmsh
import meshio
import numpy as np
import dolfin as d
from functools import partial
geom = gmsh.model.occ


class Meshing_Tools():
    def __init__(self, Dimension):
        self.dim = Dimension
        self.boundaries = []
        self.source = []
        self.refinement_settings = []
        self.source_number = 0
        self.boundary_number = 0
        self.Min_length = 1.3e-6
        return None

    def points_to_surface(self, Points_list):
        '''
        Takes a list of points that define a closed surface and constructs
        thios surface in an open gmsh application.

        Parameters
        ----------
        Points_list : TYPE list
            List containing the points which define the exterior
            of the surface. Each element of the list should

        Returns
        -------
        SurfaceDimTag : TYPE
            DESCRIPTION.

        '''

        if len(Points_list) < 3:
            print("Points_list requires 3-points minium to construct surface.")
            return None

        Pl = []
        Ll = []

        'Set points.'
        for p in Points_list:
            Pl.append(geom.addPoint(p[0], p[1], p[2]))

        'Join points as lines.'
        for i, _ in enumerate(Points_list):
            Ll.append(geom.addLine(Pl[i-1], Pl[i]))

        'Join lines as a closed loop and surface.'
        sf = geom.addCurveLoop(Ll)
        SurfaceDimTag = (2, geom.addPlaneSurface([sf]))
        return SurfaceDimTag

    def points_to_volume(self, Contour_list):
        for Points_list in Contour_list:
            if len(Points_list) < 3:
                print("One or more contours does not have enough points to",
                      "construct a surface (3 min).")
                return None

        L_list = []
        for Points_list in Contour_list:
            'Create data lists.'
            Pl = []
            Ll = []

            'Set points.'
            for p in Points_list:
                Pl.append(geom.addPoint(p[0], p[1], p[2]))

            'Join points as lines.'
            for i, _ in enumerate(Points_list):
                Ll.append(geom.addLine(Pl[i-1], Pl[i]))

            'Join lines as a closed loop and surface.'
            L_list.append(geom.addCurveLoop(Ll))

        VolumeDimTag = geom.addThruSections(L_list)

        "Delete contour lines."
        geom.remove(geom.getEntities(dim=1), recursive=True)

        return VolumeDimTag

    def shape_cutoff(self, shape_DimTags, cutoff_radius=1.0):
        '''
        Applies a radial cutoff to all shapes open in gmsh.

        Parameters
        ----------
        cutoff_radius : TYPE float, optional
            The radial size of the cutoff. Any part of the source that is
            further away from the origin than this radius will be erased.
            The default is 1.0.

        Returns
        -------
        None.

        '''
        # Check for 3D interecting spheres.
        cutoff = [(3, geom.addSphere(xc=0, yc=0, zc=0, radius=cutoff_radius))]
        geom.intersect(objectDimTags=shape_DimTags, toolDimTags=cutoff)
        return None

    def create_subdomain(self, CellSizeMin=0.1, CellSizeMax=0.1, DistMin=0.0,
                         DistMax=1.0, NumPointsPerCurve=1000):
        '''
        Creates a subdomain from the shapes currently open in the gmsh window.
        Shapes already present in previous subdomains will not be added to the
        new one.

        Parameters
        ----------
        CellSizeMin : float, optional
            DESCRIPTION. The default is 0.1.
        CellSizeMax : float, optional
            DESCRIPTION. The default is 0.1.
        DistMin : float, optional
            DESCRIPTION. The default is 0.0.
        DistMax : float, optional
            DESCRIPTION. The default is 1.0.
        NumPointsPerCurve : float, optional
            DESCRIPTION. The default is 1000.

        Returns
        -------
        None.

        '''
        # Save sources, remove duplicates, and update source number.
        self.source.append(geom.getEntities(dim=self.dim))
        del self.source[-1][:self.source_number]
        self.source_number += len(self.source[-1])

        # Check if new entry is empty.
        if self.source[-1]:
            # Save boundary information
            self.boundaries.append(geom.getEntities(dim=self.dim-1))
            del self.boundaries[-1][:self.boundary_number]
            self.boundary_number += len(self.boundaries[-1])

            # Record refinement settings for this subdomain.
            self.refinement_settings.append([CellSizeMin, CellSizeMax, DistMin,
                                             DistMax, NumPointsPerCurve])
        else:
            del self.source[-1]
        return None

    def create_background_mesh(self, CellSizeMin=0.1, CellSizeMax=0.1,
                               DistMin=0.0, DistMax=1.0,
                               NumPointsPerCurve=1000, background_radius=1.0,
                               wall_thickness=None,
                               refine_outer_wall_boundary=False):
        '''
        Takes any dim-dimensional mesh currently in an open gmsh and places
        them inside a circular/spherical vacuum chamber of radius
        'vacuum_radius' and wall thickness 'wall_thickness'.

        Parameters
        ----------
        background_radius : TYPE float, optional
            The radial size of the circle that defines background mesh.
            The default is 1.0.
        wall_thickness : TYPE float, optional
            The width of the vacuum chamber wall. So the total domain size is
            a circle of radius 'background_radius' + 'wall_thickness'.
            The default is 0.1.

        Returns
        -------
        None.

        '''
        # Get source information.
        self.create_subdomain(CellSizeMin, CellSizeMax, DistMin, DistMax,
                              NumPointsPerCurve)

        # Define vacuum and inner wall boundary.
        source_sum = geom.getEntities(dim=self.dim)

        if self.dim == 2:
            background_0 = [(2, geom.addDisk(xc=0, yc=0, zc=0,
                                             rx=background_radius,
                                             ry=background_radius))]
        elif self.dim == 3:
            background_0 = [(3, geom.addSphere(xc=0, yc=0, zc=0,
                                               radius=background_radius))]

        if self.source:
            geom.cut(objectDimTags=background_0, toolDimTags=source_sum,
                     removeObject=True, removeTool=False)

        # Record background as new subdomain.
        self.create_subdomain(CellSizeMin, CellSizeMax, DistMin, DistMax,
                              NumPointsPerCurve)

        # Define wall and outer wall boundary.
        if wall_thickness:
            source_sum = geom.getEntities(dim=self.dim)

            if self.dim == 2:
                wall_0 = [(2, geom.addDisk(
                    xc=0, yc=0, zc=0, rx=background_radius+wall_thickness,
                    ry=background_radius+wall_thickness))]

            elif self.dim == 3:
                wall_0 = [(3, geom.addSphere(
                    xc=0, yc=0, zc=0,
                    radius=background_radius+wall_thickness))]

            geom.cut(objectDimTags=wall_0, toolDimTags=source_sum,
                     removeObject=True, removeTool=False)

            if refine_outer_wall_boundary:
                self.create_subdomain(CellSizeMin, CellSizeMax, DistMin,
                                      DistMax, NumPointsPerCurve)
            else:
                self.create_subdomain()

        geom.synchronize()
        return None

    def generate_mesh(self):
        '''
        Generates a dim-dimensional mesh whose cells are taged such that
        tag = {1, 2, 3} corresponds to the source, vacuum and wall,
        respectively.

        The size of each cell is also controlled by the user such that cells
        that are less than a distance of 'DistMin' from the source and inner
        wall boundaries will have a size of 'SizeMin', while cells with
        distance more than 'DistMax' will have a size 'SizeMax'. For cells
        between these two distances the cell size will increase linearly.
        The diagram below illustrates this.

                           DistMax
                              |
        SizeMax-             /--------
                            /
                           /
                          /
        SizeMin-    o----/
                         |
                      DistMin

        Parameters
        ----------
        SizeMin : TYPE float
            Minimum cell size.
        SizeMax : TYPE float
            Maximum cell size
        DistMin : TYPE, optional
            Distance from boundaries at which cell size starts to increase
            linearly. The default is 0.0.
        DistMax : TYPE, optional
            Distance from boundaries after which cell sizes no long increase
            linearly and are instead fixed to 'SizeMax'. The default is 1.0.
        NumPointsPerCurve : TYPE, optional
            Number of points used to define boundaries in the mesh.
            The default is 1000.
        refine_source_boundary : TYPE, optional
            If true the source boundary will be refine as described above.
            The default is True.
        refine_inner_wall_boundary : TYPE, optional
            If true the inner wall boundary will be refine as described above.
            The default is True.

        Returns
        -------
        None.

        '''
        # Get boundary_type.
        if self.dim == 2:
            boundary_type = "CurvesList"
        elif self.dim == 3:
            boundary_type = "SurfacesList"

        # Group boundaries together and define distence fields.
        i = 0
        for boundary, rf in zip(self.boundaries, self.refinement_settings):
            i += 1
            gmsh.model.mesh.field.add("Distance", i)
            gmsh.model.mesh.field.setNumbers(i, boundary_type,
                                             [b[1] for b in boundary])
            gmsh.model.mesh.field.setNumber(i, "NumPointsPerCurve", rf[4])

        # Define threshold fields.
        j = 0
        for rf in self.refinement_settings:
            j += 1
            gmsh.model.mesh.field.add("Threshold", i+j)
            gmsh.model.mesh.field.setNumber(i+j, "InField", j)
            gmsh.model.mesh.field.setNumber(i+j, "SizeMin", rf[0])
            gmsh.model.mesh.field.setNumber(i+j, "SizeMax", rf[1])
            gmsh.model.mesh.field.setNumber(i+j, "DistMin", rf[2])
            gmsh.model.mesh.field.setNumber(i+j, "DistMax", rf[3])

        # Set mesh resolution.
        gmsh.model.mesh.field.add("Min", i+j+1)
        gmsh.model.mesh.field.setNumbers(i+j+1, "FieldsList",
                                         list(range(i+1, i+j+1)))
        gmsh.model.mesh.field.setAsBackgroundMesh(i+j+1)

        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)

        # Mark physical domains and boundaries.
        for i, source in enumerate(self.source):
            gmsh.model.addPhysicalGroup(dim=self.dim,
                                        tags=[s[1] for s in source], tag=i)

        for i, boundary in enumerate(self.boundaries):
            gmsh.model.addPhysicalGroup(dim=self.dim-1,
                                        tags=[b[1] for b in boundary], tag=i)

        # Generate mesh.
        gmsh.model.mesh.generate(dim=self.dim)
        return None

    def msh_2_xdmf(self, filename):
        '''
        Function converts .msh file (given by filename) and converts it
        into .xdmf and .h5 files which can then be used by dolfin/fenics.

        Returns
        mesh, subdomains
        '''
        # Define output filenames.
        outfile_mesh = filename + "_mesh.xdmf"
        outfile_boundary = filename + "_boundaries.xdmf"

        # read input from infile
        inmsh = meshio.read(filename + ".msh")

        if self.dim == 2:
            # Delete third (obj=2) column (axis=1), striping the z-component.
            outpoints = np.delete(arr=inmsh.points, obj=2, axis=1)

            meshio.write(
                outfile_mesh, meshio.Mesh(
                    points=outpoints,
                    cells=[('triangle', inmsh.get_cells_type('triangle'))],
                    cell_data={'Subdomain': [inmsh.cell_data_dict[
                        'gmsh:physical']['triangle']]},
                    field_data=inmsh.field_data))

            meshio.write(
                outfile_boundary, meshio.Mesh(
                    points=outpoints,
                    cells=[('line', inmsh.get_cells_type('line'))],
                    cell_data={'Boundary': [inmsh.cell_data_dict[
                        'gmsh:physical']['line']]},
                    field_data=inmsh.field_data))

        elif self.dim == 3:
            meshio.write(
                outfile_mesh, meshio.Mesh(
                    points=inmsh.points,
                    cells=[('tetra', inmsh.get_cells_type('tetra'))],
                    cell_data={'Subdomain': [inmsh.cell_data_dict[
                        'gmsh:physical']['tetra']]},
                    field_data=inmsh.field_data))

            meshio.write(
                outfile_boundary, meshio.Mesh(
                    points=inmsh.points,
                    cells=[('triangle', inmsh.get_cells_type('triangle'))],
                    cell_data={'Boundary': [inmsh.cell_data_dict[
                        'gmsh:physical']['triangle']]},
                    field_data=inmsh.field_data))

        # Import Mesh
        mesh = d.Mesh()
        with d.XDMFFile(outfile_mesh) as meshfile:
            meshfile.read(mesh)
            subdomains = d.MeshFunction('size_t', mesh, self.dim)
            meshfile.read(subdomains, "Subdomain")

        with d.XDMFFile(outfile_boundary) as boundaryfile:
            mvc = d.MeshValueCollection("size_t", mesh, self.dim)
            boundaryfile.read(mvc, "Boundary")
            outerwall = d.MeshFunction("size_t", mesh, mvc)

        return mesh, subdomains, outerwall

    def add_shapes(self, shape_1, shape_2):
        if shape_1 and shape_2:
            new_shape, _ = geom.fuse(shape_1, shape_2,
                                     removeObject=False,
                                     removeTool=False)

            'Get rid of unneeded shapes.'
            for shape in shape_1:
                if shape not in new_shape:
                    geom.remove([shape], recursive=True)

            for shape in shape_2:
                if shape not in new_shape:
                    geom.remove([shape], recursive=True)

        else:
            new_shape = shape_1 + shape_2
        return new_shape

    def subtract_shapes(self, shape_1, shape_2):
        if shape_1 and shape_2:
            new_shape, _ = geom.cut(shape_1, shape_2)
        else:
            new_shape = shape_1
            geom.remove(shape_2, recursive=True)

        return new_shape

    def intersect_shapes(self, shape_1, shape_2):
        if shape_1 and shape_2:
            new_shape, _ = geom.intersect(shape_1, shape_2)
        else:
            geom.remove(shape_1 + shape_2, recursive=True)
            new_shape = []
        return new_shape

    def non_intersect_shapes(self, shape_1, shape_2):
        "Make unit test to check this works."
        if shape_1 and shape_2:
            _, fragment_map = geom.fragment(shape_1, shape_2)

            shape_fragments = []
            for s in fragment_map:
                shape_fragments += s

            to_remove = []
            new_shape = []
            while shape_fragments:
                in_overlap = False
                for i, s in enumerate(shape_fragments[1:]):
                    if shape_fragments[0] == s:
                        to_remove.append(shape_fragments.pop(i+1))
                        in_overlap = True

                if in_overlap:
                    shape_fragments.pop(0)
                else:
                    new_shape.append(shape_fragments.pop(0))

            geom.remove(to_remove, recursive=True)

        else:
            geom.remove(shape_1 + shape_2, recursive=True)
            new_shape = []
        return new_shape

    def rotate_x(self, shape, rot_fraction):
        geom.rotate(shape, x=0, y=0, z=0, ax=1, ay=0, az=0,
                    angle=2*np.pi*rot_fraction)
        return shape

    def rotate_y(self, shape, rot_fraction):
        geom.rotate(shape, x=0, y=0, z=0, ax=0, ay=1, az=0,
                    angle=2*np.pi*rot_fraction)
        return shape

    def rotate_z(self, shape, rot_fraction):
        geom.rotate(shape, x=0, y=0, z=0, ax=0, ay=0, az=1,
                    angle=2*np.pi*rot_fraction)
        return shape

    def translate_x(self, shape, dx):
        geom.translate(shape, dx=dx, dy=0, dz=0)
        return shape

    def translate_y(self, shape, dy):
        geom.translate(shape, dx=0, dy=dy, dz=0)
        return shape

    def translate_z(self, shape, dz):
        geom.translate(shape, dx=0, dy=0, dz=dz)
        return shape

    def unity(self, x):
        return x

    def create_disk(self, rx=0.1, ry=0.1):
        Rx = max(self.Min_length, abs(rx))
        Ry = max(self.Min_length, abs(ry))

        if Rx >= Ry:
            new_disk = [(2, geom.addDisk(xc=0, yc=0, zc=0, rx=Rx, ry=Ry))]
        else:
            new_disk = [(2, geom.addDisk(xc=0, yc=0, zc=0, rx=Ry, ry=Rx))]
            geom.rotate(new_disk, x=0, y=0, z=0, ax=0, ay=0, az=1,
                        angle=np.pi/2)
        return new_disk

    def create_rectangle(self, dx=0.2, dy=0.2):
        Dx = max(self.Min_length, abs(dx))
        Dy = max(self.Min_length, abs(dy))

        new_rectangle = [(2, geom.addRectangle(x=-Dx/2, y=-Dy/2, z=0,
                                               dx=Dx, dy=Dy))]
        return new_rectangle

    def create_ellipsoid(self, rx=0.1, ry=0.1, rz=0.1):
        Rx = max(self.Min_length, abs(rx))
        Ry = max(self.Min_length, abs(ry))
        Rz = max(self.Min_length, abs(rz))

        new_sphere = [(3, geom.addSphere(xc=0, yc=0, zc=0, radius=1))]
        geom.dilate(new_sphere, x=0, y=0, z=0, a=Rx, b=Ry, c=Rz)
        return new_sphere

    def create_box(self, dx=0.2, dy=0.2, dz=0.2):
        Dx = max(self.Min_length, abs(dx))
        Dy = max(self.Min_length, abs(dy))
        Dz = max(self.Min_length, abs(dz))

        new_box = [(3, geom.addBox(x=-Dx/2, y=-Dy/2, z=-Dz/2, dx=Dx, dy=Dy,
                                   dz=Dz))]
        return new_box

    def create_cylinder(self, Length=0.1, r=0.1):
        L = max(self.Min_length, abs(Length))
        R = max(self.Min_length, abs(r))

        new_cylinder = [(3, geom.addCylinder(x=0, y=0, z=-L/2, dx=0, dy=0,
                                             dz=L, r=R))]
        return new_cylinder

    def create_cone(self, Length=0.1, r=0.1):
        L = max(self.Min_length, abs(Length))
        R = max(self.Min_length, abs(r))

        new_cone = [(3, geom.addCone(x=0, y=0, z=-L/4,
                                     dx=0, dy=0, dz=L, r1=R, r2=0))]
        return new_cone

    def create_torus(self, r_hole=0.1, r_tube=0.1):
        R_hole = max(self.Min_length, abs(r_hole))
        R_tube = max(self.Min_length, abs(r_tube))

        new_torus = [(3, geom.addTorus(x=0, y=0, z=0, r1=R_hole+R_tube,
                                       r2=R_tube))]
        return new_torus

    def apply_add(self, a, b):
        return partial(self.add_shapes, a, b)()

    def apply_sub(self, a, b):
        return partial(self.subtract_shapes, a, b)()

    def apply_inx(self, a, b):
        return partial(self.intersect_shapes, a, b)()

    def apply_ninx(self, a, b):
        return partial(self.non_intersect_shapes, a, b)()

    def apply_rtx(self, a, b):
        return partial(self.rotate_x, a, b)()

    def apply_rty(self, a, b):
        return partial(self.rotate_y, a, b)()

    def apply_rtz(self, a, b):
        return partial(self.rotate_z, a, b)()

    def apply_tlx(self, a, b):
        return partial(self.translate_x, a, b)()

    def apply_tly(self, a, b):
        return partial(self.translate_y, a, b)()

    def apply_create_disk(self, a, b):
        return partial(self.create_disk, a, b)()

    def apply_create_rectangle(self, a, b):
        return partial(self.create_rectangle, a, b)()

    def apply_create_unit_disk(self):
        return partial(self.create_disk)()

    def apply_create_unit_rectangle(self):
        return partial(self.create_rectangle)()

    def shape_similarity(self, shape_1, shape_2):
        M1 = 0
        for s in shape_1:
            M1 += geom.getMass(dim=s[0], tag=s[1])

        M2 = 0
        for s in shape_2:
            M2 += geom.getMass(dim=s[0], tag=s[1])

        Mf = 0
        if shape_1 and shape_2:
            fragment, _ = geom.fragment(shape_1, shape_2)

            for f in fragment:
                Mf += geom.getMass(dim=f[0], tag=f[1])

        residual = abs(2*Mf - M1 - M2)
        return residual
