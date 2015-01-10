import numpy
numpy.random.seed(0)
from scipy.stats import sem
from sys import stderr
from math import floor
from os import path
from .utils import (verbose_print, make_sure_path_exists,
                    get_signal, get_noise, colvec, mad)
from .periodogram import find_period, Lomb_Scargle, rephase
from .preprocessing import Fourier
from sklearn.cross_validation import cross_val_score
from sklearn.linear_model import LassoLarsIC
from sklearn.pipeline import Pipeline
from sklearn.grid_search import GridSearchCV
from sklearn.utils import ConvergenceWarning
import warnings
warnings.filterwarnings("ignore", category=ConvergenceWarning)
import matplotlib.pyplot as plt

__all__ = [
    'make_predictor',
    'get_lightcurve',
    'get_lightcurve_from_file',
    'find_outliers',
    'plot_lightcurve'
]


def make_predictor(regressor=LassoLarsIC(fit_intercept=False),
                   Selector=GridSearchCV, fourier_degree=(2, 25),
                   selector_processes=1,
                   use_baart=False, scoring='r2', scoring_cv=3,
                   **kwargs):
    """
    Makes a predictor object for use in get_lightcurve.

    Parameters
    ----------
    regressor : object with "fit" and "transform" methods, optional
        Regression object used for solving Fourier matrix
        (default LassoLarsIC(fit_intercept=False)).

    Selector : class with "fit" and "predict" methods, optional
        Model selection class used for finding the best fit
        (default GridSearchCV).

    selector_processes : positive integer, optional
        Number of processes to use for ``Selector`` (default 1).

    use_baart : boolean, optional
        If True, ignores ``Selector`` and uses Baart's Criteria to find
        the Fourier degree, within the boundaries (default False).

    fourier_degree : 2-tuple, optional
        Tuple containing lower and upper bounds on Fourier degree, in that
        order (default (2, 25)).

    scoring : str, optional
        Scoring method to use for ``Selector``. This parameter can be:

            - "r2", in which case use R^2 (the default)

            - "mse", in which case use mean square error

    scoring_cv : positive integer, optional
        Number of cross validation folds used in scoring (default 3).

    Returns
    -------
    out : object with "fit" and "predict" methods
        The created predictor object.
    """
    fourier = Fourier(degree_range=fourier_degree, regressor=regressor) \
              if use_baart else Fourier()
    pipeline = Pipeline([('Fourier', fourier), ('Regressor', regressor)])
    if use_baart:
        return pipeline
    else:
        params = {'Fourier__degree': list(range(fourier_degree[0],
                                                fourier_degree[1]+1))}
        return Selector(pipeline, params, scoring=scoring, cv=scoring_cv,
                        n_jobs=selector_processes)


def get_lightcurve(data, name=None,
                   predictor=None, periodogram=Lomb_Scargle,
                   sigma_clipping=mad,
                   scoring='r2', scoring_cv=3, scoring_processes=1,
                   period=None, min_period=0.2, max_period=32,
                   min_period_count=1, max_period_count=1,
                   coarse_precision=1e-5, fine_precision=1e-9,
                   period_processes=1,
                   sigma=20,
                   min_phase_cover=0.0, sample_phase=numpy.arange(0, 1, 0.01),
                   verbosity=[], **kwargs):
    """
    Fits a light curve to the given `data` using the specified methods,
    with default behavior defined for all methods.

    Parameters
    ----------
    data : array-like, shape = [n_samples, 2] or [n_samples, 3]
        Input array of time, magnitude, and optional error, column-wise.
        Time should be unphased.

    name : string or None, optional
        Name of star.

    predictor : object that has "fit" and "predict" methods, optional
        Object which fits the light curve obtained from ``data`` after rephasing
        (default ``make_predictor(scoring=scoring, scoring_cv=scoring_cv)``).

    periodogram : function, optional
        Function which finds one or more `period`s. If ``period`` is already
        provided, the function is not used. Defaults to
        ``lightcurve.Lomb_Scargle``

    sigma_clipping : function, optional
        Function which takes an array and assigns sigma scores to each element.
        Defaults to ``utils.mad``.

    scoring : str, optional
        Scoring method used by ``predictor``. This parameter can be

            - "r2", in which case use R^2 (the default)

            - "mse", in which case use mean square error

    scoring_cv : positive integer, optional
        Number of cross validation folds used in scoring (default 3).

    scoring_processes : positive integer, optional
        Number of processes to use for scoring cross validation (default 1).

    period : array-like or None, shape = [] or [n_periods], optional
        Period(s) of oscillation used in the fit. This parameter can be:

            - None, in which case the period is obtained with the given
              ``periodogram`` function (the default).

            - Zero, in which case the data are unphased.

            - A single positive number, giving the period to phase the data.

            - An array of positive numbers, giving the periods to phase the
              data.

    min_period : non-negative number, optional
        Lower bound on period(s) obtained by ``periodogram`` (default 0.2).

    max_period : non-negative number, optional
        Upper bound on period(s) obtained by ``periodogram`` (default 32.0).

    min_period_count : non-negative number, optional
        Lower bound on number of periods obtained by ``periodogram``
        (default 1).

    max_period_count : non-negative number, optional
        Upper bound on number of periods obtained by ``periodogram``
        (default 1).

    course_precision : positive number, optional
        Precision used in first period search sweep (default 1e-5).

    fine_precision : positive number, optional
        Precision used in second period search sweep (default 1e-9).

    period_processes : positive integer, optional
        Number of processes to use for period finding (default 1).

    sigma : number, optional
        Upper bound on score obtained by ``sigma_clipping`` to be considered
        an inlier.

    min_phase_cover : number between 0 and 1, optional
        Fraction of binned light curve that must contain points in order to
        proceed. If light curve has insufficient coverage, a warning is
        printed if "outlier" verbosity is on, and None is returned

    phases : array-like, shape = [n_phases]
        Array of phases to predict magnitudes at (default [0, 0.01, ..., 1.0]).

    verbosity : list, optional
        See ``utils.verbose_print``.

    Returns
    -------
    out - dict
        Results of the fit in a dictionary. The keys are:

            - name : str or None
                The name of the star.
            - period : array-like, shape = [] or [n_periods]
                The star's period(s).
            - lightcurve : array-like, shape = [n_phases]
                Magnitudes of fitted light curve sampled at ``phases``.
            - coefficients : array-like, shape = [n_coeffs, n_phases]
                Fitted light curve coefficients.
            - dA_0 : non-negative number
                Error on mean magnitude.
            - phased_data : array-like, shape = [n_samples]
                ``data`` transformed from temporal to phase space.
            - model : predictor object
                The predictor used to fit the light curve.
            - R2 : number
                The R^2 score of the fit.
            - MSE : number
                The mean square error of the fit.
            - degree : positive integer
                The degree of the Fourier fit.
            - shift : number
                The phase shift used to move phase zero to maximum brightness.
            - coverage : number between 0 and 1
                The light curve coverage.

    See also
    --------
    get_lightcurve_from_file, get_lightcurves_from_file
    """
