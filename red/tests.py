"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from django.utils import simplejson as json
from matrix import Matrix, MatrixEncoder, as_matrix


class TestModels(TestCase):
    fixtures = ['test/test_lean_fixture.json']

class TestMatrixConversions(TestCase):
    def setUp(self):
        self.matrix = Matrix(["1"], ["a","b"], {(0,0):1})
        self.as_dict = {"rows": ["a", "b"], "matrix": [[[0, 0], 1]], "width": 1, "cols": ["1"], "height": 2, "__matrix__": True}
        
    def test_matrix_sanity(self):
        self.assertTrue(self.matrix.width==1)
        self.assertTrue(self.matrix.height==2)

    def test_matrix_to_json(self):
        j = json.dumps(self.matrix, cls=MatrixEncoder)
        self.assertEquals(json.loads(j),self.as_dict)

    def test_json_to_matrix(self):
        j = json.dumps(self.matrix, cls=MatrixEncoder)
        self.assertEquals(json.loads(j, object_hook=as_matrix).__dict__, self.matrix.__dict__)


class TestMatrixMath(TestCase):
    def setUp(self):
        def lol_to_dict(m):
            d = {}
            for y, j in enumerate(m):
                for x, i in enumerate(j):
                    if i:
                        d[(x,y)] = i
            return d
    
        self.am = [[0, -1, 2],[4, 11, 2]]
        self.a = Matrix(["a", "b", "c"], ["foo", "bar"], lol_to_dict(self.am))

        self.bm = [[3,-1],[1,2],[6,1]]
        self.b = Matrix(["baz", "batz"], ["l", "o", "l"], lol_to_dict(self.bm))
    
        self.cm = [[11,0],[35,20]]
        self.c = Matrix(["baz", "batz"], ["foo", "bar"], lol_to_dict(self.cm))

    

    def testMatrixMult(self):
        self.assertEquals(self.a.mult(self.b).__dict__, self.c.__dict__)
