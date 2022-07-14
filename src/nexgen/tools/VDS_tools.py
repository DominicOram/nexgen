"""
Tools to write Virtual DataSets
"""
import operator

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, List, Tuple, Union
from functools import reduce
import h5py
import numpy as np

vds_logger = logging.getLogger("nexgen.VDSWriter")


MAX_FRAMES_PER_DATASET = 1000


@dataclass
class Dataset:
    name: str

    # The full shape of the source, regardless of start index
    source_shape: Tuple[int]

    # The start index that we should start copying from
    start_index: int = 0

    # The shape of the destination, including the start_index
    dest_shape: Tuple[int] = None

    def __post_init__(self):
        self.dest_shape = (
            self.source_shape[0] - self.start_index,
            *self.source_shape[1:],
        )

    def __add__(self, x):
        """Returns a dataset that has the same start index and shape as if the two were appended to each other."""
        return Dataset(
            "",
            source_shape=(
                self.source_shape[0] + x.source_shape[0],
                *self.source_shape[1:],
            ),
            start_index=self.start_index + x.start_index,
        )


def find_datasets_in_file(nxdata):
    # Look for the source datasets in the NeXus file.
    # FIXME for now this assumes that the source datasets are always links
    dsets = []
    for k in nxdata.keys():
        if isinstance(nxdata.get(k, getlink=True), h5py.ExternalLink):
            dsets.append(k)
    return dsets


def split_datasets(
    dsets, data_shape: Tuple[int, int, int], start_idx: int = 0
) -> List[Dataset]:
    """Splits the full data shape and start index up into values per dataset,
    given that each dataset has a maximum size.
    """
    if start_idx > data_shape[0]:
        raise ValueError(
            f"Start index {start_idx} must be less than full dataset length {data_shape[0]}"
        )
    if start_idx < 0:
        raise ValueError("Start index must be positive")

    full_frames = data_shape[0]
    result = []
    for dset_name in dsets:
        dset = Dataset(
            name=dset_name,
            source_shape=(min(MAX_FRAMES_PER_DATASET, full_frames), *data_shape[1:]),
            start_index=min(MAX_FRAMES_PER_DATASET, max(start_idx, 0)),
        )
        result.append(dset)
        start_idx -= MAX_FRAMES_PER_DATASET
        full_frames -= MAX_FRAMES_PER_DATASET

    return result


def create_virtual_layout(datasets: List[Dataset], data_type):
    """Create a virtual layout and populate it based on the provided data

    Args:
        datasets (List[Dataset]): The datasets that we're merging
        data_type (Any): The datatype of the data to copy
    """
    full_dataset: Dataset = reduce(operator.add, datasets)
    layout = h5py.VirtualLayout(shape=full_dataset.dest_shape, dtype=data_type)

    dest_start = 0
    for dataset in datasets:
        end = dest_start + dataset.source_shape[0] - dataset.start_index
        vsource = h5py.VirtualSource(
            ".", "/entry/data/" + dataset.name, shape=dataset.source_shape
        )

        layout[dest_start:end, :, :] = vsource[
            dataset.start_index : dataset.source_shape[0], :, :
        ]
        dest_start = end

    return layout


def image_vds_writer(
    nxsfile: h5py.File,
    full_data_shape: Union[Tuple, List],
    start_index: int = 0,
    data_type: Any = np.uint16,
):
    """
    Virtual DataSet writer function for image data.

    Args:
        nxsfile (h5py.File): NeXus file being written.
        full_data_shape (Union[Tuple, List]): Shape of the full dataset, usually defined as (num_frames, *image_size).
        start_index(int): The start point for the source data
        data_type (Any, optional): Dtype. Defaults to np.uint16.
    """
    vds_logger.info("Start creating VDS ...")
    # Where the vds will go
    nxdata = nxsfile["/entry/data"]
    entry_key = "data"
    dset_names = find_datasets_in_file(nxdata)

    datasets = split_datasets(dset_names, full_data_shape, start_index)

    layout = create_virtual_layout(datasets, data_type)

    # Writea Virtual Dataset in NeXus file
    nxdata.create_virtual_dataset(entry_key, layout, fillvalue=-1)
    vds_logger.info("VDS written to NeXus file.")


def vds_file_writer(
    nxsfile: h5py.File,
    datafiles: List[Path],
    data_shape: Union[Tuple, List],
    data_type: Any = np.uint16,
):
    """
    Write a Virtual DataSet _vds.h5 file for image data.

    Args:
        nxsfile (h5py.File): NeXus file being written.
        datafiles (List[Path]): List of paths to source files.
        data_shape (Union[Tuple, List]): Shape of the dataset, usually defined as (num_frames, *image_size).
        data_type (Any, optional): Dtype. Defaults to np.uint16.
    """
    vds_logger.info("Start creating VDS ...")
    # Where the vds will go
    nxdata = nxsfile["/entry/data"]
    entry_key = "data"

    # For every source dataset define its shape and number of frames
    # Once again, it is assumed that the maximum number of frames per dataset is 1000
    frames = (data_shape[0] // 1000) * [1000] + [data_shape[0] % 1000]
    sshape = [(f, *data_shape[1:]) for f in frames]

    # Create virtual layout
    layout = h5py.VirtualLayout(shape=data_shape, dtype=data_type)
    start = 0
    for n, filename in enumerate(datafiles):
        end = start + frames[n]
        vsource = h5py.VirtualSource(
            filename.name, entry_key, shape=sshape[n]
        )  # Source definition
        layout[start:end:1, :, :] = vsource
        start = end

    # Create a _vds.h5 file and add link to nexus file
    s = Path(nxsfile.filename).expanduser().resolve()
    vds_filename = s.parent / f"{s.stem}_vds.h5"
    del s
    with h5py.File(vds_filename, "w") as vds:
        vds.create_virtual_dataset("data", layout, fillvalue=-1)
    nxdata["data"] = h5py.ExternalLink(vds_filename.name, "data")
    vds_logger.info(f"{vds_filename} written and link added to NeXus file.")
