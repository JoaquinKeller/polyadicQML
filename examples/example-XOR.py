import numpy as np
import matplotlib.pyplot as plt

from polyadicqml import Classifier

from polyadicqml.manyq import mqCircuitML

SEED = 197
np.random.seed(SEED)

##############################
# We create a dataset of 200 points corresponding to the XOR problem
#       1 --|-- 0
#       |   |   |
#      -----|------
#       |   |   |
#       0 --|-- 1

n_pc = 50 # Number of points per cluster

# Create a matrix of vertices of the centered square
X = np.asarray(n_pc * [[1.5, 0.]] +    # First quadrant
            n_pc * [[-1.5, 0.]] +  # Third quadrant
            n_pc * [[0., -1.5]] +   # Second quadrant
            n_pc * [[0., 1.5]]     # Fourth quadrant
)
# Add gaussian noise
X += .5 * np.random.randn(*X.shape)
# Rotate of pi/4
# X = X @ [[np.cos(np.pi/4), np.sin(np.pi/4)],
#         [-np.sin(np.pi/4), np.cos(np.pi/4)]]

# X = 2 * np.arctan(X)

# Create target vecor
y = np.concatenate((np.zeros(2*n_pc), np.ones(2*n_pc)))

COLORS = ["tab:blue", "tab:red"]
if True:
    import seaborn as sns
    sns.set()
    fig, ax = plt.subplots(figsize=(5,5))
    idx = y == 1
    ax.plot(X[~ idx,0], X[~ idx,1], ls="", marker="o", color=COLORS[0], label="0")
    ax.plot(X[idx,0], X[idx,1], ls="", marker="o", color=COLORS[1], label="1",)

    graph_args = dict(ls="", marker = "D", ms=10, mec="black", mew=2)

    ax.plot([1.5, -1.5], [0, 0 ], color=COLORS[0], **graph_args)
    ax.plot([0, 0 ], [1.5, -1.5], color=COLORS[1], **graph_args)

    ax.set(xlim=[-np.pi,np.pi], ylim=[-np.pi,np.pi])
    ax.legend(loc="upper right")

    plt.savefig("figures/XOR-points.png", bbox_inches="tight")
    plt.close()

##############################
# Now we define the make_circuit function using the builder interface

def make_circuit(bdr, x, params, shots=None):
    bdr.allin(x[[0,1]])

    bdr.cz(0, 1)
    bdr.allin(params[[0,1]])

    bdr.cz(0, 1)
    bdr.allin(params[[2,3]])


    if shots: bdr.measure_all()
    return bdr.circuit()

##############################
# Now we instanciate a backend and the circuit

nbqbits = 2
nbparams = 6

qc = mqCircuitML(make_circuit=make_circuit,
                nbqbits=nbqbits, nbparams=nbparams)

bitstr = ['00', '01']

model = Classifier(qc, bitstr)

model.fit(X, y)

##############################
# Then we test the model

t = np.linspace(-np.pi,np.pi, num = 50)
X_test = np.array([[t1, t2] for t1 in t for t2 in t])

y_pred = model.predict_label(X_test)

if True:
    fig, ax = plt.subplots(figsize=(5,5))
    idx = y_pred == 1
    ax.plot(X_test[idx,0], X_test[idx,1], ls="", marker="s", color="coral", alpha=.3)
    ax.plot(X_test[~ idx,0], X_test[~ idx,1], ls="", marker="s", color="deepskyblue", alpha=.3)

    idx = y == 1
    ax.plot(X[idx,0], X[idx,1], ls="", marker="o", color=COLORS[1], label="1")
    ax.plot(X[~ idx,0], X[~ idx,1], ls="", marker="o", color=COLORS[0], label="0")

    graph_args = dict(ls="", marker = "D", ms=10, mec="black", mew=2)

    ax.plot([0, 0 ], [1.5, -1.5], color=COLORS[1], **graph_args)
    ax.plot([1.5, -1.5], [0, 0 ], color=COLORS[0], **graph_args)

    ax.plot([-np.pi, np.pi], [-np.pi, np.pi], color="tab:grey")
    ax.plot([-np.pi, np.pi], [np.pi, -np.pi], color="tab:grey")
    ax.set(xlim=[-np.pi,np.pi], ylim=[-np.pi,np.pi],)
    ax.legend(loc="upper right")

    plt.savefig("figures/XOR-predictions.png", bbox_inches="tight")
    plt.close()