# TODO ###
# Replace dA_0 with error matrix dA
    if predictor is None:
        predictor = make_predictor(scoring=scoring, scoring_cv=scoring_cv)

    while True:
        signal = get_signal(data)
        if len(signal) <= scoring_cv:
            return

        # Find the period of the inliers
        if period is not None:
            _period = period
        else:
            verbose_print("{}: finding period".format(name),
                          operation="period", verbosity=verbosity)
            _period = find_period(signal,
                                  min_period, max_period,
                                  min_period_count, max_period_count,
                                  coarse_precision, fine_precision,
                                  periodogram, period_processes)

        predictor.estimator.set_params(Fourier__periods=_period)
        verbose_print("{}: using period {}".format(name, _period),
                      operation="period", verbosity=verbosity)
        time, mag, *err = signal.T

# TODO ###
# Generalize number of bins to function parameter ``coverage_bins``, which
# defaults to 100, the current hard-coded behavior
#
        # TEMP FIX ###
        # Coverage determination not yet implemented for multiple periods
        # Unless phases is 1D, skip coverage detection
        if False:#numpy.ndim(phases) == 1:
            # Determine whether there is sufficient phase coverage
            coverage = numpy.zeros((100))
            for p in phase:
                coverage[int(floor(p*100))] = 1
            coverage = sum(coverage)/100
            if coverage < min_phase_cover:
                verbose_print("{}: {} {}".format(name, coverage,
                                                 min_phase_cover),
                              operation="coverage",
                              verbosity=verbosity)
                verbose_print("Insufficient phase coverage",
                              operation="outlier",
                              verbosity=verbosity)
                return
        else:
            coverage = numpy.nan

        # Predict light curve
        with warnings.catch_warnings(record=True) as w:
            try:
                predictor = predictor.fit(colvec(time), mag)
            except Warning:
                # not sure if this should be only in verbose mode
                print(name, w, file=stderr)
                return

        # Reject outliers and repeat the process if there are any
        if sigma > 0:
            outliers = find_outliers(data.data, _period, predictor, sigma,
                                     sigma_clipping)
            num_outliers = sum(outliers)[0]
            if num_outliers == 0 or \
               set.issubset(set(numpy.nonzero(outliers.T[0])[0]),
                            set(numpy.nonzero(data.mask.T[0])[0])):
                data.mask = outliers
                break
            if num_outliers > 0:
                verbose_print("{}: {} outliers".format(name, sum(outliers)[0]),
                              operation="outlier",
                              verbosity=verbosity)
            data.mask = numpy.ma.mask_or(data.mask, outliers)
            continue
        else:
            break

    # Build light curve and shift to max light
    all_times = numpy.linspace(min(time), max(time), 100)
    lightcurve = predictor.predict(colvec(all_times))
#    print(lightcurve); exit()
    arg_max_light = lightcurve.argmin()
    lightcurve = numpy.concatenate((lightcurve[arg_max_light:],
                                    lightcurve[:arg_max_light]))
    shift = arg_max_light / time.size
