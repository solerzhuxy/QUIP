import sys, cPickle, time, atexit, signal, os.path, numpy, logging
import _libatoms
from oo_fortran import *
from farray import FortranArray, frange

# Read spec file generated by f90doc -f and construct wrappers for classes
# and routines found therein.

_libatoms.system.system_initialise()
atexit.register(_libatoms.system.system_finalise)

spec = cPickle.load(open(os.path.join(os.path.dirname(__file__),'libatoms.spec')))

classes, routines, params = wrap_all(_libatoms, spec,
                                     ['system',
                                      'extendable_str',
                                      'units',
                                      'linearalgebra',
                                      'dictionary',
                                      'table',
                                      'periodictable',
                                      'minimization',
                                      'atoms',
                                      'quaternions',
                                      'rigidbody',
                                      'group',
                                      'constraints',
                                      'thermostat',
                                      'dynamicalsystem',
                                      'paramreader',
                                      'spline',
                                      'sparse',
                                      'clusters',
                                      'structures',
                                      'frametools',
                                      'nye_tensor',
                                      'libatoms',
                                      'libatoms_misc_utils',
                                      'cinoutput',
                                      'topology'],
                                     short_names={'dynamicalsystem':'ds'},
                                     default_init_args={'Atoms': (0, numpy.identity(3))})   

for name, cls in classes:
   setattr(sys.modules[__name__], name, cls)

for name, routine in routines:
   setattr(sys.modules[__name__], name, routine)

sys.modules[__name__].__dict__.update(params)

del classes
del routines
del params
                      
# Add some hand-coded routines to some classes

Dictionary._arrays['_keys'] = Dictionary._arrays['keys']
del Dictionary._arrays['keys']
Dictionary.keys = lambda self: [''.join(self._keys[:,i]).strip() for i in frange(self.n)]

def fdict_get_item(self, k):
   i = self.lookup_entry_i(k)
   if i == -1: 
      raise KeyError('Key "%s" not found ' % k)

   t, s = self.get_type_and_size(k)

   if t == T_NONE:
      raise ValueError('Key %s has no associated value' % k)
   elif t == T_INTEGER:
      v,p = self.get_value_i(k)
   elif t == T_REAL:
      v,p = self.get_value_r(k)
   elif t == T_COMPLEX:
      v,p = self.get_value_c(k)
   elif t == T_CHAR:
      v,p = self.get_value_s(k)
      v = v.strip()
   elif t == T_LOGICAL:
      v,p = self.get_value_l(k)
   elif t == T_INTEGER_A:
      v,p = self.get_value_i_a(k,s)
   elif t == T_REAL_A:
      v,p = self.get_value_r_a(k,s)
   elif t == T_COMPLEX_A:
      v,p = self.get_value_c_a(k,s)
   elif t == T_CHAR_A:
      a,p = self.get_value_s_a(k,s)
      v = [''.join(line).strip() for line in a]
   elif t == T_LOGICAL_A:
      v,p = self_get_value_l_a(k,s)
   else:
      raise ValueError('Unsupported dictionary entry type %d' % t)

   return v

Dictionary.__getitem__ = fdict_get_item
del fdict_get_item

def fdict_set_item(self, k, v):
   if type(v) == type(0):
      self.set_value_i(k,v)
   elif type(v) == type(0.0):
      self.set_value_r(k,v)
   elif type(v) == type(0j):
      self.set_value_c(k,v)
   elif type(v) == type(''):
      self.set_value_s(k,v)
   elif type(v) == type(True):
      self.set_value_l(k,v)
   elif hasattr(v, '__iter__'):
      v0 = v[0]
      if type(v0) == type(0):
         self.set_value_i_a(k,v)
      elif type(v0) == type(0.0):
         self.set_value_r_a(k,v)
      elif type(v0) == type(0j):
         self.set_value_c_a(k,v)
      elif type(v0) == type(''):
         self.set_value_s_a(k,numpy.array(v))
      elif type(v0) == type(True):
         self.set_value_l_a(k,v)
   else:
      raise ValueError('Unsupported dictionary entry type %s' % v)

Dictionary.__setitem__ = fdict_set_item
del fdict_set_item

from dictmixin import DictMixin, MakeFullDict
MakeFullDict(Dictionary)

Dictionary.__repr__ = lambda self: 'Dictionary(%s)' % DictMixin.__repr__(self)


