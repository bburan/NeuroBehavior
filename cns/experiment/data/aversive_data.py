"""Note that the function and variable names may be a bit ambiguous since I'm
not sure what to call the SAFE/WARN trials.  We need to agree on some sensible
terminology to avoid any confusion.  For example:

    TRIAL - The response to the test signal plus it's associated "false alarms".
    TRIAL BLOCK - All pars presented during an experiment.
"""
#from .experiment_data import ExperimentData, AnalyzedData
from cns.experiment.data.experiment_data import ExperimentData, AnalyzedData
from cns.channel import FileMultiChannel
from enthought.traits.api import Instance, List, CFloat, Int, Float, Any, \
    Range, DelegatesTo, cached_property, on_trait_change, Array, Event, \
    Property, Undefined
import numpy as np
from cns.data.persistence import append_node

def apply_mask(fun, seq, mask):
    seq = np.array(seq).ravel()
    return [fun(seq[m]) for m in mask]

WATER_DTYPE = [('timestamp', 'i'), ('infused', 'f')]
TRIAL_DTYPE = [('timestamp', 'i'), ('par', 'f'), ('shock', 'f'), ('type', 'S16'), ]
LOG_DTYPE = [('timestamp', 'i'), ('name', 'S64'), ('value', 'S128'), ]

class AversiveData(ExperimentData):

    # This is a bit of a hack but I'm not sure of a better way to send the
    # datafile down the hierarchy.  We need access to this data file so we can
    # stream data to disk rather than storing it in a temporary buffer.
    store_node = Any

    contact_fs = Float

    contact_data = Instance(FileMultiChannel, store='automatic')
    contact_digital = Property
    contact_digital_mean = Property
    contact_analog = Property
    trial_running = Property

    def _get_contact_digital(self):
        return self.contact_data.get_channel('digital')

    def _get_contact_digital_mean(self):
        return self.contact_data.get_channel('digital_mean')

    def _get_contact_analog(self):
        return self.contact_data.get_channel('analog')

    def _get_trial_running(self):
        return self.contact_data.get_channel('trial_running')

    def _contact_data_default(self):
        names = ['digital', 'digital_mean', 'analog', 'trial_running']
        return FileMultiChannel(node=self.store_node, fs=self.contact_fs,
                           name='contact', type=np.float32, names=names,
                           channels=4, window_fill=0)

    water_log = Any(store='automatic')
    def _water_log_default(self):
        description = np.recarray((0,), dtype=WATER_DTYPE)
        return append_node(self.store_node, 'water_log', 'table', description)
    
    def log_water(self, ts, infused):
        self.water_log.append([(ts, infused)])
        self.water_updated = True

    # This is actually a pointer to the stored data, which acts like a numpy
    # array for the most part
    trial_data_table = Any(store='automatic')
    trial_data = Property(depends_on='curidx')
    trial_log = Any(store='automatic')

    #updated = Event

    curidx = Int(0)

    # TODO: Is this a performance hit?
    def _get_trial_data(self):
        return self.trial_data_table[:]

    def _set_trial_data(self, data):
        try:
            self.trial_data_table = data
        except (ValueError, TypeError):
            self.trial_data_table = np.array(data, dtype=TRIAL_DTYPE)
        self.curidx = len(self.trial_data_table)

    def _trial_data_table_default(self):
        description = np.recarray((0,), dtype=TRIAL_DTYPE)
        return append_node(self.store_node, 'trial_data', 'table', description)

    def _trial_log_default(self):
        description = np.recarray((0,), dtype=LOG_DTYPE)
        return append_node(self.store_node, 'trial_log', 'table', description)

    safe_indices = Property(Array('i'), store='array', depends_on='curidx')
    warn_indices = Property(Array('i'), store='array', depends_on='curidx')
    remind_indices = Property(Array('i'), store='array', depends_on='curidx')

    warn_ts = Property(Array('f'))
    safe_ts = Property(Array('f'))

    def _get_warn_ts(self):
        return self.trial_data[self.warn_indices]['timestamp']

    def _get_safe_ts(self):
        return self.trial_data[self.safe_indices]['timestamp']

    def _get_safe_indices(self):
        return np.flatnonzero(self.trial_data['type'] == 'safe')

    def _get_warn_indices(self):
        return np.flatnonzero(self.trial_data['type'] == 'warn')

    def _get_remind_indices(self):
        return np.flatnonzero(self.trial_data['type'] == 'remind')

    safe_trials = Property(Array('f'), store='property')
    warn_trials = Property(Array('f'), store='property')

    def _get_safe_trials(self):
        return self.trial_data[self.safe_indices]

    def _get_warn_trials(self):
        return self.trial_data[self.warn_indices]

    # Variables below are information derived from raw data, does not depend on
    # any sort of analysis that may be done on the raw data.

    total_trials = Property(Int, depends_on='curidx', store='attribute')

    par_count = Property(List(Int), depends_on='curidx', store='attribute')
    pars = Property(List(Int), depends_on='curidx')

    par_info = Property(store='table',
                               col_names=['par', 'count'],
                               col_types=['f', 'i'])

    def _get_par_info(self):
        return zip(self.pars, self.par_count)

    safe_par_mask = Property(List(Array(dtype='b')), depends_on='curidx')
    warn_par_mask = Property(List(Array(dtype='b')) , depends_on='curidx')

    updated = Event

    def log(self, timestamp, name, value):
        self.trial_log.append([(timestamp, name, '%r' % value)])

    def update(self, timestamp, par, shock, type):
        self.trial_data_table.append([(timestamp, par, shock, type)])
        self.curidx += 1
        self.updated = timestamp

    @cached_property
    def _get_total_trials(self):
        return len(self.warn_trials)

    @cached_property
    def _get_pars(self):
        # Should be sorted
        return np.unique(self.warn_trials['par'])

    @cached_property
    def _get_safe_par_mask(self):
        return [self.safe_trials['par'] == par for par in self.pars]

    @cached_property
    def _get_warn_par_mask(self):
        return [self.warn_trials['par'] == par for par in self.pars]

    @cached_property
    def _get_par_count(self):
        return apply_mask(len, self.warn_trials, self.warn_par_mask)

