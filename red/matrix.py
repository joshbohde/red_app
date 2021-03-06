import numpy
from scipy import sparse, int8, linalg
from rbco.msexcel import xls_to_excelerator_dict as xls
from itertools import count, takewhile, product, imap, izip
from operator import mul
from django.utils import simplejson as json
from django.core.serializers.json import DjangoJSONEncoder
from collections import defaultdict
import json

import re
def titlecase(s):
    return re.sub(r"[A-Za-z]+('[A-Za-z]+)?",
                  lambda mo: mo.group(0)[0].upper() +
                  mo.group(0)[1:].lower(),
                  s)

def special_round(n):
    if n < 1 and n > 0:
        return 1
    else:
        return int(round(n))

class Matrix(object):
    """
    Matrix with Column and Row Headers
    Empty cells default to 0.
    """
    def __init__(self, cols, rows, matrix, width=None, height=None):
        self.cols = cols
        self.width = width if width else len(cols)
        self.rows = rows
        self.height = height if height else len(rows)
        self.matrix = matrix
        self._max = None

    def to_sparse_matrix(self):
        """
        Convert the JSON formatted matrix to a numpy sparse matrix
        """
        d = sparse.dok_matrix((self.height, self.width), int8)
        for (x,y),v in self.matrix.iteritems():
            # Have to reverse coords, because scipy puts them in (y,x) format
            d[y,x] = v
        return d

    def mult_like(self, other, f):
        """
        Setup functions for multiplication like routines.
        Will pass all locals to f.
        """
        rows = self.rows
        height = self.height
        cols = other.cols
        width = other.width
        matrix = f(**locals())
        return Matrix(cols, rows, matrix, width, height)

    def mult(self, other):
        """
        Matrix multiplication preserving rows and column metadata
        """
        def multiply(self, other, **kwargs):
            a = self.to_sparse_matrix().tocsc()
            b = other.to_sparse_matrix().tocsc()
            return Matrix.from_sparse_matrix(a * b)
        return self.mult_like(other, multiply)

    def get_max(self):
        """
        Find the maximum value of the entire matrix.
        """
        if not(self._max):
            self._max = int(max(self.to_sparse_matrix().itervalues()))
        return self._max
    max = property(get_max)

    def c1(self, other):
        """
        C1 calculation.
        Performed as matrix multiplication, but instead of summing the multiplied pairs,
        find the maximum.
        """
        def c1_routine(self, other, height, width, **kwargs):
            ret = sparse.dok_matrix((height, width))
            a = self.to_sparse_matrix().tolil()
            b = other.to_sparse_matrix().T.tolil()
            for i,j in product(xrange(height), xrange(width)):
                r = a.getrow(i).toarray().tolist()[0]
                c = b.getrow(j).toarray().tolist()[0]
                m =  max(imap(mul, r, c))
                ret[i,j] = m
            return Matrix.from_sparse_matrix(ret)
        return self.mult_like(other, c1_routine)

    def c2(self, other):
        """
        C2 calculation
        Performed as matrix multiplication, but instead of summing the multiplied pairs,
        find the arithmetic mean.
        """
        def c2_routine(self, other, height, width, **kwargs):
            ret = sparse.dok_matrix((height, width))
            a = self.to_sparse_matrix().tolil()
            b = other.to_sparse_matrix().T.tolil()
            for i,j in product(xrange(height), xrange(width)):
                r = a.getrow(i).toarray().tolist()[0]
                c = b.getrow(j).toarray().tolist()[0]
                lol = [float(x*y) for x,y in izip(r,c) if x and y]
                if lol:
                    m =  special_round(numpy.mean(lol))
                    ret[i,j] = m
            return Matrix.from_sparse_matrix(ret)
        return self.mult_like(other, c2_routine)

    def l1(self, rows):
        """
        L1 is L2 applied to only certain rows
        """
        return self.mask(rows).l2()

    def l2(self, rows=None):
        """
        Normalize the matrix s.t. values are between 1 and 5
        If rows is None, then use all of them
        """
        func = lambda i: special_round(5.0 * i / self.max)
        def process(mat):
            matrix = ((k,func(v)) for k,v in mat.matrix.iteritems())
            return Matrix(cols=mat.cols, rows=mat.rows, matrix=dict(matrix),
                          height=mat.height, width=mat.width)
        if rows == None:
            return process(self)
        return process(self.mask(rows))

    def mask(self, row_nums):
        """
        Build a new matrix composed of the rows in row_nums
        """
        row_nums = sorted(row_nums)
        row_lookup = dict((v,n) for n,v in enumerate(row_nums))
        rows = [self.rows[n] for n in row_nums]

        height = len(rows)
        cols = self.cols
        width = self.width
        matrix = dict(((x,row_lookup[y]),v) for ((x,y),v) in self.matrix.iteritems() if y in row_nums)
        return Matrix(cols=cols, rows=rows, matrix=matrix, height=height, width=width)

    @staticmethod
    def run_fever_chart(c, l):
        ret = [[0 for y in xrange(5)] for x in xrange(5)]
        cm = c.to_sparse_matrix()
        lm = l.to_sparse_matrix()
        for k,x in cm.iteritems():
            if x:
                y = lm.get(k)
                if y:
                    ret[5 - int(y)][int(x-1)] += 1
        return ret

    @staticmethod
    def run_report(c, l):
        ret = [[[] for y in xrange(5)] for x in xrange(5)]
        cm = c.to_sparse_matrix()
        lm = l.to_sparse_matrix()
        for k,x in cm.iteritems():
            if x:
                y = lm.get(k)
                if y:
                    ret[5 - int(y)][int(x-1)].append(k)
        return ret
    
    @staticmethod
    def from_sparse_matrix(sp):
        """
        Have to reverse coords, because scipy puts them in (y,x) format
        """
        return dict(((int(x), int(y)), int(v)) for (y,x), v in sparse.dok_matrix(sp).iteritems())

    @staticmethod
    def from_excel_file(filename):
        parsed = xls(filename)[0][1]
        def iter_over_key(f):
            return [titlecase(parsed[f(n)].strip()) for n in 
                    takewhile(lambda n: parsed.has_key(f(n)), count(1))]

        cols = iter_over_key(lambda n: (0,n))
        width = len(cols)

        rows = iter_over_key(lambda n: (n,0))
        height = len(rows)

        def check(r,c):
            return 0 < r <= height and 0 < c <= width

        matrix = dict(((y-1, x-1),v) for (x,y),v in parsed.iteritems() if check(x,y) and v != 0 )
        return Matrix(cols=cols, rows=rows, matrix=matrix, width=width, height=height)

    def __unicode__(self):
        return json.dumps(self, cls=MatrixEncoder)

class MatrixEncoder(DjangoJSONEncoder):
    """
    Encodes a Matrix object as JSON
    """
    def default(self, obj):
        if isinstance(obj, Matrix):
            return {"__matrix__": True,
                    "cols": obj.cols,
                    "width": obj.width,
                    "rows": obj.rows,
                    "height":obj.height,
                    "matrix":obj.matrix.items()}
        return DjangoJSONEncoder.default(self, obj)

def as_matrix(dct):
    if '__matrix__' in dct:
        dct['matrix'] = dict(((tuple(k), v) for k,v in dct['matrix']))
        del dct['__matrix__']
        m =  Matrix(**dict((str(k),v) for k,v in dct.iteritems()))
        return m
    return dct