class FrameReader(object):
   """Read-only access to an XYZ or NetCDF trajectory. The file is opened
   and then read lazily as frames are asked for. Supports list-like interface:

   fr = FrameReader('foo.xyz')
   at1 = fr[0]      # First frame
   at2 = fr[-1]     # Last frame
   ats = fr[0:10:3] # Every third frame between 0 and 10
   ats = [ a for a in fr if a.n == 100 ]  # Only frames with exactly 100 atoms
"""
   def __init__(self, source, start=0, stop=-1, step=None, count=None):
      self.cio = CInOutput(source)
      self.cio.query()
      if count is not None:
         self.frames = slice(count)
      else:
         self.frames = slice(start,stop,step)

   def __del__(self):
      self.cio.close()

   def __len__(self):
      return len(range(*self.frames.indices(self.cio.n_frame)))

   def __getitem__(self, frame):
      start, stop, step = self.frames.indices(self.cio.n_frame)

      if isinstance(frame, int):
         if frame < 0: frame = frame + (stop - start)
         if start + frame >= stop:
            raise ValueError("frame %d out of range %d" % (start + frame, stop))
         return self.cio.read(start+frame)

      elif isinstance(frame, slice):
         allframes = range(start, stop, step)
         subframes = [ allframes[i] for i in range(*frame.indices(len(allframes))) ]
         print subframes
         return [ self.cio.read(f) for f in subframes ]
      else:
         raise TypeError('frame should be either an integer or a slice')

   def __iter__(self):
      for frame in range(*self.frames.indices(self.cio.n_frame)):
         yield self.cio.read(frame)
      raise StopIteration

   def __reversed__(self):
      for frame in reversed(range(*self.frames.indices(self.cio.n_frame))):
         yield self.cio.read(frame)
      raise StopIteration


def write_atoms(self, target, append=True):
   "Write atoms object to an XYZ or NetCDF file."
   cio = CInOutput(target, OUTPUT, append)
   try:
      cio.write(self)
   finally:
      cio.close()

Atoms.write = write_atoms
del write_atoms

def read_atoms(cls, source, frame=0):
   """Read a single frame from an XYZ or NetCDF file, then close the file.
   This is a classmethod so should be called as at = Atoms.read(source)."""
   at, = ( FrameReader(source, start=frame, count=1) )
   return at

Atoms.read  = classmethod(read_atoms)
del read_atoms


def show_atoms(self, property=None):
   """Show this atoms object in AtomEye."""
   import atomeye
   if atomeye.__window_id is None:
      atomeye.start()
   atomeye.set_atoms(self)
   if property is not None: 
      atomeye.aux_property_coloring(property)

Atoms.show = show_atoms
del show_atoms

def atoms_update_hook(self):
   # Remove existing pointers
   if hasattr(self, '_props'):
      for prop in self._props:
         try:
            delattr(self, prop)
         except AttributeError:
            pass

   type_names = {PROPERTY_INT: "integer",
                 PROPERTY_REAL: "real",
                 PROPERTY_STR: "string",
                 PROPERTY_LOGICAL: "logical"}

   self._props = {}
   for prop,(ptype,col_start,col_end) in self.properties.iteritems():
      prop = prop.lower()
      self._props[prop] = (ptype,col_start,col_end)
      doc = "%s : %s property with %d %s" % (prop, type_names[ptype], col_end-col_start+1, 
                                             {True:"column",False:"columns"}[col_start==col_end])
      if ptype == PROPERTY_REAL:
         if col_end == col_start:
            setattr(self, prop, FortranArray(self.data.real[col_start,1:self.n],doc))
         else:
            setattr(self, prop, FortranArray(self.data.real[col_start:col_end,1:self.n],doc))
      elif ptype == PROPERTY_INT:
         if col_end == col_start:
            setattr(self, prop, FortranArray(self.data.int[col_start,1:self.n],doc))
         else:
            setattr(self, prop, FortranArray(self.data.int[col_start:col_end,1:self.n],doc))
      elif ptype == PROPERTY_STR:
         if col_end == col_start:
            setattr(self, prop, FortranArray(self.data.str[:,col_start,1:self.n],doc))
         else:
            setattr(self, prop, FortranArray(self.data.str[:,col_start:col_end,1:self.n],doc))
      elif ptype == PROPERTY_LOGICAL:
         if col_end == col_start:
            setattr(self, prop, FortranArray(self.data.logical[col_start,1:self.n],doc))
         else:
            setattr(self, prop, FortranArray(self.data.logical[col_start:col_end,1:self.n],doc))
      else:
         raise ValueError('Bad property type :'+str(self.properties[prop]))

Atoms.update_hook = atoms_update_hook
del atoms_update_hook