class AnalyzedAversiveData(AnalyzedData):

    data = Instance(AversiveData, ())
    updated = Event

    # The next few pars will influence the analysis of the data,
    # specifically the "score".  Anytime these pars change, the data must
    # be reanalyzed.
    contact_offset = CFloat(0.9, store='attribute')
    contact_dur = CFloat(0.1, store='attribute')
    contact_fraction = Range(0.0, 1.0, 0.5, store='attribute')

    # False alarms and hits can only be determined after we score the data.
    # Scores contains the actual contact ratio for each trial.  False alarms and
    # hits are then computed against these scores (using the contact_fraction as
    # the threshold).
    _contact_scores = Array(dtype='f', shape=(1000,))
    contact_scores = Property(Array(dtype='f'), store='array', depends_on='curidx')
    curidx = Int(0)

    def _get_contact_scores(self):
        return self._contact_scores[:self.curidx]

    # These are really just contact scores, hits, misses, etc. made available as
    # various arrays to facilitate analysis and plotting.  Very little
    # computation is done here, just filtering of the data.

    # True/False sequence indicating whether animal was in contact with the
    # spout during the check.
    fa_seq = Property(Array(dtype='f'), depends_on='curidx')
    hit_seq = Property(Array(dtype='f'), depends_on='curidx')
    remind_seq = Property(Array(dtype='f'), depends_on='curidx')

    # Fraction (0 to 1) indicating degree of animal's contact with spout during
    # the check.
    safe_scores = Property(Array(dtype='f'), depends_on='curidx')
    warn_scores = Property(Array(dtype='f'), depends_on='curidx')
    remind_scores = Property(Array(dtype='f'), depends_on='curidx')

    # Actual position in the sequence (used in conjunction with the *_seq
    # properties to generate the score chart used in the view.
    safe_indices = DelegatesTo('data')
    warn_indices = DelegatesTo('data')
    remind_indices = DelegatesTo('data')

    # The summary scores
    pars = DelegatesTo('data')
    par_hit_frac = Property(List(Float), depends_on='curidx')
    par_fa_frac = Property(List(Float), depends_on='curidx')

    par_info = Property(store='table',
                                  col_names=['par', 'hit_frac', 'fa_frac'],
                                  col_types=['f', 'f', 'f'],
                                  )

    def _get_par_info(self):
        return zip(self.pars,
                   self.par_hit_frac,
                   self.par_fa_frac, )

    def score_timestamp(self, ts):
        ts = ts/self.data.contact_fs
        lb, ub = ts + self.contact_offset, ts + self.contact_offset + self.contact_dur
        return self.data.contact_digital.get_range(lb, ub)[0].mean()

    @on_trait_change('data')
    def reprocess_timestamps(self):
        self.curidx = 0
        for ts in self.data.trial_data['timestamp']:
            self.process_timestamp(ts)

    @on_trait_change('data.updated')
    def process_timestamp(self, timestamp):
        # need to check if timestamp is undefined because this apparently fires when the class is initialized
        if timestamp is not Undefined:
            score = self.score_timestamp(timestamp)
            self._contact_scores[self.curidx] = score
            self.curidx += 1
            self.updated = True

    @cached_property
    def _get_par_fa_frac(self):
        return apply_mask(np.mean, self.fa_seq, self.data.safe_par_mask)

    @cached_property
    def _get_par_hit_frac(self):
        return apply_mask(np.mean, self.hit_seq, self.data.warn_par_mask)

    @cached_property
    def _get_fa_seq(self):
        return self.safe_scores < self.contact_fraction

    @cached_property
    def _get_hit_seq(self):
        return self.warn_scores < self.contact_fraction

    @cached_property
    def _get_remind_seq(self):
        return self.remind_scores < self.contact_fraction

    @cached_property
    def _get_safe_scores(self):
        return self.contact_scores[self.data.safe_indices]

    @cached_property
    def _get_warn_scores(self):
        return self.contact_scores[self.data.warn_indices]

    @cached_property
    def _get_remind_scores(self):
        return self.contact_scores[self.data.remind_indices]

if __name__ == '__main__':
    import tables
    f = tables.openFile('test2.h5', 'w')
    data = AversiveData(store_node=f.root)
    #analyzed = AnalyzedAversiveData(data=data)
    from cns.data.persistence import add_or_update_object
    add_or_update_object(data, f.root)

