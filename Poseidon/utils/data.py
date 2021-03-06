#!/usr/bin/env python

"""
File I/O class
A wrapper around various NetCDF libraries, based on 
https://github.com/boutproject/BOUT-dev similar class


NOTE: NetCDF includes unlimited dimensions,
but this library is just for very simple
I/O operations. Educated guesses are made
for the dimensions.

"""

import os
import datetime
import numpy as np


# Record which library to use
library = None

try:
    from netCDF4 import Dataset
    library = "netCDF4"
    has_netCDF = True
except:
    raise ImportError("DataFile: No supported NetCDF modules available")

class DataFile:
    impl = None
    def __init__(self, filename=None, write=False, create=False, format='NETCDF3_CLASSIC'):
        if filename is not None:
            if filename.split('.')[-1] in ('hdf5','hdf','h5'):
                self.impl = DataFile_HDF5(filename=filename, write=write, create=create, format=format)
            else:
                self.impl = DataFile_netCDF(filename=filename, write=write, create=create, format=format)
        elif format == 'HDF5':
            self.impl = DataFile_HDF5(filename=filename, write=write, create=create, format=format)
        else:
            self.impl = DataFile_netCDF(filename=filename, write=write, create=create, format=format)

    def info(self,**kwargs):
        self.impl.info(**kwargs)

    def open(self, filename, write=False, create=False,
             format='NETCDF3_CLASSIC'):
      self.impl.open(filename, write=write, create=create,
                  format=format)
    def close(self):
        self.impl.close()

    def __del__(self):
        self.impl.__del__()

    def __enter__(self):
        return self.impl.__enter__()

    def __exit__(self, type, value, traceback):
        self.impl.__exit__(type, value, traceback)

    def read(self, name, ranges=None):
        """Read a variable from the file."""
        return self.impl.read(name, ranges=ranges)

    def list(self):
        """List all variables in the file."""
        return self.impl.list()

    def dimensions(self, varname):
        """Array of dimension names"""
        return self.impl.dimensions(varname)

    def ndims(self, varname):
        """Number of dimensions for a variable."""
        return self.impl.ndims(varname)

    def size(self, varname):
        """List of dimension sizes for a variable."""
        return self.impl.size(varname)

    def write(self, name, data, **kwargs):
        """Writes a variable to file, making guesses for the dimensions"""
        return self.impl.write(name, data, **kwargs)

    def __getitem__(self, name):
        return self.impl.__getitem__(name)

    def __setitem__(self, key, value):
        self.impl.__setitem__(key, value)
    

