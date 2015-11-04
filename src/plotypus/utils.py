from os import makedirs
from os.path import basename, join, isdir
from sys import stderr
from multiprocessing import Pool
import numbers
from numpy import absolute, concatenate, isscalar, median, resize

__all__ = [
    'verbose_print',
    'pmap',
    'make_sure_path_exists',
    'valid_basename',
    'get_signal',
    'get_noise',
    'colvec',
    'mad',
    'autocorrelation'
]


def verbose_print(message, *, operation, verbosity):
    """verbose_print(message, *, operation, verbosity)

    Prints *message* to stderr only if the given *operation* is in the list
    *verbosity*. If "all" is in *verbosity*, all operations are printed.

    **Parameters**

    message : str
        The message to print.
    operation : str
        The type of operation being performed.
    verbosity : [str] or None
        The list of operations to print *message* for. If "all" is contained
        in the list, then all operations are printed. If None, no operation is
        printed.

    **Returns**

    None
    """
    if (verbosity is not None) and ((operation in verbosity) or
                                    ("all"     in verbosity)):
        print(message, file=stderr)


def pmap(func, args, processes=None, callback=lambda *_, **__: None, **kwargs):
    """pmap(func, args, processes=None, callback=do_nothing, **kwargs)

    Parallel equivalent of ``map(func, args)``, with the additional ability of
    providing keyword arguments to func, and a callback function which is
    applied to each element in the returned list. Unlike map, the output is a
    non-lazy list. If *processes* is 1, no thread pool is used.

    **Parameters**

    func : function
        The function to map.
    args : iterable
        The arguments to map *func* over.
    processes : int or None, optional
        The number of processes in the thread pool. If only 1, no thread pool
        is used to avoid useless overhead. If None, the number is chosen based
        on your system by :class:`multiprocessing.Pool` (default None).
    callback : function, optional
        Function to call on the return value of ``func(arg)`` for each *arg*
        in *args* (default do_nothing).
    kwargs : dict
        Extra keyword arguments are unpacked in each call of *func*.

    **Returns**

    results : list
        A list equivalent to ``[func(x, **kwargs) for x in args]``.
    """
    ######################
    ## Input Validation ##
    ######################
    # processes=None is a special case, and avoids all the following checks
    if (processes is not None):
        # processes must be scalar, not an array, list, etc
        if not isscalar(processes):
            raise TypeError("Number of processes must be scalar, not '{}'"
                            .format(processes))
        # processes must be an integer
        elif not isinstance(processes, numbers.Integral):
            raise TypeError("Number of processes must be an integer, not '{}'"
                            .format(processes))
        # processes must be at least 1
        elif processes < 1:
            raise TypeError("Number of processes must be positive, not '{}'"
                            .format(processes))

    # if only one process is used, avoid the overhead of a thread pool, while
    # emulating the behavior of a `multiprocessing.apply_async`
    if processes is 1:
        # initialize a list of results
        results = []
        # map the function over the arguments,
        # run the callback function on each result,
        # and append the results to a list
        for arg in args:
            result = func(arg, **kwargs)
            results.append(result)
            callback(result)
        # return the list of results
        return results
    # if more than one process is used, use a thread pool
    else:
        # create a thread pool with the number of processes specified,
        # or use the number of CPUs if processes=None
        with Pool(processes) as p:
            # create a list of futures, holding the results of calling the
            # function on each argument
            results = [p.apply_async(func, (arg,), kwargs, callback)
                       for arg in args]
            # evaluate each of the results and store them in a list,
            # return the list
            return [result.get() for result in results]


def make_sure_path_exists(path):
    """make_sure_path_exists(path)

    Creates the supplied *path* if it does not exist.
    Raises *OSError* if the *path* cannot be created.

    **Parameters**

    path : str
        Path to create.

    **Returns**

    None
    """
    try:
        makedirs(path)
    except OSError:
        if not isdir(path):
            raise


def valid_basename(s):
    """valid_basename(s)

    Predicate function to check if the string *s* is a valid basename, meaning
    it is both a valid filename, and does not contain a directory.

    **Parameters**

    s : str

    **Returns**

    is_valid : bool
    """
    return s == basename(s)


def get_signal(data):
    """get_signal(data)

    Returns all of the values in *data* that are not outliers.

    **Parameters**

    data : masked array

    **Returns**

    signal : array
        Non-masked values in *data*.
    """
    return data[~data.mask].data.reshape(-1, data.shape[1])


def get_noise(data):
    """get_noise(data)

    Returns all identified outliers in *data*.

    **Parameters**

    data : masked array

    **Returns**

    noise : array
        Masked values in *data*.
    """
    return data[data.mask].data.reshape(-1, data.shape[1])


def colvec(X):
    """colvec(X)

    Converts a row-vector *X* into a column-vector.

    **Parameters**

    X : array-like, shape = [n_samples]

    **Returns**

    out : array-like, shape = [n_samples, 1]
    """
    return resize(X, (X.shape[0], 1))


def rowvec(X):
    """rowvec(X)

    Converts a column-vector *X* into a row-vector.

    **Parameters**

    X : array-like, shape = [n_samples, 1]

    **Returns*

    out : array-like, shape = [n_samples]
    """
    return resize(X, (1, X.shape[0]))[0]


def mad(data, axis=None):
    """mad(data, axis=None)

    Computes the median absolute deviation of *data* along a given *axis*.
    See `link <https://en.wikipedia.org/wiki/Median_absolute_deviation>`_ for
    details.

    **Parameters**

    data : array-like

    **Returns**

    mad : number or array-like
    """
    return median(absolute(data - median(data, axis)), axis)


def autocorrelation(X, lag=1):
    """autocorrelation(X, lag=1)

    Computes the autocorrelation of *X* with the given *lag*.
    Autocorrelation is simply
    autocovariance(X) / covariance(X-mean, X-mean),
    where autocovariance is simply
    covariance((X-mean)[:-lag], (X-mean)[lag:]).

    See `link <https://en.wikipedia.org/wiki/Autocorrelation>`_ for details.

    **Parameters**

    X : array-like, shape = [n_samples]

    lag : int, optional
        Index difference between points being compared (default 1).
    """
    differences = X - X.mean()
    products = differences * concatenate((differences[lag:],
                                          differences[:lag]))

    return products.sum() / (differences**2).sum()

_latex_replacements = [
    ('\\', '\\\\'),
    ('{',  '\\{'),
    ('{',  '\\}'),
    ('$',  '\\$'),
    ('&',  '\\&'),
    ('#',  '\\#'),
    ('^',  '\\textasciicircum{}'),
    ('_',  '\\textunderscore{}'),
    ('~',  '\\~'),
    ('%',  '\\%'),
    ('<',  '\\textless{}'),
    ('>',  '\\textgreater{}'),
    ('|',  '\\textbar{}')
]

def sanitize_latex(string):
    """sanitize_latex(string)

    Sanitize a string for input to LaTeX.

    Replacements taken from `Stack Overflow
    <http://stackoverflow.com/questions/2627135/how-do-i-sanitize-latex-input>`_

    **Parameters**

    string: str

    **Returns**

    sanitized_string: str
    """
    sanitized_string = string
    for old, new in _latex_replacements:
        sanitized_string = sanitized_string.replace(old, new)
    return sanitized_string
