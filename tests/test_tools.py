import time
from pathlib import Path

import pint

import nexgen

ureg = pint.UnitRegistry()


def test_cif2nxs():
    assert nexgen.imgcif2mcstas([0, 0, 0]) == (0, 0, 0)
    assert nexgen.imgcif2mcstas([1, 0, 0]) == (-1, 0, 0)
    assert nexgen.imgcif2mcstas([0, 1, 0]) == (0, 1, 0)
    assert nexgen.imgcif2mcstas([0, 0, 1]) == (0, 0, -1)


def test_get_filename_template():
    # Check filename from _master.h5 file
    fn = nexgen.get_filename_template(Path("File_01_master.h5"))
    assert type(fn) is str
    assert fn == "File_01_%06d.h5"
    assert fn % 1 == "File_01_000001.h5"
    # Check filename from .nxs file
    fn = nexgen.get_filename_template(Path("File_02.nxs"))
    assert type(fn) is str
    assert fn == "File_02_%06d.h5"
    assert fn % 1 == "File_02_000001.h5"


def test_get_nexus_filename():
    # Check nexus filename from meta
    nxs = nexgen.get_nexus_filename(Path("File_01_meta.h5"))
    assert nxs.as_posix() == "File_01.nxs"
    # Check nexus filename from datafile
    nxs = nexgen.get_nexus_filename(Path("File_02_0001.h5"))
    assert nxs.as_posix() == "File_02.nxs"


def test_split_arrays():
    assert nexgen.split_arrays("imgcif", ["phi"], [1, 0, 0]) == {"phi": (-1, 0, 0)}
    two_axes = nexgen.split_arrays("mcstas", ["omega", "phi"], [1, 0, 0, 0, 1, 0])
    assert two_axes["omega"] == (1, 0, 0) and two_axes["phi"] == (0, 1, 0)
    assert (
        len(
            nexgen.split_arrays(
                "mcstas", ["omega", "phi", "chi"], [1, 0, 0, 0, 1, 0, 0, 0, 1]
            )
        )
        == 3
    )


def test_iso_timestamps():
    assert nexgen.get_iso_timestamp(None) is None
    # Check that no exceptions are raised when passing a time.time() object
    assert nexgen.get_iso_timestamp(time.time())


def test_units_of_length():
    assert nexgen.units_of_length("1.5m") == ureg.Quantity(1.5, "m")
    # Check that a dimensionless unit defaults to mm
    assert nexgen.units_of_length(100) == ureg.Quantity(100, "m")
    # Check conversion to base units
    assert nexgen.units_of_length("5cm", True) == ureg.Quantity(0.05, "m")
    assert nexgen.units_of_length("1in", True) == ureg.Quantity(0.0254, "m")


def test_units_of_time():
    assert nexgen.units_of_time("0.05s") == ureg.Quantity(0.05, "s")
    # Check that a dimensionless value deafults to seconds
    assert nexgen.units_of_time(1) == ureg.Quantity(1, "s")
    # Check conversion to base units
    assert nexgen.units_of_time("20ms") == ureg.Quantity(0.02, "s")
