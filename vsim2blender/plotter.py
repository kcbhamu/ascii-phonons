import bpy
import yaml
import os
import random
# import sys
from mathutils import Vector
import math
import cmath

# # Modify path to import stuff from other file

# sys.path.insert(0, os.path.abspath(script_directory)+'/..')
from vsim2blender.ascii_importer import import_vsim, cell_vsim_to_vectors


script_directory = os.path.dirname(__file__)
defaults_table_file = script_directory + '/periodic_table.yaml'

def draw_bounding_box(cell):
    a, b, c = cell
    verts = [tuple(x) for x in [(0,0,0), a, a+b, b, c, c+a, c+a+b, c+b]]
    faces = [(0,1,2,3), (0,1,5,4), (1,2,6,5), (2,3,7,6), (3,0,4,7), (4,5,6,7)]
    box_mesh = bpy.data.meshes.new("Bounding Box")
    box_object = bpy.data.objects.new("Bounding Box", box_mesh)
    box_object.location = (0,0,0)
    bpy.context.scene.objects.link(box_object)
    box_mesh.from_pydata(verts,[],faces)
    box_mesh.update(calc_edges=True)

    box_material = bpy.data.materials.new("Bounding Box")
    box_object.data.materials.append(box_material)
    box_material.type = "WIRE"
    box_material.diffuse_color=(0,0,0)
    box_material.use_shadeless = True

def init_material(symbol, col=False, shadeless=True):
    """
    Create material if non-existent. Assign a random colour if none is specified.

    Arguments:
        col: 3-tuple or list containing RGB color. If False, use a random colour.
        shadeless: Boolean; Enable set_shadeless parameter. Informally known as "lights out".
    """

    if symbol in bpy.data.materials.keys():
        return bpy.data.materials[symbol]
    elif not col:
        col = (random.random(), random.random(), random.random())

    material = bpy.data.materials.new(name=symbol)
    material.diffuse_color = col
    material.use_shadeless = shadeless
    return material

def add_atom(position,lattice_vectors,symbol,cell_id=(0,0,0), scale_factor=1.0, reduced=False,
             yaml_file=False,periodic_table=False, name=False):
    """
    Add atom to scene

    Arguments:
        position: 3-tuple, list or vector containing atom coordinates. Units same as unit cell unless reduced=True
        lattice_vectors: 3-tuple or list containing Vectors specifying lattice bounding box/repeating unit
        symbol: chemical symbol. Used for colour and size lookup.
        cell_id: 3-tuple of integers, indexing position of cell in supercell. (0,0,0) is the
            origin cell. Negative values are ok.
        scale_factor: master scale factor for atomic spheres
        reduced: Boolean. If true, positions are taken to be in units of lattice vectors;
            if false, positions are taken to be Cartesian.
        yaml_file: If False, use colours and sizes from default periodic_table.yaml file.
            If a string is provided, this is taken to be a YAML file in same format, values clobber defaults.
        periodic_table: dict containing atomic radii and colours in format
            {'H':{'r': 0.31, 'col': [0.8, 0.8, 0.8]}, ...}. Takes
            priority over yaml_file and default table.
        name: Label for atom object
    """
    if reduced:
        cartesian_position = Vector((0.,0.,0.))
        for i, (position_i, vector) in enumerate(zip(position, lattice_vectors)):
            cartesian_position += (position_i + cell_id[i]) * vector
    else:
        cartesian_position = Vector(position)
        for i, vector in enumerate(lattice_vectors):
            cartesian_position += (cell_id[i] * vector)


    # Get colour. Priority order is 1. periodic_table dict 2. yaml_file 3. defaults_table
    if yaml_file:
        yaml_file_data = yaml.load(open(yaml_file))
    else:
        yaml_file_data = False

    defaults_table = yaml.load(open(defaults_table_file))

    if periodic_table and symbol in periodic_table and 'col' in periodic_table[symbol]:
        col = periodic_table[symbol]['col']
    elif yaml_file_data and symbol in yaml_file_data and 'col' in yaml_file_data[symbol]:
        col = yaml_file_data[symbol]['col']
    else:
        if symbol in defaults_table and 'col' in defaults_table[symbol]:
            col = defaults_table[symbol]['col']
        else:
            col=False        

    # Get atomic radius. Priority order is 1. periodic_table dict 2. yaml_file 3. defaults_table
    if periodic_table and symbol in periodic_table and 'r' in periodic_table[symbol]:
        radius = periodic_table[symbol]['r']
    elif yaml_file_data and symbol in yaml_file_data and 'r' in yaml_file_data[symbol]:
        radius = yaml_file_data[symbol]['r']
    elif symbol in defaults_table and 'r' in defaults_table[symbol]:
        radius = defaults_table[symbol]['r']
    else:
        radius = 1.0


    bpy.ops.mesh.primitive_uv_sphere_add(location=cartesian_position, size=radius * scale_factor)
    atom = bpy.context.object
    if name:
        atom.name = name

    material = init_material(symbol, col=col)
    atom.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    
    return atom

