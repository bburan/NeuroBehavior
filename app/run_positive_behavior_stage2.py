from config import settings

from cns.data.h5_utils import get_or_append_node
from cns.experiment.experiment.positive_experiment import \
    PositiveExperiment as PositiveExperimentStage2

import tables

def experiment_stage2():
    store = tables.openFile('test.h5', 'w')
    ae = PositiveExperimentStage2(store_node=store.root)
    ae.configure_traits()

if __name__ == '__main__':
    experiment_stage2()