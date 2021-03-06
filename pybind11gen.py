#!/usr/bin/env python3
#
# Apache 2 license
#

import argparse
import collections

import CppHeaderParser

MethodHookData = collections.namedtuple('MethodHookData', [
    'methname',
    'in_params', 'ret_names',
    'pre', 'post'
])


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


def _process_method(clsname, meth, hooks, overloaded=False):

    # skip destructor
    if meth.get('destructor', False):
        return []
    
    ret = []
    methname = meth['name']
    parameters = meth['parameters']
    
    # fix types that are enums
    for p in parameters:
        if p.get('enum'):
            p['raw_type'] = p['enum']
            p['type'] = p['enum']
    
    # constructor
    if methname == clsname:
        params = ','.join(p['raw_type'] for p in parameters)
        ret.append('  .def(py::init<%s>())' % params)
    
    else:
        
        pre = []
        post = []
        ret_names = []
        if meth['returns'] != 'void':
            ret_names.append('__ret')
        
        in_params = parameters[:]
        
        modified = False
        
        # data that hooks can modify
        hook_data = MethodHookData(methname,
                                   in_params, ret_names,
                                   pre, post)
        
        for hook in hooks.get('method_hooks', []):
            if hook(clsname, meth, hook_data):
                modified = True
        
        py_methname = hook_data.methname
        
        if modified:
            
            in_args = ''
            if in_params:
                in_args = ', ' + ', '.join('%(type)s %(name)s' % p for p in in_params)
            
            ret.append('  .def("%(py_methname)s", [](%(clsname)s &__inst%(in_args)s) {' % locals())
            
            if pre:
                ret.append('    ' + '; '.join(pre) + ';')
            
            meth_params = ', '.join(p['name'] for p in meth['parameters'])
            
            fnret = 'auto __ret = '
            
            if '__ret' not in ret_names:
                fnret = ''
            
            if not post:
                if ret_names == ['__ret']:
                    ret_names = []
                    fnret = 'return '
            
            ret.append('    %(fnret)s__inst.%(methname)s(%(meth_params)s);' % locals())
            
            if post:
                ret.append('    ' + '; '.join(post) + ';')
                        
            if len(ret_names) == 0:
                pass
            elif len(ret_names) == 1:
                ret.append('    return %s;' % ret_names[0])
            else:
                ret.append('    return std::make_tuple(%s);' % ', '.join(ret_names))
                
            ret.append('  })')
            
        else:
            overload = ''
            if overloaded:
                # overloaded method
                params = ','.join(p['raw_type'] for p in parameters)
                overload = '(%s (%s::*)(%s))' % (
                    meth['returns'],
                    clsname, params
                )
            
            ret.append('  .def("%s", %s&%s::%s)' % (py_methname, overload, clsname, methname))
    
    return ret

def _process_class(cls, hooks):
    
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
                ret += _process_method(clsname, ml[0], hooks)
            else:
                for mh in ml:                    
                    ret += _process_method(clsname, mh, hooks, True)
                
        ret[-1] = ret[-1] + ';'
    
    for e in cls['enums']['public']:
        ret.append('')
        ret += _process_enum(e, clsname=clsname) 
    
    return ret

def process_header(fname, hooks):
    '''Returns a list of lines'''
    
    header = CppHeaderParser.CppHeader(fname)
    output = []
    
    for e in header.enums:
        output += _process_enum(e)
        output.append('')
    
    #for fn in header.functions:
    #    output += _process_fn(fn)
    #    output.append('') 
    
    for cls in sorted(header.classes.values(), key=lambda c: c['line_number']):
        output += _process_class(cls, hooks)
        output.append('')
        
    return output

#
# Hooks
#

# Method hook parameters:
#   clsname: name of the class
#   method: a method dictionary from cppheaderparser
#   in_params: copy of method['parameters']
#   ret_names: variables to return
#   pre: statements to insert before function call
#   post: statements to insert after function call
#   .. returns True if method hook did something 

def _reference_hook(clsname, method, hook_data):
    
    parameters = method['parameters']
    refs = [p for p in parameters if p['reference']]
    if refs:
        hook_data.in_params[:] = [p for p in hook_data.in_params if not p['reference']]
        hook_data.pre.extend('%(raw_type)s %(name)s' % p for p in refs)
        hook_data.ret_names.extend(p['name'] for p in refs)
        return True
        
        

def _ctr_hook(clsname, method, hook_data):
    
    if method['returns'] == 'CTR_Code':
        hook_data.ret_names.remove('__ret')
        hook_data.post.append('CheckCTRCode(__ret)')
        return True


def process_module(module_name, headers, hooks):

    print()
    print('#include <pybind11/pybind11.h>')
    print('namespace py = pybind11;')
    print()
    
    for header in headers:
        print('#include <%s>' % header) # TODO, not usually the actual path
        
    print()
    print('PYBIND11_PLUGIN(%s) {' % module_name)
    print()
    print('    py::module m("%s");' % module_name)
    print()

    for header in headers:
        print('    ' + '\n    '.join(process_header(header, hooks)))
        print()
        
    print('    return m.ptr();')
    print('}')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('module_name')
    parser.add_argument('headers', nargs='+')
    
    args = parser.parse_args()
    
    hooks = {}
    hooks['method_hooks'] = [_reference_hook, _ctr_hook]
    
    process_module(args.module_name, args.headers, hooks)

if __name__ == '__main__':
    main()
