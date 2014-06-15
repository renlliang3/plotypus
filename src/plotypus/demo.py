import numpy as np
from sklearn.linear_model import LinearRegression, LassoCV
from sklearn.pipeline import Pipeline
from .Fourier import Fourier
from .utils import colvec

import matplotlib
matplotlib.use('PDF')
from matplotlib import rc
rc('font',**{'family':'serif','serif':['Latin Modern']})
rc('text', usetex=True)
import matplotlib.pyplot as plt

def lc(X):
    return 10 + np.cos(2*np.pi*X) + 0.1*np.cos(18*np.pi*X)

def main():
    X_true = np.linspace(0, 1, 101)
    y_true = lc(X_true)

    n_samples = 50
    X_sample = np.random.uniform(size=n_samples)
    y_sample = lc(X_sample) + np.random.normal(0, 0.1, n_samples)

    predictor = Pipeline([('Fourier', Fourier(9)),
                          ('OLS',   LinearRegression())])
    predictor = predictor.fit(colvec(X_sample), y_sample)
    y_pred = predictor.predict(colvec(X_true))

    predictor = Pipeline([('Fourier', Fourier(9)),
                          ('Lasso',   LassoCV())])
    predictor = predictor.fit(colvec(X_sample), y_sample)
    y_lasso = predictor.predict(colvec(X_true))

    ax = plt.gca()
    signal, = plt.plot(np.hstack((X_true,1+X_true)),
                       np.hstack((y_true, y_true)), 
                       linewidth=1.5,
                       color='black')

    fd, = plt.plot(np.hstack((X_true,1+X_true)), np.hstack((y_pred, y_pred)), 
                   linewidth=1.5, color='black', ls='dotted')

    lasso, = plt.plot(np.hstack((X_true,1+X_true)),
                      np.hstack((y_lasso, y_lasso)), 
                      linewidth=1.5,
                      color='black',
                      ls='dashed')

    sc = plt.scatter(np.hstack((X_sample,1+X_sample)),
                     np.hstack((y_sample, y_sample)),
                     color='black')

    plt.legend([signal, sc, fd, lasso],
               ["Signal", "Noisy Data", "FD", "Lasso FD"],
               loc='best')

    plt.xlim(0,2)
    plt.xlabel('Phase')
    plt.ylabel('Magnitude')
    plt.title('Simulated Lightcurve Example')
    plt.savefig('demo.pdf')
    plt.clf()
