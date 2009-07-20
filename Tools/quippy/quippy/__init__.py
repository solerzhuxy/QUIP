"""quippy package

James Kermode <james.kermode@kcl.ac.uk>

Contains python bindings to the libAtoms/QUIP Fortran 95 codes
<http://www.libatoms.org>. """

import sys
assert sys.version_info >= (2,4,0)

import cPickle, atexit, os, numpy, logging
from numpy import *

logging.root.setLevel(logging.WARNING)

try:
   import _quippy

   from oo_fortran import FortranDerivedType, FortranDerivedTypes, fortran_class_prefix, wrap_all

   # Read spec file generated by f90doc and construct wrappers for classes
   # and routines found therein.

   def quippy_cleanup():
      _quippy.system.verbosity_pop()
      _quippy.system.system_finalise()

   _quippy.system.system_initialise(-1)
   _quippy.system.verbosity_push(0)
   atexit.register(quippy_cleanup)

   spec = cPickle.load(open(os.path.join(os.path.dirname(__file__),'quippy.spec')))

   classes, routines, params = wrap_all(_quippy, spec, spec['wrap_modules'], spec['short_names'])

   for name, cls in classes:
      setattr(sys.modules[__name__], name, cls)

   for name, routine in routines:
      setattr(sys.modules[__name__], name, routine)

   sys.modules[__name__].__dict__.update(params)

except ImportError:
   logging.warning('_quippy extension module not available - falling back on pure python version')

   from pupyatoms import *

AtomsReaders = {}
AtomsWriters = {}

import extras
for name, cls in classes:
   try:
      new_cls = getattr(extras, name[len(fortran_class_prefix):])
   except AttributeError:
      new_cls = type(object)(name[len(fortran_class_prefix):], (cls,), {})
      
   setattr(sys.modules[__name__], name[len(fortran_class_prefix):], new_cls)
   FortranDerivedTypes['type(%s)' % name[len(fortran_class_prefix):].lower()] = new_cls


del classes
del routines
del params
del wrap_all
del extras
del fortran_class_prefix
                      
import farray;      from farray import *
import atomslist;   from atomslist import *
import periodic;    from periodic import *
import xyz_netcdf;  from xyz_netcdf import *
import paramreader; from paramreader import *

try:
   import atomeye
except ImportError:
   logging.warning('_atomeye extension module not available - atomeye interface disabled')

import castep, sio2, povray

