#! /usr/bin/env python

"""This module contains code to locate the appropriate PSF library files
to use for a given simulation. It supports the selection of one PSF
"core" file, which is assumed to contain a 3D array of PSFs that is read
into a ``griddedPSFmodel`` instance, as well as a single PSF "wings" file,
which contains a single PSF instance.

For both of these files, once they are identified, they are read in via
the appropriate mechanisms for the data they contain, and the resulting
object is returned.

Author
------

    - Bryan Hilbert

Use
---

    This module can be imported and called as such:
    ::
        from mirage.psf import psf_selction
        library = psf_selection.get_gridded_psf_library('nircam', 'nrcb1',
                                                        'f200w', 'clear',
                                                        'predicted', 0,
                                                        '/path/to/library/')
"""


from copy import copy
from glob import glob
import os

from astropy.io import fits
import numpy as np
from webbpsf.utils import to_griddedpsfmodel

from mirage.utils.constants import NIRISS_PUPIL_WHEEL_FILTERS


def confirm_gridded_properties(filename, instrument, detector, filtername, pupilname,
                               wavefront_error_type, wavefront_error_group, file_path,
                               extname='PRIMARY'):
    """Examine the header of the gridded PSF model file to confirm that
    the properties of the data match those expected.

    Parameters
    ----------
    filename : str
        Base name of the PSF library file to be checked

    instrument : str
        Name of instrument the PSFs are from

    detector : str
        Name of the detector within ```instrument```

    filtername : str
        Name of filter used for PSF library creation

    pupilname : str
        Name of pupil wheel element used for PSF library creation

    wavefront_error_type : str
        Wavefront error. Can be 'predicted' or 'requirements'

    wavefront_error_group : int
        Wavefront error realization group. Must be an integer from 0 - 9.

    file_path : str
        Path pointing to the location of the PSF library

    extname : str
        Name of the extension within ``filename`` to check

    Returns
    -------
    full_filename : str
        Full path and filename if the file properties are as expected.
        None if the properties do not match.
    """
    full_filename = os.path.join(file_path, filename)
    with fits.open(full_filename) as hdulist:
        header = hdulist[extname.upper()].header

    inst = header['INSTRUME']
    try:
        det = header['DETECTOR']
    except KeyError:
        det = header['DET_NAME']
    filt = header['FILTER']
    try:
        pupil = header['PUPIL']
    except KeyError:
        # If no pupil mask value is present, then assume the CLEAR is
        # being used
        if instrument.upper() == 'NIRCAM':
            pupil = 'CLEAR'
        elif instrument.upper() == 'NIRISS':
            pupil = 'CLEARP'

    opd_file = header['OPD_FILE']
    if 'predicted' in opd_file:
        wfe_type = 'predicted'
    elif 'requirements' in opd_file:
        wfe_type = 'requirements'
    realization = header['OPDSLICE']

    # make the check below pass for FGS
    if instrument.lower() == 'fgs':
        pupil = 'N/A'
        pupilname = 'N/A'
        filt = 'N/A'
        filtername = 'N/A'

    if inst.lower() == instrument.lower() and det.lower() == detector.lower() and \
       filt.lower() == filtername.lower() and pupil.lower() == pupilname.lower() and \
       wfe_type == wavefront_error_type.lower() and realization == wavefront_error_group:
        return full_filename
    else:
        return None


