from enthought.traits.api import Instance
from enthought.traits.ui.api import View, Include, VGroup

from ._positive_am_noise_paradigm_mixin import PositiveAMNoiseParadigmMixin
from ._positive_am_noise_controller_mixin import PositiveAMNoiseControllerMixin

from experiments.abstract_positive_experiment import AbstractPositiveExperiment
from experiments.abstract_positive_controller import AbstractPositiveController
from experiments.abstract_positive_paradigm import AbstractPositiveParadigm
from experiments.positive_data import PositiveData

from experiments.cl_controller_mixin import CLControllerMixin
from experiments.cl_paradigm_mixin import CLParadigmMixin
from experiments.cl_experiment_mixin import CLExperimentMixin
from experiments.positive_cl_data_mixin import PositiveCLDataMixin

from experiments.pump_controller_mixin import PumpControllerMixin
from experiments.pump_paradigm_mixin import PumpParadigmMixin
from experiments.pump_data_mixin import PumpDataMixin

class Controller(
        PositiveAMNoiseControllerMixin,
        AbstractPositiveController, 
        CLControllerMixin,
        PumpControllerMixin):
    pass

class Paradigm(
        PositiveAMNoiseParadigmMixin,
        AbstractPositiveParadigm, 
        PumpParadigmMixin,
        CLParadigmMixin,
        ):

    traits_view = View(
            VGroup(
                Include('constant_limits_paradigm_mixin_group'),
                Include('abstract_positive_paradigm_group'),
                Include('pump_paradigm_mixin_syringe_group'),
                label='Paradigm',
                ),
            VGroup(
                Include('speaker_group'),
                Include('signal_group'),
                label='Sound',
                ),
            )

class Data(
    PositiveData, 
    PositiveCLDataMixin, 
    PumpDataMixin): 
        pass

class Experiment(AbstractPositiveExperiment, CLExperimentMixin):

    data = Instance(Data, ())
    paradigm = Instance(Paradigm, ())

node_name = 'PositiveAMNoiseCLExperiment'
