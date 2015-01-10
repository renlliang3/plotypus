import numpy as np
from scipy.signal import lombscargle
#from multiprocessing import Pool
from functools import partial

from .utils import pmap


__all__ = [
    'find_period',
    'Lomb_Scargle',
    'rephase',
    'get_phase'
]


def Lomb_Scargle(data, precision,
                 min_period, max_period,
                 min_period_count=1, max_period_count=1,
                 period_jobs=1):
    if min_period_count != 1 or max_period_count != 1:
        raise Exception("Lomb Scargle can only find one period.")
    if period_jobs != 1:
        raise Exception("Lomb Scargle can only use one process.")

    time, mags, *e = data
    scaled_mags = (mags-mags.mean())/mags.std()
    minf, maxf = 2*np.pi/max_period, 2*np.pi/min_period
    freqs = np.arange(minf, maxf, precision)
    pgram = lombscargle(time, scaled_mags, freqs)

    return 2*np.pi/freqs[np.argmax(pgram)]


def conditional_entropy(data, precision,
                        min_period, max_period,
                        min_period_count=1, max_period_count=1,
                        xbins=10, ybins=5, period_jobs=1):
    if min_period_count != 1 or max_period_count != 1:
        raise Exception("Conditional entropy can only find one period.")

    periods = np.arange(min_period, max_period, precision)
    copy = np.ma.copy(data)
    copy[:,1] = (copy[:,1]  - np.min(copy[:,1])) \
       / (np.max(copy[:,1]) - np.min(copy[:,1]))
    partial_job = partial(CE, data=copy, xbins=xbins, ybins=ybins)
    m = partial(pmap, processes=period_jobs)
#    m = map if period_jobs <= 1 else Pool(period_jobs).map
    entropies = list(m(partial_job, periods))

    return periods[np.argmin(entropies)]


def CE(period, data, xbins=10, ybins=5):
    if period <= 0:
        return np.PINF

    phase, mag, err = rephase(data, period)
    bins, *_ = np.histogram2d(phase, mag, [xbins, ybinx], [[0, 1], [0, 1]])
    size = phase.size

#    r = rephase(data, period)
#    bins, *_ = np.histogram2d(r[:,0], r[:,1], [xbins, ybins], [[0,1], [0,1]])
#    size = r.shape[0]

# The following code was once more readable, but much slower.
# Here is what it used to be:
# -----------------------------------------------------------------------
#    return np.sum((lambda p: p * np.log(np.sum(bins[i,:]) / size / p) \
#                             if p > 0 else 0)(bins[i][j] / size)
#                  for i in np.arange(0, xbins)
#                  for j in np.arange(0, ybins)) if size > 0 else np.PINF
# -----------------------------------------------------------------------
# TODO: replace this comment with something that's not old code
    if size > 0:
        # bins[i,j] / size
        divided_bins = bins / size
        # indices where that is positive
        # to avoid division by zero
        arg_positive = divided_bins > 0

        # array containing the sums of each column in the bins array
        column_sums = np.sum(divided_bins, axis=0)
        # array is repeated row-wise, so that it can be sliced by arg_positive
        column_sums = np.repeat(np.reshape(column_sums, (1,-1)), xbins, axis=0)

        # select only the elements in both arrays which correspond to a
        # positive bin
        select_divided_bins = divided_bins[arg_positive]
        select_column_sums  = column_sums[arg_positive]

        # initialize the result array
        A = np.empty((xbins, ybins), dtype=float)
        # store at every index [i,j] in A which corresponds to a positive bin:
        # bins[i,j]/size * log(bins[i,:] / size / (bins[i,j]/size))
        A[ arg_positive] = select_divided_bins \
                         * np.log(select_column_sums / select_divided_bins)
        # store 0 at every index in A which corresponds to a non-positive bin
        A[~arg_positive] = 0

        # return the summation
        return np.sum(A)
    else:
        return np.PINF


def find_periods(data,
                 min_period=0.2, max_period=32.0,
                 min_period_count=1, max_period_count=1,
                 coarse_precision=1e-5, fine_precision=1e-9,
                 periodogram=Lomb_Scargle,
                 period_jobs=1):
    if min_period >= max_period:
        return min_period

    coarse_period = periodogram(data,
                                precision=coarse_precision,
                                min_period=min_period,
                                max_period=max_period,
                                min_period_count=min_period_count,
                                max_period_count=max_period_count,
                                period_jobs=period_jobs)

    if coarse_precision <= fine_precision:
        return coarse_period
    else:
        return periodogram(data,
                           precision=fine_precision,
                           min_period=(coarse_period - coarse_precision),
                           max_period=(coarse_period + coarse_precision),
                           min_period_count=min_period_count,
                           max_period_count=max_period_count,
                           period_jobs=period_jobs)


def rephase(data, period=1.0, shift=0.0, copy=True, col=0):
    rephased = np.ma.array(data, copy=copy)
    rephased[:, col] = get_phase(rephased[:, col], period, shift)

    return rephased


def get_phase(time, period=1.0, shifts=0.0):
    """
    Returns ``time`` after phasing with the given ``period``, and subtracting
    a constant ``shift``.

    Parameters
    ----------
    time : array-like, shape = [n_samples]
        Array of time values to be phased.

    periods : scalar, optional
        Period to phase ``time`` (default 1.0).

    shift : scalar, optional
        Constant shift to subtract from the phases (default 0.0).

    Returns
    -------
    phases : array-like, shape = [n_periods, n_samples]
        Phased ``time`` values.
    """
    return (time / period - shifts) % 1.0
