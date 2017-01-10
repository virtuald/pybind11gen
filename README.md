pybind11gen
===========

Pure python pybind11 bindings generator that uses CppHeaderParser to parse C++
code and generate pybind11 compatible output.

At the moment this is not anything near a complete solution, but it gets you
99% of the way. Maybe in the future it'll be better. Or not. Make pull requests
and let's see where it goes.

Notes
-----

* Doesn't generate a complete module, just the hard part (function declarations and enums)

Install
-------

    git clone https://github.com/virtuald/pybind11gen.git
    cd pybind11gen
    pip install -r requirements.txt


Usage
-----

    ./pybind11gen.py header1.h header2.h...

License
=======

Apache 2

Author
======

Dustin Spicuzza (dustin@virtualroadside.com)