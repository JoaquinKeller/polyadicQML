"""Circuit builders for the manyQ simulator"""
from ..circuitBuilder import circuitBuilder

import manyq as mq


class mqBuilder(circuitBuilder):
    """Builder for circuits to be run on manyQ simulator.
    """
    def __init__(self, nbqbits, batch_size, *args, gpu=False, **kwargs):
        super().__init__(nbqbits)
        mq.initQreg(nbqbits, batch_size, gpu=gpu)

        self.__txt = ""

    def __run_circuit__(self, nbshots=None):
        if not nbshots:
            return mq.measureAll()
        else:
            return mq.makeShots(nbshots)

    def __call__(self, nbshots=None):
        return self.__run_circuit__(nbshots)

    def __str__(self):
        return self.__txt

    def __repr__(self):
        return "mqBuilder(" + str(self) + ")"

    def circuit(self):
        """Return the built circuit.

        Returns
        -------
        quantum circuit
        """
        return self

    ##############################
    # GATES

    def measure_all(self):
        mq.measureAll()

        self.__txt += "measure_all()"

        return self

    def __single_input(self, idx, theta):
        self.__verify_index__(idx)
        mq.SX(idx)
        mq.RZ(idx, theta)
        mq.SX(idx)

        self.__txt += f"SX({idx})RZ({idx},{theta})SX({idx})"

    def input(self, idx, theta):
        if isinstance(idx, list):
            for p, i in enumerate(idx):
                self.__single_input(i, theta[p])
        else:
            self.__single_input(idx, theta)

        return self

    def allin(self, theta):
        for i in range(self.nbqbits):
            self.__single_input(i, theta[i])

        return self

    def cz(self, a, b):
        self.__verify_index__(a)
        self.__verify_index__(b)

        mq.CZ(a, b)

        self.__txt += f"CZ({a},{b})"

        return self


    def fsim(self, a, b, theta, phi):
        self.__verify_index__(a)
        self.__verify_index__(b)

        mq.fSIM(a, b, theta, phi)

        self.__txt += f"fSIM({a},{b})"

        return self