class DataFile_netCDF(DataFile):
    handle = None


    def info(self,**kwargs):
        
        for attr, value in kwargs.items(): #add attributes
             setattr(self.handle, attr, value)

    def open(self, filename, write=False, create=False,
             format='NETCDF3_64BIT'):
        if (not write) and (not create):
                self.handle = Dataset(filename, "r")
        elif create:
                self.handle = Dataset(filename, "w", format=format)
        else:
                self.handle = Dataset(filename, "a")
        # Record if writing
        self.writeable = write or create

    def close(self):
        if self.handle is not None:
            self.handle.close()
        self.handle = None

    def __init__(self, filename=None, write=False, create=False,
                 format='NETCDF3_64BIT'):
        if not has_netCDF:
            message = "DataFile: No supported NetCDF python-modules available"
            raise ImportError(message)
        if filename is not None:
            self.open(filename, write=write, create=create, format=format)

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def read(self, name, ranges=None):
        """Read a variable from the file."""
        if self.handle is None: return None

        try:
            var = self.handle.variables[name]
        except KeyError:
            # Not found. Try to find using case-insensitive search
            var = None
            for n in list(self.handle.variables.keys()):
                if n.lower() == name.lower():
                    print("WARNING: Reading '"+n+"' instead of '"+name+"'")
                    var = self.handle.variables[n]
            if var is None:
                return None
        ndims = len(var.dimensions)
        if ndims == 0:
            data = var.getValue()
            return data #[0]
        else:
            if ranges is not None:
                if len(ranges) != 2*ndims:
                    print("Incorrect number of elements in ranges argument")
                    return None

                if ndims == 1:
                        data = var[ranges[0]:ranges[1]]
                elif ndims == 2:
                        data = var[ranges[0]:ranges[1],
                                   ranges[2]:ranges[3]]
                elif ndims == 3:
                        data = var[ranges[0]:ranges[1],
                                   ranges[2]:ranges[3],
                                   ranges[4]:ranges[5]]
                elif ndims == 4:
                        data = var[(ranges[0]):(ranges[1]),
                                   (ranges[2]):(ranges[3]),
                                   (ranges[4]):(ranges[5]),
                                   (ranges[6]):(ranges[7])]
                return data
            else:
                return var[:]

    def __getitem__(self, name):
        var = self.read(name)
        if var is None:
            raise KeyError("No variable found: "+name)
        return var

    def list(self):
        """List all variables in the file."""
        if self.handle is None: return []
        return list(self.handle.variables.keys())

    def keys(self):
        """List all variables in the file."""
        return self.list()

    def dimensions(self, varname):
        """Array of dimension names"""
        if self.handle is None: return None
        try:
            var = self.handle.variables[varname]
        except KeyError:
            raise ValueError("No such variable")
        return var.dimensions

    def ndims(self, varname):
        """Number of dimensions for a variable."""
        if self.handle is None:
           raise ValueError("File not open")
        try:
            var = self.handle.variables[varname]
        except KeyError:
            raise ValueError("No such variable")
        return len(var.dimensions)

    def size(self, varname):
        """List of dimension sizes for a variable."""
        if self.handle is None: return []
        try:
            var = self.handle.variables[varname]
        except KeyError:
            return []

        def dimlen(d):
            dim = self.handle.dimensions[d]
            if dim is not None:
                t = type(dim).__name__
                if t == 'int':
                    return dim
                return len(dim)
            return 0
        return [dimlen(d) for d in var.dimensions]
        
    def write(self, name, data, **kwargs):
        """Writes a variable to file, making guesses for the dimensions"""

        info = kwargs.get('info', False)

        kwargs.pop('info',kwargs)

        if not self.writeable:
            raise Exception("File not writeable. Open with write=True keyword")

        s = np.shape(data)

        # Get the variable type
        t = type(data).__name__

        if t == 'NoneType':
            print("DataFile: None passed as data to write. Ignoring")
            return

        if t == 'ndarray':
            # Numpy type. Get the data type
            t = data.dtype.str

        if t == 'list':
            # List -> convert to numpy array
            data = np.array(data)
            t = data.dtype.str

        if (t == 'int') or (t == '<i8') or (t == 'int64') :
            # NetCDF 3 does not support type int64
            data = np.int32(data)
            t = data.dtype.str

        try:
            # See if the variable already exists
            var = self.handle.variables[name]

            # Check the shape of the variable
            if var.shape != s:
                print("DataFile: Variable already exists with different size: "+ name)
                # Fallthrough to the exception
                raise
        except:
            # Not found, so add.

            # Get dimensions
            defdims = [(),
                       ('x',),
                       ('x','y'),
                       ('x','y','z'),
                       ('t','x','y','z')]

            def find_dim(dim):
                # Find a dimension with given name and size
                size, name = dim

                # See if it exists already
                try:
                    d = self.handle.dimensions[name]

                    # Check if it's the correct size
                    if type(d).__name__ == 'int':
                        if d == size:
                            return name;
                    else:
                        if len(d) == size:
                            return name

                    # Find another with the correct size
                    for dn, d in list(self.handle.dimensions.items()):
                        # Some implementations need len(d) here, some just d
                        if type(d).__name__ == 'int':
                            if d == size:
                                return dn
                        else:
                            if len(d) == size:
                                return dn

                    # None found, so create a new one
                    i = 2
                    while True:
                        dn = name + str(i)
                        try:
                            d = self.handle.dimensions[dn]
                            # Already exists, so keep going
                        except KeyError:
                            # Not found. Create
                            if info:
                                print("Defining dimension "+ dn + " of size %d" % size)
                            try:
                                self.handle.createDimension(dn, size)
                            except AttributeError:
                                # Try the old-style function
                                self.handle.create_dimension(dn, size)
                            return dn
                        i = i + 1

                except KeyError:
                    # Doesn't exist, so add
                    if info:
                        print("Defining dimension "+ name + " of size %d" % size)
                    try:
                        self.handle.createDimension(name, size)
                    except AttributeError:
                        self.handle.create_dimension(name, size)

                return name

            # List of (size, 'name') tuples
            dlist = list(zip(s, defdims[len(s)]))
            # Get new list of variables, and turn into a tuple
            dims = tuple( map(find_dim, dlist) )

            # Create the variable
            var = self.handle.createVariable(name, t, dims)
            for attr, value in kwargs.items(): #add attributes
                 setattr(var, attr, value)

            if var is None:
                raise Exception("Couldn't create variable")

        # Write the data

        try:
            # Some libraries allow this for arrays
            var.assignValue(data)
        except:
            # And some others only this
            var[:] = data
