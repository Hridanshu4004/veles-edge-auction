import numpy as np
import random

def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
