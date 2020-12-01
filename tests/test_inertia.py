try:
    from . import generic as g
except BaseException:
    import generic as g


# tetToTris extracts outward facing triangles
# of a tetrahedron given in this order
#    1
#  / | \
# 0-----2
#  \ | /
#    3

triIdxs = g.np.ravel([[2, 1, 0], [3, 0, 1], [3, 2, 0], [3, 1, 2]])


def tetToTris(tet):
    return g.np.reshape(tet[triIdxs], (-1, 3))


class InertiaTest(g.unittest.TestCase):

    def test_inertia(self):
        t0 = g.np.array([[-0.419575686853, -0.898655215203, -0.127965023308, 0.],
                         [0.712589964872, -0.413418145015, 0.566834172697, 0.],
                         [-0.562291548012, 0.146643245877, 0.813832890385, 0.],
                         [0., 0., 0., 1.]])
        t1 = g.np.array([[0.343159553585, 0.624765521319, -0.701362648103, 0.],
                         [0.509982849005, -0.750986657709, -0.419447891476, 0.],
                         [-0.788770571525, -0.213745370274, -0.57632794673, 0.],
                         [0., 0., 0., 1.]])

        # make sure our transformations are actually still transformations
        assert g.np.abs(g.np.dot(t0, t0.T) - g.np.eye(4)).max() < 1e-10
        assert g.np.abs(g.np.dot(t1, t1.T) - g.np.eye(4)).max() < 1e-10

        c = g.trimesh.primitives.Cylinder(height=10,
                                          radius=1,
                                          sections=720,  # number of slices
                                          transform=t0)
        c0m = c.moment_inertia.copy()
        c0 = g.trimesh.inertia.cylinder_inertia(c.volume,
                                                c.primitive.radius,
                                                c.primitive.height,
                                                c.primitive.transform)

        ct = g.np.abs((c0m / c0) - 1)

        # we are comparing an inertia tensor from a mesh of a cylinder
        # to an inertia tensor from an actual cylinder, so allow for some
        # discretization uncertainty
        assert ct.max() < 1e-3

        # check our principal axis calculation against this cylinder
        # the direction (long axis) of the cylinder should correspond to
        # the smallest principal component of inertia, AKA rotation along
        # the axis, rather than the other two which are perpendicular
        components, vectors = g.trimesh.inertia.principal_axis(
            c.moment_inertia)
        # inferred cylinder axis
        inferred = vectors[components.argmin()]

        # inferred cylinder axis should be close to actual cylinder axis
        axis_test = g.np.allclose(g.np.abs(inferred),
                                  g.np.abs(c.direction))
        assert axis_test

        # make sure Trimesh attribute is plumbed correctly
        assert g.np.allclose(c.principal_inertia_components, components)
        assert g.np.allclose(c.principal_inertia_vectors, vectors)

        # the other two axis of the cylinder should be identical
        assert g.np.abs(g.np.diff(g.np.sort(components)[-2:])).max() < 1e-8

        m = g.get_mesh('featuretype.STL')
        i0 = m.moment_inertia.copy()
        # rotate the moment of inertia
        i1 = g.trimesh.inertia.transform_inertia(
            transform=t0, inertia_tensor=i0)

        # rotate the mesh
        m.apply_transform(t0)
        # check to see if the rotated mesh + recomputed moment of inertia
        # is close to the rotated moment of inertia
        tf_test = g.np.abs((m.moment_inertia / i1) - 1)
        assert tf_test.max() < 1e-6

        # do it again with another transform
        i2 = g.trimesh.inertia.transform_inertia(
            transform=t1, inertia_tensor=i1)
        m.apply_transform(t1)
        tf_test = g.np.abs((m.moment_inertia / i2) - 1)
        assert tf_test.max() < 1e-6

    def test_primitives(self):
        primitives = [g.trimesh.primitives.Cylinder(height=5),
                      g.trimesh.primitives.Box(),
                      g.trimesh.primitives.Sphere(radius=1.23)]
        for p in primitives:
            for i in range(100):
                # check to make sure the analytic inertia tensors are relatively
                # close to the meshed inertia tensor (order of magnitude and
                # sign)
                b = p.to_mesh()
                comparison = g.np.abs(
                    p.moment_inertia - b.moment_inertia)
                c_max = comparison.max() / g.np.abs(p.moment_inertia).max()
                assert c_max < .1

                if hasattr(p.primitive, 'transform'):
                    matrix = g.trimesh.transformations.random_rotation_matrix()
                    p.primitive.transform = matrix
                elif hasattr(p.primitive, 'center'):
                    p.primitive.center = g.np.random.random(3)

    def test_tetrahedron(self):
        # Based on the 'numerical example' of the paper:

        # Explicit Exact Formulas for the 3-D Tetrahedron Inertia Tensor
        # in Terms of its Vertex Coordinates, [F. Tonon, 2004]
        # http://thescipub.com/pdf/jmssp.2005.8.11.pdf

        # set up given vertices
        vertices = g.np.float32([[8.3322, -11.86875, 0.93355],
                                 [0.75523, 5., 16.37072],
                                 [52.61236, 5., -5.3858],
                                 [2., 5., 3.]])

        # set up a simple trimesh tetrahedron
        tris = tetToTris(g.np.int32([0, 1, 2, 3]))
        tm_tet = g.trimesh.Trimesh(vertices, tris)

        # 'ground truth' values from the paper
        # however, there are some minor flaws

        # a small deviation in the last decimal of the mass-centers' x:
        CM_gt = g.np.float32([15.92492, 0.78281, 3.72962])

        # moment of inertia values
        a_mi, b_mi, c_mi = [43520.33257, 194711.28938, 191168.76173]
        # principle inertia values
        a_pi, b_pi, c_pi = [4417.6615, -46343.16662, 11996.20119]

        # NOTE: I guess there is a mistake in the paper
        # b' (Eq. 9e) computes from x and z values
        # c' (Eq. 9f) computes from x and y values
        # therefore the given matrix E_Q (Eq. 2) is not correct
        # b' and c' need to be swapped like this:
        MI_gt = g.np.float32([[a_mi, -c_pi, -b_pi],
                              [-c_pi, b_mi, -a_pi],
                              [-b_pi, -a_pi, c_mi]])

        # check center of mass
        assert g.np.allclose(CM_gt, tm_tet.center_mass)

        # check moment of inertia tensor
        assert g.np.allclose(MI_gt, tm_tet.moment_inertia)

    def test_cube_with_tetras(self):

        # set up a unit cube, vertices in this order:
        #   1-----2
        #  /|    /|
        # 0-+---3 |
        # | 5---+-6
        # |/    |/
        # 4-----7

        vertices = g.np.float32([[-1, -1, 1],
                                 [-1, 1, 1],
                                 [1, 1, 1],
                                 [1, -1, 1],
                                 [-1, -1, -1],
                                 [-1, 1, -1],
                                 [1, 1, -1],
                                 [1, -1, -1]]) * 0.5

        # 6 quad faces for the cube
        quads = g.np.int32([[3, 2, 1, 0],
                            [0, 1, 5, 4],
                            [1, 2, 6, 5],
                            [2, 3, 7, 6],
                            [3, 0, 4, 7],
                            [4, 5, 6, 7]])

        # set up two different tetraherdalizations of a cube
        # using 5 tets (1 in the middle and 4 around)
        tetsA = g.np.int32([[0, 1, 3, 4],
                            [1, 2, 3, 6],
                            [1, 4, 5, 6],
                            [3, 4, 6, 7],
                            [1, 3, 4, 6]])
        # using 6 sets (around the cube diagonal)
        tetsB = g.np.int32([[0, 1, 2, 6],
                            [0, 1, 6, 5],
                            [0, 4, 5, 6],
                            [0, 4, 6, 7],
                            [0, 3, 7, 6],
                            [0, 2, 3, 6]])

        # create a trimesh cube from vertices and faces
        tm_cube = g.trimesh.Trimesh(vertices, quads)

        # https://en.wikipedia.org/wiki/List_of_moments_of_inertia
        # ground truth for a unit cube with side length s = mass m = 1
        # I = 1/6 * m * s^2
        MI_gt = g.np.eye(3) / 6
        assert g.np.allclose(MI_gt, tm_cube.moment_inertia)

        # compare both tetrahedralizations
        # should be equivalent to each other and to the cube
        for tets in [tetsA, tetsB]:
            # create trimesh tets from vertices and triangles
            tm_tets = [g.trimesh.Trimesh(vertices, tetToTris(t)) for t in tets]

            # get mass, center of mass, and moment of inertia for each tet
            Ms = [tm_tet.mass for tm_tet in tm_tets]
            CMs = [tm_tet.center_mass for tm_tet in tm_tets]
            MIs = [tm_tet.moment_inertia for tm_tet in tm_tets]

            # compute total mass and center of mass
            mass = g.np.sum(Ms)
            center_mass = g.np.dot(Ms, CMs)

            # compare with unit cube
            assert g.np.abs(tm_cube.mass - mass) < 1e-6
            assert g.np.allclose(tm_cube.center_mass, center_mass)

            # the moment of inertia tensors for the individual tetrahedra
            # have to be re-assembled, using the parallel-axis-theorem
            # https://en.wikipedia.org/wiki/Parallel_axis_theorem#Tensor_generalization

            E = g.np.eye(3)
            MI = g.np.zeros((3, 3), g.np.float32)
            for i in range(len(tm_tets)):
                R = CMs[i] - center_mass
                MI += MIs[i] + Ms[i] * (g.np.dot(R, R) * E - g.np.outer(R, R))

            assert g.np.allclose(MI_gt, MI)


if __name__ == '__main__':
    g.trimesh.util.attach_to_log()
    g.unittest.main()
