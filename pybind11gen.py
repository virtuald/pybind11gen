#!/usr/bin/env python3
#
# Apache 2 license
#

import argparse
import collections
import inspect

import CppHeaderParser


def _process_enum(enum, clsname=None):

    name = enum['name']
    typename = name
    parent = 'm'
    
    if clsname:
        typename = '%s::%s' % (clsname, typename)
        parent = clsname.lower()
    
    ret = ['py::enum_<%s>(%s, "%s")' % (typename, parent, name)]
    
    for v in enum['values']:
        k = v['name']
        ret.append('  .value("%s", %s::%s)' % (k, typename, k))
    
    ret[-1] = ret[-1] + ';'
    return ret


def _process_fn(fn):
    return [] # TODO


def _process_method(clsname, meth, overloaded=False):
    ret = []
    methname = meth['name']
    parameters = meth['parameters']

    # destructor
    if meth.get('destructor', False):
        return ret
    
    # constructor
    if methname == clsname:
        params = ','.join(p['raw_type'] for p in parameters)
        ret.append('  .def(py::init<%s>())' % params)
    
    else:
        # assume reference parameters are 'out' parameters?
        # -> TODO, make this configurable
        refs = [p for p in parameters if p['reference']]
        
        if refs:
            # fix enums
            for p in parameters:
                if p.get('enum'):
                    p['raw_type'] = p['enum']
                    p['type'] = p['enum']
            
            out_vars =  '; '.join('%(raw_type)s %(name)s' % p for p in refs)
            out_names = ', '.join(p['name'] for p in refs)
            in_args = ', '.join('%(type)s %(name)s' % p for p in parameters if not p['reference'])
            if in_args:
                in_args = ', ' + in_args
            
            meth_params = ', '.join(p['name'] for p in meth['parameters'])
            fndef = '  .def("%(methname)s", [](%(clsname)s &__inst%(in_args)s) { %(out_vars)s; auto __ret = __inst.%(methname)s(%(meth_params)s); return std::make_tuple(__ret, %(out_names)s); })' % locals()
            ret.append(fndef)
        else:
            overload = ''
            if overloaded:
                # overloaded method
                params = ','.join(p['raw_type'] for p in parameters)
                overload = '(%s (%s::*)(%s))' % (
                    meth['returns'],
                    clsname, params
                )
            
            ret.append('  .def("%s", %s&%s::%s)' % (methname, overload, clsname, methname))
    
    return ret

def _process_class(cls):
    
    clsname = cls['name']
    varname = clsname.lower()
        
    ret = ['py::class_<%s> %s(m, "%s");' % (clsname, varname, clsname)]
    
    # Collect methods first to determine if there are overloads
    # ... yes, we're ignoring base classes here
    methods = cls['methods']['public']
    if methods:
        ret.append(varname)
        
        # collapse them to find overloads
        meths = collections.OrderedDict()
        for meth in methods:
            meths.setdefault(meth['name'], []).append(meth)
        
        # process it
        for ml in meths.values():
            if len(ml) == 1:
                ret += _process_method(clsname, ml[0])
            else:
                for mh in ml:                    
                    ret += _process_method(clsname, mh, True)
                
        ret[-1] = ret[-1] + ';'
    
    for e in cls['enums']['public']:
        ret.append('')
        ret += _process_enum(e, clsname=clsname) 
    
    return ret

def process_header(fname):
    '''Returns a list of lines'''
    
    header = CppHeaderParser.CppHeader(fname)
    output = []
    
    for e in header.enums:
        output += _process_enum(e)
        output.append('')
    
    #for fn in header.functions:
    #    output += _process_fn(fn)
    #    output.append('') 
    
    for cls in header.classes.values():
        output += _process_class(cls)
        output.append('')
        
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('module_name')
    parser.add_argument('headers', nargs='+')
    
    args = parser.parse_args()

    print('#include <pybind11/pybind11.h>')
    print('namespace py = pybind11;')
    print()
    
    for header in args.headers:
        print('#include <%s>' % header) # TODO, not usually the actual path
        
    print()
    print('PYBIND11_PLUGIN(%s) {' % args.module_name)
    print()
    print('    py::module m("%s");' % args.module_name)
    print()

    for header in args.headers:
        print('    ' + '\n    '.join(process_header(header)))
        print()
        
    print('    return m.ptr();')
    print('}')
        

if __name__ == '__main__':
    main()