#    data.T[0] = rephase(data.data, _period, shift).T[0]

    # Grab the coefficients from the model
    coefficients = predictor.named_steps['Regressor'].coef_ \
        if isinstance(predictor, Pipeline) \
        else predictor.best_estimator_.named_steps['Regressor'].coef_,

    # compute R^2 and MSE if they haven't already been
    # (one or zero have been computed, depending on the predictor)
    estimator = predictor.best_estimator_ \
        if hasattr(predictor, 'best_estimator_') \
        else predictor

    get_score = lambda scoring: predictor.best_score_ \
        if hasattr(predictor, 'best_score_') \
        and predictor.scoring == scoring \
        else cross_val_score(estimator, colvec(time), mag,
                             cv=scoring_cv, scoring=scoring,
                             n_jobs=scoring_processes).mean()

    return {'name':         name,
            'period':       _period,
            'lightcurve':   lightcurve,
            'coefficients': coefficients[0],
            'dA_0':         sem(lightcurve),
            'phased_data':  data,
            'model':        predictor,
            'R2':           get_score('r2'),
            'MSE':          abs(get_score('mean_squared_error')),
            'degree':       estimator.get_params()['Fourier__degree'],
            'shift':        shift,
            'coverage':     coverage}


def get_data_from_file(filename, use_cols=None, skiprows=0):
    return numpy.loadtxt(filename, usecols=use_cols, skiprows=skiprows)


def get_lightcurve_from_file(filename, *args, use_cols=None, skiprows=0,
                             **kwargs):
    data = get_data_from_file(filename, skiprows=skiprows, use_cols=use_cols)
    if len(data) != 0:
        masked_data = numpy.ma.array(data=data, mask=None, dtype=float)
        return get_lightcurve(masked_data, *args, **kwargs)
    else:
        return


def get_lightcurves_from_file(filename, directories, *args, **kwargs):
    return [get_lightcurve_from_file(path.join(d, filename), *args, **kwargs)
            for d in directories]


def single_periods(data, period, min_points=10, *args, **kwargs):
    time, mag, *err = data.T

    tstart, tfinal = numpy.min(time), numpy.max(time)
    periods = numpy.arange(tstart, tfinal+period, period)
    data_range = (
        data[numpy.logical_and(time>pstart, time<=pend),:]
        for pstart, pend in zip(periods[:-1], periods[1:])
    )

    return (
        get_lightcurve(d, period=period, *args, **kwargs)
        for d in data_range
        if d.shape[0] > min_points
    )


def single_periods_from_file(filename, *args, use_cols=(0, 1, 2), skiprows=0,
                             **kwargs):
    data = numpy.ma.array(data=numpy.loadtxt(filename, usecols=use_cols,
                                             skiprows=skiprows),
                          mask=None, dtype=float)
    return single_periods(data, *args, **kwargs)


def find_outliers(data, period, predictor, sigma, method=mad):
    time, mag, *err = data
    residuals = numpy.absolute(predictor.predict(colvec(time)) - mag)
    outliers = numpy.logical_and((residuals > err[0]) if err else True,
                                 residuals > sigma * method(residuals))

    return numpy.tile(numpy.vstack(outliers), data.shape[1])


def plot_lightcurve(name, lightcurve, period, data, output='.', legend=False,
                    color=True, phases=numpy.arange(0, 1, 0.01),
                    err_const=0.0004,
                    **kwargs):
    ax = plt.gca()
    ax.invert_yaxis()
    plt.xlim(0,2)

    # Plot points used
    phase, mag, *err = get_signal(data).T

    error = err[0] if err else mag*err_const

    inliers = plt.errorbar(numpy.hstack((phase,1+phase)),
                           numpy.hstack((mag, mag)),
                           yerr=numpy.hstack((error, error)),
                           ls='None',
                           ms=.01, mew=.01, capsize=0)

    # Plot outliers rejected
    phase, mag, *err = get_noise(data).T

    error = err[0] if err else mag*err_const

    outliers = plt.errorbar(numpy.hstack((phase,1+phase)),
                            numpy.hstack((mag, mag)),
                            yerr=numpy.hstack((error, error)),
                            ls='None', marker='o' if color else 'x',
                            ms=.01 if color else 4,
                            mew=.01 if color else 1,
                            capsize=0 if color else 1)

    # Plot the fitted light curve
    signal, = plt.plot(numpy.hstack((phases,1+phases)),
                       numpy.hstack((lightcurve, lightcurve)),
                       linewidth=1)

    if legend:
        plt.legend([signal, inliers, outliers],
                   ["Light Curve", "Inliers", "Outliers"],
                   loc='best')

    plt.xlabel('Phase ({0:0.7} day period)'.format(period))
    plt.ylabel('Magnitude')

    plt.title(name)
    plt.tight_layout(pad=0.1)
    make_sure_path_exists(output)
    plt.savefig(path.join(output, name))
    plt.clf()
