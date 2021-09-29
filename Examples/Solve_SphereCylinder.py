#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  7 09:25:00 2021

@author: ppycb3

Environment - fenics2019

Example demenstrating how to solve for the field profile for a sphere and
infinitly long cylinder by using the 2D mesh of a circular source inside
a vacuum. These calculated solutions are then compared to the approximate
analytic solutions.
"""
import numpy as np
import dolfin as d
from scipy.special import kn
import matplotlib.pyplot as plt
from Density_profiles import source_wall, vacuum

import sys
sys.path.append("..")
from Main.Meshing_Tools import Meshing_Tools
from Main.Solver_Chameleon import Field_Solver
from Main.Density_Profiles import Density_Profile


# Analytic solutions.
def solution_sphere(alpha, n, source_density, R, r):
    source_field_min = pow(source_density, -1/(n+1))
    R_roll = R - alpha*(1 - source_field_min)/source_density
    sol = []

    for r_i in r:
        if r_i < R_roll:
            sol.append(source_field_min)
        elif r_i > R:
            sol.append(1 - (R/r_i)*np.exp(-(r_i-R)*np.sqrt((n+1)/alpha)))
        else:
            sol.append((source_density/(3*alpha))*((r_i**2)/2
                                                   + (R_roll**3)/r_i
                                                   - 1.5*R_roll**2)
                       + source_field_min)

    return np.array(sol)


def solution_cylinder(alpha, n, source_density, R, r):
    source_field_min = pow(source_density, -1/(n+1))
    sol = []

    for r_i in r:
        if r_i <= R:
            sol.append(source_field_min)
        elif r_i > R:
            sol.append(1+kn(0, r_i*np.sqrt((n+1)/alpha))/np.log(R*np.sqrt(
                (n+1)/alpha)/2))

    return np.array(sol)


# Import mesh and convert from .msh to .xdmf.
R = 0.005
MT = Meshing_Tools(Dimension=2)
filename = "../Saved Meshes/Circle_in_Vacuum_r" + str(R)
mesh, subdomains, boundaries = MT.msh_2_xdmf(filename)


# Set model parameters.
n = 1
alpha = 0.1
ps = 1e17


# Define the density profile of the mesh using its subdomains.
p_sphere = Density_Profile(mesh=mesh, subdomain_markers=subdomains,
                           mesh_symmetry='vertical axis-symmetry',
                           profiles=[source_wall, vacuum, source_wall],
                           degree=0)

p_cylinder = Density_Profile(mesh=mesh, subdomain_markers=subdomains,
                             mesh_symmetry='cylinder slice',
                             profiles=[source_wall, vacuum, source_wall],
                             degree=0)


# Setup problem.
s_sphere = Field_Solver(alpha, n, density_profile=p_sphere)
s_cylinder = Field_Solver(alpha, n, density_profile=p_cylinder)


# Set tolerance on field solutions and solve for above problems.
s_sphere.tol_du = 1e-10
s_cylinder.tol_du = 1e-10

s_sphere.picard()
s_cylinder.picard()


# Plot calculated value against the analytic solution and measure difference.
dx = 0.01
R_max = 1.0 - 1e-4

calculated_field_sphere = []
calculated_field_cylinder = []
N = 100

for t in np.linspace(0, 2*np.pi, N, endpoint=False):
    dr = dx*np.array([np.cos(t), np.sin(t)])

    calculated_field_sphere.append(
        s_sphere.probe_function(function=s_sphere.field,
                                gradient_vector=dr,
                                radial_limit=R_max))

    calculated_field_cylinder.append(
        s_cylinder.probe_function(function=s_cylinder.field,
                                  gradient_vector=dr,
                                  radial_limit=R_max))

X = np.array([i*dx for i in range(N)])
analytic_field_sphere = solution_sphere(alpha, n, ps, R, r=X)
analytic_field_cylinder = solution_cylinder(alpha, n, ps, R, r=X)


# Plot field profiles against analytic solutions.
plt.figure()
plt.ylabel(r"$\hat{\phi}$")
plt.xlabel(r"$\hat{r}$")

for cs in calculated_field_sphere[1:]:
    plt.plot(X, cs, 'k.')

for cc in calculated_field_cylinder[1:]:
    plt.plot(X, cc, 'kx')

plt.plot(X, calculated_field_sphere[0], 'k.',
         label=r"Analytic $\hat{\phi}_{Sphere}$")
plt.plot(X, analytic_field_sphere, 'b-',
         label=r"Calculated $\hat{\phi}_{Sphere}$")
plt.plot(X, calculated_field_cylinder[0], 'kx',
         label=r"Analytic $\hat{\phi}_{Cylinder}$")
plt.plot(X, analytic_field_cylinder, 'r-',
         label=r"Calculated $\hat{\phi}_{Cylinder}$")
plt.legend()


# Plot relative errors between analytic and calculated solutions.
plt.figure()
plt.ylabel(r"$\hat{\phi}$")
plt.xlabel(r"$\hat{r}$")

for cs in calculated_field_sphere[1:]:
    err_sphere = (cs - analytic_field_sphere)/analytic_field_sphere
    plt.plot(X, err_sphere, 'r-')

for cc in calculated_field_cylinder[1:]:
    err_cylinder = (cc - analytic_field_cylinder)/analytic_field_cylinder
    plt.plot(X, err_sphere, 'r-')


err_sphere = (calculated_field_sphere[0]
              - analytic_field_sphere)/analytic_field_sphere

err_cylinder = (calculated_field_cylinder[0]
                - analytic_field_cylinder)/analytic_field_cylinder

plt.plot(X, err_sphere, 'r-', label="Sphere")
plt.plot(X, err_cylinder, 'b-', label="Cylinder")
plt.legend()


# Make image of subdomains of the mesh with zoomed in image of the source.
D = 1e-2
G = 1.15

fig = plt.figure(figsize=(6, 4))

ax_pos_0 = [0.10, 0.10, 0.85, 0.85]
ax_pos_1 = [0.55, 0.65, 0.25, 0.25]

ax0 = fig.add_axes(ax_pos_0)
plt.ylim([-G, G])
plt.xlim([-G, G])
plt.ylabel('Y')
plt.xlabel('X')
d.plot(subdomains)
plt.plot([-D, D, D, -D, -D], [-D, -D, D, D, -D], 'r-')
plt.plot([-D, 0.265], [+D, 1.00], 'r-')
plt.plot([+D, 0.95], [-D, 0.325], 'r-')

ax1 = fig.add_axes(ax_pos_1)
plt.ylim([-D, D])
plt.xlim([-D, D])
d.plot(subdomains)

plt.show()