def get_gridded_psf_library(instrument, detector, filtername, pupilname, wavefront_error,
                            wavefront_error_group, library_path):
    """Find the filename for the appropriate gridded PSF library and
    read it in to a griddedPSFModel

    Parameters
    ----------
    instrument : str
        Name of instrument the PSFs are from

    detector : str
        Name of the detector within ```instrument```

    filtername : str
        Name of filter used for PSF library creation

    pupilname : str
        Name of pupil wheel element used for PSF library creation

    wavefront_error : str
        Wavefront error. Can be 'predicted' or 'requirements'

    wavefront_error_group : int
        Wavefront error realization group. Must be an integer from 0 - 9.

    library_path : str
        Path pointing to the location of the PSF library

    Returns:
    --------
    library : photutils.griddedPSFModel
        Object containing PSF library

    """
    # First, as a way to save time, let's assume a file naming convention
    # and search for the appropriate file that way. If we find a match,
    # confirm the properties of the file via the header. This way we don't
    # need to open and examine every file in the gridded library, which
    # saves at least a handful of seconds.
    if instrument.lower() == 'fgs':
        default_file_pattern = '{}_{}_fovp*_samp*_npsf*_{}_realization{}.fits'.format(instrument.lower(),
                                                                                        detector.lower(),
                                                                                        wavefront_error.lower(),
                                                                                        wavefront_error_group)
    else:
        default_file_pattern = '{}_{}_{}_{}_fovp*_samp*_npsf*_{}_realization{}.fits'.format(instrument.lower(),
                                                                                        detector.lower(),
                                                                                        filtername.lower(),
                                                                                        pupilname.lower(),
                                                                                        wavefront_error.lower(),
                                                                                        wavefront_error_group)
    default_matches = glob(os.path.join(library_path, default_file_pattern))

    library_file = None
    if len(default_matches) == 1:
        library_file = confirm_gridded_properties(default_matches[0], instrument, detector, filtername,
                                                  pupilname, wavefront_error, wavefront_error_group,
                                                  library_path)

    # If the above search found no matching files, or multiple matching
    # files (based only on filename), or if the matching file's gridded
    # PSF model properties don't match what's expected, then resort to
    # opening and examining all files in the library.
    if library_file is None:
        library_file = get_library_file(instrument, detector, filtername, pupilname,
                                        wavefront_error, wavefront_error_group, library_path)

    print("PSFs will be generated using: {}".format(os.path.basename(library_file)))

    try:
        library = to_griddedpsfmodel(library_file)
    except OSError:
        print("OSError: Unable to open {}.".format(library_file))
    return library


def get_library_file(instrument, detector, filt, pupil, wfe, wfe_group, library_path, wings=False):
    """Given an instrument and filter name along with the path of
    the PSF library, find the appropriate library file to load.

    Parameters
    -----------
    instrument : str
        Name of instrument the PSFs are from

    detector : str
        Name of the detector within ```instrument```

    filt : str
        Name of filter used for PSF library creation

    pupil : str
        Name of pupil wheel element used for PSF library creation

    wfe : str
        Wavefront error. Can be 'predicted' or 'requirements'

     wfe_group : int
        Wavefront error realization group. Must be an integer from 0 - 9.

    library_path : str
        Path pointing to the location of the PSF library

    Returns
    --------
    matches : str
        Name of the PSF library file for the instrument and filtername
    """
    psf_files = glob(os.path.join(library_path, '*.fits'))

    # Create a dictionary of header information for all PSF library files
    # psf_table = {}
    matches = []

    instrument = instrument.upper()
    detector = detector.upper()
    filt = filt.upper()
    pupil = pupil.upper()
    wfe = wfe.lower()

    # handle the NIRISS NRM case
    if pupil == 'NRM':
        pupil = 'MASK_NRM'

    for filename in psf_files:
        header = fits.getheader(filename)
        file_inst = header['INSTRUME'].upper()
        try:
            file_det = header['DETECTOR'].upper()
        except KeyError:
            file_det = header['DET_NAME'].upper()
        file_filt = header['FILTER'].upper()

        try:
            file_pupil = header['PUPIL_MASK'].upper()
        except KeyError:
            # If no pupil mask value is present, then assume the CLEAR is
            # being used
            if file_inst.upper() == 'NIRCAM':
                file_pupil = 'CLEAR'
            elif file_inst.upper() == 'NIRISS':
                try:
                    file_pupil = header['PUPIL'].upper()  # can be 'MASK_NRM'
                except KeyError:
                    file_pupil = 'CLEARP'

        # NIRISS has many filters in the pupil wheel. Webbpsf does
        # not make a distinction, but Mirage does. Adjust the info
        # to match Mirage's expectations
        if file_inst.upper() == 'NIRISS' and file_filt in NIRISS_PUPIL_WHEEL_FILTERS:
            save_filt = copy(file_filt)
            if file_pupil == 'CLEARP':
                file_filt = 'CLEAR'
            else:
                raise ValueError(('Pupil value is something other than '
                                  'CLEARP, but the filter being used is '
                                  'in the pupil wheel.'))
            file_pupil = save_filt

        opd = header['OPD_FILE']
        if 'requirements' in opd:
            file_wfe = 'requirements'
        elif 'predicted' in opd:
            file_wfe = 'predicted'

        file_wfe_grp = header['OPDSLICE']

        # allow check below to pass for FGS
        if instrument.lower() == 'fgs':
            file_filt = 'N/A'
            filt = 'N/A'
            file_pupil = 'N/A'
            pupil = 'N/A'

        if not wings:
            match = (file_inst == instrument and file_det == detector and file_filt == filt and
                     file_pupil == pupil and file_wfe == wfe and file_wfe_grp == wfe_group)
        else:
            match = (file_inst == instrument and file_det == detector and file_filt == filt and
                     file_pupil == pupil and file_wfe == wfe)

        if match:
            matches.append(filename)
        # psf_table[filename] = [file_inst, file_det, file_filt, file_pupil, file_wfe, file_wfe_grp, match]

    # Find files matching the requested inputs
    if len(matches) == 1:
        return matches[0]
    elif len(matches) == 0:
        raise ValueError("No PSF library file found matching requested parameters.")
    elif len(matches) > 1:
        raise ValueError("More than one PSF library file matches requested parameters: {}".format(matches))


