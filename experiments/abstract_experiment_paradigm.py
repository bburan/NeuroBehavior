from enthought.traits.api import HasTraits, Enum, Property, Bool, List, \
     Float, Button, Instance, Tuple
from enthought.traits.ui.api import VGroup, Item, HGroup
from .evaluate import Expression

PARAMETER_FILTER = {
        'editable': lambda x: x is not False,
        'type':     lambda x: x not in ('event', 'python'),
        'ignore':   lambda x: x is not True,
        }

from enthought.traits.ui.api import TabularEditor
from enthought.traits.ui.tabular_adapter import TabularAdapter

class SpeakerRange(HasTraits):
    
    frequency = Float(store='attribute', context=True, log=False)
    max_level = Float(store='attribute', context=True, log=False)
    
    def __lt__(self, other):
        if not isinstance(other, SpeakerRange):
            return NotImplemented
        a = self.frequency, self.max_level
        b = other.frequency, other.max_level
        return a < b
    
    def __eq__(self, other):
        if not isinstance(other, SpeakerRange):
            return NotImplemented
        a = self.frequency, self.max_level
        b = other.frequency, other.max_level
        return a == b

speaker_range_columns = [
    ('Frequency (Hz)', 'frequency'),
    ('Max level (dB SPL)', 'max_level'),
    ]

speaker_range_editor = TabularEditor(
    auto_update=True,
    editable=True,
    multi_select=True,
    selected='_selected_speaker_range',
    adapter=TabularAdapter(columns=speaker_range_columns),
    )

class AbstractExperimentParadigm(HasTraits):

    def __load_paradigm_fired(self):
        instance = load_instance(PARADIGM_ROOT, PARADIGM_WILDCARD)
        if instance is not None:
            self.copy_traits(instance)

    def __save_paradigm_fired(self):
        print dump_instance(self, PARADIGM_ROOT, PARADIGM_WILDCARD)

    speaker = Expression("random_speaker(0.5)", label='Output Speaker',
            store='attribute', context=True, log=True)
    speaker_equalize = Bool(False, label='Equalize speakers?',
            store='attribute', context=True, log=True)
    #primary_gain = Float(0, label='Primary gain', store='attribute',
    #        context=True, log=True)
    #secondary_gain = Float(0, label='Secondary gain', store='attribute',
    #        context=True, log=True)
    fixed_attenuation = Bool(False, label='Fixed hardware attenuation?',
            context=True, log=True)
    expected_speaker_range = List(Instance(SpeakerRange), container=True,
            store='attribute', label='Expected speaker range', context=True)

    _add_speaker_range = Button('Add')
    _remove_speaker_range = Button('Remove')
    _sort_speaker_range = Button('Sort')
    _selected_speaker_range = List
    
    def __sort_speaker_range_fired(self):
        self.expected_speaker_range.sort()
    
    def __add_speaker_range_fired(self):
        # If a setting is selected, let's assume that the user wishes to
        # duplicate 
        if len(self._selected_speaker_range) != 0:
            for speaker_range in self._selected_speaker_range:
                self.expected_speaker_range.append(speaker_range.clone_traits())
        else:
            self.expected_speaker_range.append(SpeakerRange())
        
    def __remove_speaker_range_fired(self):
        for speaker_range in self._selected_speaker_range:
            self.expected_speaker_range.remove(speaker_range)
        self._selected_speaker_range = []
    
    @classmethod
    def get_parameters(cls):
        return sorted(cls.class_trait_names(**PARAMETER_FILTER))

    @classmethod
    def get_parameter_info(cls):
        '''
        Dictionary of available parameters and their corresponding
        human-readable label
        '''
        traits = cls.class_traits(**PARAMETER_FILTER)
        return dict((name, trait.label) for name, trait in traits.items())

    @classmethod
    def get_parameter_label(cls, parameter):
        return cls.get_parameter_info()[parameter]

    speaker_group = VGroup(
            'speaker',
            'speaker_equalize',
            #'primary_gain',
            #'secondary_gain',
            Item('fixed_attenuation'),
            VGroup(
                HGroup('_add_speaker_range', '_remove_speaker_range', 
                       '_sort_speaker_range', show_labels=False,
                       enabled_when='fixed_attenuation'),
                Item('expected_speaker_range', editor=speaker_range_editor, 
                     enabled_when='fixed_attenuation', show_label=False),
                ),
            label='Speaker',
            show_border=True,
            )