# Computing the positions
#
# Key equation is:
# _u_(jl,t) = Sum over _k_, nu: _U_(j,_k_,nu) exp(i[_k_ _r_(jl) - w(_k_,nu)t])
# [M. T. Dove, Introduction to Lattice Dynamics (1993) Eqn 6.18]
#
# Where nu is the mode identity, w is frequency, _U_ is the
# displacement vector, and _u_ is the displacement of atom j in unit
# cell l. We can break this down to a per-mode displacement and so the
# up-to-date position of atom j in cell l in a given mode visualisation
#
# _r'_(jl,t,nu) = _r_(jl) +  _U_(j,_k_,nu) exp(i[_k_ _r_(jl) - w(_k_,nu) t])
#
# Our unit of time should be such that a full cycle elapses over the
# desired number of frames. 
#
# A full cycle usually lasts 2*pi/w, so let t = frame*2*pi/wN;
# -w t becomes -w 2 pi frame/wN = 2 pi frame / N
#
# _r'_(jl,t,nu) = _r_(jl) + _U_(j,_k_,nu) exp(i[_k_ _r_(jl) - 2 pi (frame#)/N])
#
#

def animate_atom_vibs(atom, qpt, cell_id, displacement_vector, n_frames=30):

    r = atom.location
    for frame in range(n_frames):
        bpy.context.scene.frame_set(frame)
        exponent = cmath.exp( complex(0,1) * (r.dot(qpt) - 2 * math.pi*frame/n_frames)).real
        atom.location = r + Vector([x.real for x in [x * exponent for x in displacement_vector]])
        atom.keyframe_insert(data_path="location",index=-1)

def main(ascii_file=False):

    if not ascii_file:
        ascii_file='gamma_vibs.ascii'

    vsim_cell, positions, symbols, vibs = import_vsim(ascii_file)
    lattice_vectors = cell_vsim_to_vectors(vsim_cell)

    # For now, no supercell, first mode, Gamma point
    vib_index = 10
    cell_id = Vector((0,0,0))
    qpt = Vector((0,0,0))


    # Switch to a new empty scene
    bpy.ops.scene.new(type='EMPTY')
    
    # Draw bounding box #
    draw_bounding_box(lattice_vectors)

    # Draw atoms
    for atom_index, (position, symbol) in enumerate(zip(positions, symbols)):
        atom = add_atom(position,lattice_vectors,symbol,cell_id=(0,0,0), name = '{0}_{1}'.format(atom_index,symbol))
        displacement_vector = vibs[vib_index].vectors[atom_index]
        animate_atom_vibs(atom, qpt, cell_id, displacement_vector)

    # Position camera and render

    camera_x = lattice_vectors[0][0]/2. + lattice_vectors[2][0]/2.
    camera_loc=( camera_x, -3 * max((lattice_vectors[0][0], lattice_vectors[2][2])), lattice_vectors[2][2]/2.)
    bpy.ops.object.camera_add(location=camera_loc,rotation=(math.pi/2,0,0))
    camera = bpy.context.object
    bpy.context.scene.camera = camera

    bpy.context.scene.world = bpy.data.worlds['World']
    bpy.data.worlds['World'].horizon_color = [0.5, 0.5, 0.5]

    bpy.context.scene.render.resolution_x = 1080
    bpy.context.scene.render.resolution_y = 1080
    bpy.context.scene.render.resolution_percentage = 50
    bpy.context.scene.render.use_edge_enhance = True


if __name__=="__main__":
    main('gamma_vibs.ascii')