def get_psf_wings(instrument, detector, filtername, pupilname, wavefront_error, wavefront_error_group,
                  library_path):
    """Locate the file containing PSF wing image and read them in. The
    idea is that there will only be one file for a given detector/filter/
    pupil/WFE/realization combination. This file will contain a PSF
    sampled at detector resolution and covering some large area in pixels.
    Later, when making the seed image, the appropriate subarray will be
    pulled out of this array for each input source depending on its
    magnitude.

    Parameters
    ----------
    instrument : str
        Name of instrument the PSFs are from

    detector : str
        Name of the detector within ```instrument```

    filtername : str
        Name of filter used for PSF library creation

    pupilname : str
        Name of pupil wheel element used for PSF library creation

    wavefront_error : str
        Wavefront error. Can be 'predicted' or 'requirements'

    wavefront_error_group : int
        Wavefront error realization group. Must be an integer from 0 - 9.

    library_path : str
        Path pointing to the location of the PSF library

    Returns
    -------
    psf_wings : numpy.ndarray
        Array containing the PSF wing data. Note that the outermost row
        and column are not returned, in order to avoid edge effects

    """
    # First, as a way to save time, let's assume a file naming convention
    # and search for the appropriate file that way. If we find a match,
    # confirm the properties of the file via the header. This way we don't
    # need to open and examine every file in the gridded library, which
    # saves at least a handful of seconds.
    default_file_pattern = '{}_{}_{}_{}_fovp*_samp*_{}_realization{}.fits'.format(instrument.lower(),
                                                                                  detector.lower(),
                                                                                  filtername.lower(),
                                                                                  pupilname.lower(),
                                                                                  wavefront_error.lower(),
                                                                                  wavefront_error_group)
    default_matches = glob(os.path.join(library_path, default_file_pattern))

    wings_file = None
    if len(default_matches) == 1:
        wings_file = confirm_gridded_properties(default_matches[0], instrument, detector, filtername,
                                                pupilname, wavefront_error, wavefront_error_group,
                                                library_path, extname='DET_DIST')

    # If the above search found no matching files, or multiple matching
    # files (based only on filename), or if the matching file's gridded
    # PSF model properties don't match what's expected, then resort to
    # opening and examining all files in the library.
    if wings_file is None:
        # Find the file containing the PSF wings
        wings_file = get_library_file(instrument, detector, filtername, pupilname,
                                      wavefront_error, wavefront_error_group, library_path, wings=True)

    print("PSF wings will be from: {}".format(os.path.basename(wings_file)))
    with fits.open(wings_file) as hdulist:
        psf_wing = hdulist['DET_DIST'].data
    # Crop the outer row and column in order to remove any potential edge
    # effects leftover from creation
    psf_wing = psf_wing[1:-1, 1:-1]

    for shape in psf_wing.shape:
        if shape % 2 == 0:
            print(("WARNING: PSF wing file contains an even number of rows or columns. "
                   "These must be even."))
            raise ValueError
    return psf_wing
