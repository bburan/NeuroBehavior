from enthought.traits.api import Instance
from enthought.traits.ui.api import View, Include

from abstract_positive_experiment import AbstractPositiveExperiment
from positive_dt_paradigm import PositiveDTParadigm
from positive_dt_controller import PositiveDTController

from positive_dt_data import PositiveDTData

class PositiveDTExperiment(AbstractPositiveExperiment):

    paradigm = Instance(PositiveDTParadigm, ())

    def _data_default(self):
        return PositiveDTData(store_node=self.data_node)

    traits_view = View(Include('traits_group'),
                       resizable=True,
                       kind='live',
                       handler=PositiveDTController)