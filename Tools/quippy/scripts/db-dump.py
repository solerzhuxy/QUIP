import sys
import optparse

import numpy as np

from ase.db import connect
from ase.db.cli import plural, cut, Formatter

from quippy.io import dict2atoms, AtomsWriter

class FullFormatter(Formatter):
    def __init__(self, cols, sort):
        self.sort = sort
        
        self.columns = ['id', 'age', 'user', 'formula', 'calc',
                        'energy', 'fmax', 'pbc', 'size', 'keywords',
                        'charge', 'mass', 'fixed', 'smax', 'magmom']
        
        if cols is not None:
            if cols[0] == '+':
                cols = cols[1:]
            elif cols[0] != '-':
                self.columns = []
            for col in cols.split(','):
                if col[0] == '-':
                    self.columns.remove(col[1:])
                else:
                    self.columns.append(col.lstrip('+'))
        
        self.funcs = []
        for col in self.columns:
            f = getattr(self, col, None)
            if f is None:
                f = self.keyval_factory(col)
            self.funcs.append(f)

    def keyval_factory(self, key):
        def keyval_func(d):
            value = d.key_value_pairs.get(key, '(none)')
            return str(value)
        return keyval_func

    def format(self, dcts, uniq=False):
        table = [self.columns]
        widths = [0 for col in self.columns]
        signs = [1 for col in self.columns]  # left or right adjust
        ids = []
        fd = sys.stdout
        for dct in dcts:
            row = []
            for i, f in enumerate(self.funcs):
                try:
                    s = f(dct)
                except AttributeError:
                    s = ''
                else:
                    if isinstance(s, int):
                        s = '%d' % s
                    elif isinstance(s, float):
                        s = '%.3f' % s
                    else:
                        signs[i] = -1
                    if len(s) > widths[i]:
                        widths[i] = len(s)
                row.append(s)
            table.append(row)
            ids.append(dct.id)
        widths = [w and max(w, len(col))
                  for w, col in zip(widths, self.columns)]
        
        if self.sort:
            headline = table.pop(0)
            n = self.columns.index(self.sort)
            table.sort(key=lambda row: row[n])
            table.insert(0, headline)

        if uniq:
            uniq_table = []
            for row in table:
                if len(uniq_table) > 0 and row == uniq_table[-1]:
                    continue
                uniq_table.append(row)
            table = uniq_table
            
        for row in table:
            fd.write('|'.join('%*s' % (w * sign, s)
                              for w, sign, s in zip(widths, signs, row)
                              if w > 0))
            fd.write('\n')
        return ids 
    
def run(opt, args, verbosity):
    con = connect(args.pop(0))
    if args:
        if len(args) == 1 and args[0].isdigit():
            expressions = int(args[0])
        else:
            expressions = ','.join(args)
    else:
        expressions = []

    if opts.count:
        opts.limit = 0

    rows = con.select(expressions, verbosity=verbosity, limit=opts.limit)

    if opts.count:
        n = 0
        for row in rows:
            n += 1
        print('%s' % plural(n, 'row'))
        return

    dcts = list(rows)

    if len(dcts) > 0:
        if opts.include_all or opts.list_columns:
            keys = []
            for dct in dcts:
                for key in dct.key_value_pairs.keys():
                    if key not in keys:
                        keys.append(key)
            opt.columns = ','.join(['+'+key for key in keys])
            
        f = FullFormatter(opts.columns, opts.sort)
        if verbosity > 1 or opt.list_columns:
            for col in f.columns:
                if not opt.list_columns:
                    print 'COLUMN',
                print col
            if opt.list_columns:
                return
            
        if verbosity >= 1:
            f.format(dcts, uniq=opts.uniq)

        if opts.extract is not None:
            if '%' not in opts.extract:
                writer = AtomsWriter(opts.extract)
            for i, dct in enumerate(dcts):
                if '%' in opts.extract:
                    filename = opts.extract % i
                    writer = AtomsWriter(filename)
                at = dict2atoms(dct)
                if verbosity > 1:
                    print 'Writing config %d %r to %r' % (i, at, writer)
                writer.write(at)

parser = optparse.OptionParser(
    usage='Usage: %prog db-name [selection] [options]',
    description='Print a formatted table of data from an ase.db database')

add = parser.add_option
add('-v', '--verbose', action='store_true', default=False)
add('-q', '--quiet', action='store_true', default=False)
add('-n', '--count', action='store_true',
    help='Count number of selected rows.')
add('-C', '--list-columns', action='store_true', default=False,
    help='Print list of available columns and exit.')
add('-c', '--columns', metavar='col1,col2,...',
    help='Specify columns to show.  Precede the column specification ' +
    'with a "+" in order to add columns to the default set of columns.  ' +
    'Precede by a "-" to remove columns.')
add('-a', '--include-all', action='store_true', default=False,
    help='Include columns for all key/value pairs in database.')
add('-s', '--sort', metavar='column',
    help='Sort rows using column.  Default is to sort after ID.')
add('-u', '--uniq', action='store_true',
    help='Suppress printing of duplicate rows.')
add('-x', '--extract', metavar='filename',
    help='''Extract matching configs and save to file(s). Use a filename containing a
"%" expression for multiple files labelled by an index starting from 0,
e.g. "file-%03d.xyz".''')
add('--limit', type=int, default=500, metavar='N',
    help='Show only first N rows (default is 500 rows).  Use --limit=0 ' +
    'to show all.')

opts, args = parser.parse_args()
verbosity = 1 - opts.quiet + opts.verbose

try: 
    run(opts, args, verbosity)
except Exception as x:
    if verbosity < 2:
        print('{0}: {1}'.format(x.__class__.__name__, x.message))
        sys.exit(1)
    else:
        raise


