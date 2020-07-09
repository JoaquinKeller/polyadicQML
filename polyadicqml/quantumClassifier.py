"""Module for classification using quantum machine learning models.
"""
import numpy as np

import pickle
import json
from tqdm.auto import tqdm

import datetime

from scipy.optimize import minimize

from .circuitML import circuitML

from .utility import CE_loss

class Classifier():
    """Class for quantum classifiers. Defines the API using the scikit-learn format.

    Parameters
    ----------
    circuit : circuitML
        Quantum circuit to simulate, how to use and store is defined in child classes.
    bitstr : list of int or list of str
        Which bitstrings should correspond to each class. The number of classes for the classification is defined by the number of elements.
    params : vector, optional
        Initial model paramters. If None (default) uses circuit.random_params().
    nbshots : int, optional
        Number of shots for the quantum circuit. If 0, negative or None, then exact proabilities are computed, by default None
    nbshots_increment : float, int or callable, optional
        How to increase the number of shots as optimization progress. If float or int, the increment arise every `nbshots_incr_delay` iterations: if float, then the increment is multiplicative; if int, then it is added. If callable, the new nbshots is computed by calling `nbshots_increment(nbshots, n_iter, loss_value)`.
    nbshots_incr_delay : int, optional
        After how many iteration nb_shots has to increse. By default 20, if nbshots_increment is given
    loss : callable, optional
        Loss function, by default Negative LogLoss (Cross entropy).
    job_size : int, optional
        Number of runs for each circuit job, by default the number of observations.
    budget : int, optional
        Maximum number of optimization steps, by default 100
    name : srt, optional
        Name to identify this classifier.
    save_path : str, optional
        Where to save intermediate training results, by deafult None. If None, intermediate results are not saved.

    Attributes
    ----------
    bitstr : list[int]
        Bitstrings (as int) on which to read the classes
    nbshots : int
        Number of shots to run circuit
    job_size : int
        Number of circuits to run in each backend job
    nfev : int
        Number if times the circuit has been run
    """
    def __init__(self, circuit, bitstr, **kwargs):
        super().__init__()

        # Retrieve keyword arguments
        params = kwargs.get('params')
        nbshots = kwargs.get('nbshots')
        nbshots_increment = kwargs.get('nbshots_increment')
        nbshots_incr_delay = kwargs.get('nbshots_incr_delay')
        loss = kwargs.get('loss', CE_loss)
        job_size = kwargs.get('job_size')
        budget = kwargs.get('budget', 100)
        name = kwargs.get('name')
        save_path = kwargs.get('save_path')

        # Testing circuit and setting it
        self.set_circuit(circuit)

        # Testing for bitstring validity
        if isinstance(bitstr[0], int):
            for i in bitstr:
                if not isinstance(i, int):
                    raise TypeError("All bitstrings must have the same type")
            self.bitstr = bitstr
        elif isinstance(bitstr[0], str):
            for i in bitstr:
                if not isinstance(i, str):
                    raise TypeError("All bitstrings must have the same type")
            self.bitstr = [int(bit, 2) for bit in bitstr]
        else:
            raise TypeError("Bitstrings must be either int or binary strings")

        if params is None:
            self.set_params(circuit.random_params())
        else:
            self.set_params(params)

        if not (isinstance(nbshots, int) or (nbshots is None)):
            raise TypeError("Invalid `nbshots` type")
        if nbshots is not None and nbshots < 1:
            nbshots = None
        self.nbshots = nbshots

        if not (isinstance(nbshots_incr_delay, int) or (nbshots_incr_delay is None)):
            raise TypeError("Invalid `nbshots_incr_delay` type")
        self.nbshots_incr_delay = 20 if nbshots_incr_delay is None else nbshots_incr_delay

        if nbshots_increment is None:
            self.nbshots_increment = lambda nbshots, n_iter, loss_value: nbshots
        elif isinstance(nbshots_increment, float):
            self.nbshots_increment = lambda nbshots, n_iter, loss_value: int(
                nbshots_increment * nbshots) if n_iter % self.nbshots_incr_delay == 0 else nbshots
        elif isinstance(nbshots_increment, int):
            self.nbshots_increment = lambda nbshots, n_iter, loss_value: nbshots + \
                nbshots_increment if n_iter % self.nbshots_incr_delay == 0 else nbshots
        else:
            self.nbshots_increment = nbshots_increment

        if not isinstance(budget, int):
            raise TypeError("Invalid `budget` type")
        self.__budget__ = budget

        self.job_size = job_size

        self.__loss__ = loss
        self.__min_loss__ = np.inf

        self.__last_loss_value__ = None
        self.__last_output__ = None
        self.__last_params__ = None
        self.__loss_progress__ = []
        self.__output_progress__ = []
        self.__params_progress__ = []
        self.__name__ = name
        self.__save_path__ = save_path
        self.__info__ = {
            'circuit': str(circuit),
            'nbshots': nbshots,
            'nbshots_increment': str(nbshots_increment),
            'nbshots_incr_delay': str(nbshots_incr_delay),
            'bitstr': [bin(bit) for bit in self.bitstr],
            'job_size' : job_size if job_size else "FULL",
            }
        self.nfev = 0

    def __verify_circuit__(self, circuit):
        """Test wheter a circuit is valid and raise TypeError if it is not.

        Parameters
        ----------
        circuit : circuitML
            QML circuit

        Raises
        ------
        TypeError
            If the circuit is not a circuitML
        ValueError
            If self has a circuit and the new circuit does not uses the same make_circuit fuction
        """
        if not isinstance(circuit, circuitML):
            raise TypeError(f"Circuit was type {type(circuit)} while circuitML was expected.")
        if hasattr(self, 'circuit'):
            if self.circuit != circuit:
                raise ValueError("Given circuit is different from previous circuit")

    def set_circuit(self, circuit):
        """Set the circuit after testing for validity.

        For a circuit to be valid, it has to be an instance of circuitML and, in case self already has a circuit, to use the same make_circuit function.

        Parameters
        ----------
        circuit : circuitML
            QML circuit

        Raises
        ------
        Union[TypeError, ValueError]
            If the circuit is invalid.
        """
        self.__verify_circuit__(circuit)
        self.circuit = circuit

    def set_params(self, params):
        """Parameters setter

        Parameters
        ----------
        params : vector
            Parameters vector
        """
        self.params = params

    def run_circuit(self, X, params=None):
        """Run the circuit with input `X` and parameters `params`.
        
        Parameters
        ----------
        X : array-like
            Input matrix of shape (nb_samples, nb_features).
        params : vector-like, optional
            Parameter vector, by default uses the model :attr:`~polyadicqml.Classifier.params`

        Returns
        -------
        array
            Bitstring counts as an array of shape (nb_samples, 2**nbqbits)
        """
        if params is None:
            params = self.params
        
        self.nfev += 1

        return self.circuit.run(X, params, self.nbshots,
                               job_size=self.job_size)

    def predict_proba(self, X, params=None):
        """Compute the bitstring probabilities associated to each input point of the design matrix.

        Parameters
        ----------
        X : array
            Design matrix of n samples
        params : vector, optional
            Circuit parameters, by default None. If not given, model parameters are used.

        Returns
        -------
        array
            Predicted bitstring probabilities. Rows correspond to samples and columns to bitstrings, whose order is defined in :attr:`~polyadicqml.quantumClassifier.bitstr`. 
        """
        out = self.run_circuit(X, params)

        if self.nbshots:
            out = out / float(self.nbshots)

        return out[:, self.bitstr]

    def proba_to_label(self, proba) -> np.ndarray:
        """Transforms a matrix of real values in integer labels.

        Parameters
        ----------
        proba : array
            Real valued array

        Returns
        -------
        vector
            Labels vector
        """
        return np.argmax(proba, axis=1)

    def predict(self, X):
        """Compute the predicted class for each input point of the design matrix.

        Parameters
        ----------
        X : array
            Design matrix of n samples

        Returns
        -------
        vector
            Labels vector
        """
        return self.proba_to_label(self.predict_proba(X))

    def __call__(self, X):
        """Compute the predicted class for each input point of the design matrix.
        Equivalent to :meth:`~polyadicqml.quantumClassifier.predict`

        Parameters
        ----------
        X : array
            Design matrix of n samples
        params : vector, optional
            Circuit parameters, by default None. If not given, model parameters are used.

        Returns
        -------
        vector
            Labels vector
        """
        return self.predict(X)

    def set_loss(self, loss=None):
        """Loss function setter.

        Parameters
        ----------
        loss : callable, optional
            Loss function of the form loss(y_true, y_pred, labels), by default None.
            If None is given, nothing happens.
        """
        if loss is not None:
            self.__loss__ = loss

    def __callback__(self, params, loss=False, output=False, ):
        """Callback function for optimization. It is called after each step.

        Parameters
        ----------
        params : vector
            Current parameter vector
        loss : bool, optional
            Wheter to store the loss value, by default False
        output : bool, optional
            Wheter to store the current output and parameters , by default False
        """
        if loss or output:
            self.__loss_progress__.append(self.__last_loss_value__)
        if output:
            self.__output_progress__.append(self.__last_output__.tolist())
            self.__params_progress__.append(params.tolist())

        self.__n_iter__ += 1
        if self.__save_path__ and self.__n_iter__ % 10 == 0:
            self.save()
        
        self.pbar.update()

        
    def fit(self, input_train, target_train, batch_size=None,
            **kwargs):
        """Fit the model according to the given training data.

        Parameters
        ----------
        input_train : array
            Training design matrix.
        target_train : vector
            Labels corresponding to `input_train`.
        batch_size : int, optional
            Minibatches size, by default None. If none uses the full dataset with rndom shuffle at each iteration.
        method : str, optional
            Optimization method, by default BFGS
        bounds : sequence, optional
            Bounds on variables for L-BFGS-B, TNC, SLSQP, Powell, and
            trust-constr methods as a sequence of ``(min, max)`` pairs for
            each element in x. None is used to specify no bound.
        options : dict, optional
            Optimizer options, by default {'maxiter': budget}
        save_loss_progress : bool, optional
            Whether to store the loss progress, by default False
        save_output_progress : file path, optional
            Path where to save the output evolution , by default None. If none is given, the output is not saved.
        seed : int, optional
            Random seed, by default None

        Returns
        -------
        Classifier
            self
        """

        method =  kwargs.get('method', 'BFGS')
        save_loss_progress = kwargs.get('save_loss_progress')
        save_output_progress = kwargs.get('save_output_progress')
        seed = kwargs.get('seed') 

        _nbshots = self.nbshots
        if seed is not None:
            np.random.seed(seed)
        self.pbar = tqdm(total=self.__budget__, desc="Training", leave=False)
        self.__n_iter__ = 0

        if not batch_size:
            batch_size = len(target_train)

        _labels = np.unique(target_train)
        if len(_labels) > len(self.bitstr):
            raise ValueError(f"Too many labels: expected {len(self.bitstr)}, found {len(_labels)} in target_train")

        indices = np.arange(len(target_train))

        def to_optimize(params):
            _indices = np.random.choice(
                indices, size=batch_size, replace=False)
            self.nbshots = self.nbshots_increment(
                self.nbshots, self.__n_iter__, self.__min_loss__)

            probas = self.predict_proba(input_train[_indices], params)
            loss_value = self.__loss__(target_train[_indices], probas,
                                       labels=_labels)

            self.__last_loss_value__ = loss_value
            self.__last_output__ = probas[np.argsort(_indices)]

            if loss_value < self.__min_loss__:
                self.__min_loss__ = loss_value
                self.set_params(params.copy())

            if method == "COBYLA":
                self.__callback__(params, save_loss_progress, save_output_progress)

            return loss_value

        # SCIPY.MINIMIZE IMPLEMENTATION
        options = kwargs.get('options', {'maxiter': self.__budget__})
        bounds = kwargs.get('bounds')
        if method == 'L-BFGS-B' and bounds is None:
            bounds = [(-np.pi, np.pi) for _ in self.params]

        mini_kwargs = dict(
            method=method, bounds=bounds, 
            options=options,
        )
        if method.lower() not in ('cobyla'):
            mini_kwargs["callback"] = lambda xk : self.__callback__(
                xk, save_loss_progress, save_output_progress,
            )

        mini_out = minimize(to_optimize, self.params, **mini_kwargs)

        self.set_params(mini_out.x.copy())

        if "sim_calls" not in self.__info__.keys():
            self.__info__["nfev"] = self.nfev
            self.__info__["n_iter"] = self.__n_iter__

        del self.__n_iter__
        self.pbar.close()
        del self.pbar

        if save_output_progress:
            with open(save_output_progress, "w") as f:
                _d = dict(output = self.__output_progress__,
                          labels = target_train.tolist(),
                          loss_value = self.__loss_progress__,
                          params = self.__params_progress__)
                json.dump(_d, f)
            self.__output_progress__ = []
            self.__params_progress__ = []

        # we reset the number if nbshots, as we changed it during training.
        self.nbshots = _nbshots

        return self

    def info_dict(self):
        """Returns a dictionary containing models information.

        Returns
        -------
        dict
            Information dictionary
        """
        out = {}

        model_info = {
            "parameters": self.params.tolist(),
        }
        if self.__loss_progress__:
            model_info["loss_progress"] = self.__loss_progress__

        model_info.update(self.__info__)

        name = self.__name__ if self.__name__ is not None else "quantumClassifier"

        out[str(name)] = model_info
        return out

    def save(self, path=None):
        if path is None:
            path = self.__save_path__
        model_info = {
            "parameters": self.params.tolist(),
        }
        if self.__loss_progress__:
            model_info["loss_progress"] = self.__loss_progress__

        model_info.update(self.__info__)
        with open(path, 'wb') as f:
            pickle.dump(model_info, f)
