"""Note that the function and variable names may be a bit ambiguous since I'm
not sure what to call the SAFE/WARN trials.  We need to agree on some sensible
terminology to avoid any confusion.  For example:

    TRIAL - The response to the test signal plus it's associated "false alarms".
    TRIAL BLOCK - All trials presented during an experiment.
"""
#from .experiment_data import ExperimentData, AnalyzedData
from cns.experiment.data.experiment_data import ExperimentData, AnalyzedData
from cns.channel import FileMultiChannel, FileChannel, RAMChannel
from enthought.traits.api import Instance, List, CFloat, Int, Float, Any, \
    Range, DelegatesTo, cached_property, on_trait_change, Array, Event, \
    Property, Undefined, Callable, Str, Enum, Bool
from datetime import datetime
import numpy as np
from cns.data.h5_utils import append_node, get_or_append_node
from cns.pipeline import deinterleave, broadcast
from scipy.stats import norm
from cns.traits.api import Alias

def apply_mask(fun, seq, mask):
    seq = np.array(seq).ravel()
    return [fun(seq[m]) for m in mask]

# All timestamps reflect the sample number of the contact data
WATER_DTYPE = [('timestamp', 'i'), ('infused', 'f')]
TRIAL_DTYPE = [('timestamp', 'i'), ('par', 'f'), ('shock', 'f'), ('type', 'S16'), ]
LOG_DTYPE = [('timestamp', 'i'), ('name', 'S64'), ('value', 'S128'), ]

def migrate_data(data):
    raise NotImplementedError
    if data.version == 0.1:
        old_data = data.__dict__
        new_data = old_data.copy()
        del new_data['__traits_listener__']
        new_data['touch_digital'] = old_data.contact_data[0,:]
        new_data['touch_digital_mean'] = old_data.contact_data[1,:]
        new_data['touch_digital_analog'] = old_data.contact_data[2,:]
        new_data['trial_running'] = old_data.contact_data[3,:]
        return AversiveData(**new_data)
    else:
        return data

class BaseAversiveData(ExperimentData):

    version = Float(0.0)
    latest_version = 0.1

    def log_water(self, ts, infused):
        self.water_log.append([(ts, infused)])
        self.water_updated = True

    def log_event(self, timestamp, name, value):
        self.trial_log.append([(timestamp, name, '%r' % value)])

    def update(self, timestamp, par, shock, type):
        self.trial_data_table.append([(timestamp, par, shock, type)])
        self.curidx += 1
        self.updated = timestamp

    # This is actually a pointer to the stored data, which acts like a numpy
    # array for the most part
    trial_data = Property(depends_on='curidx')
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

    safe_indices = Property(Array('i'), store='array', depends_on='curidx')
    warn_indices = Property(Array('i'), store='array', depends_on='curidx')
    remind_indices = Property(Array('i'), store='array', depends_on='curidx')

    warn_ts = Property(Array('f'))
    safe_ts = Property(Array('f'))

    comment = Str('', store='attribute')
    exit_status = Enum('complete', 'partial', 'aborted', store='attribute')
    start_time = Instance(datetime, store='attribute')
    stop_time = Instance(datetime, store='attribute')
    duration = Property(store='attribute')

    def _get_duration(self):
        if self.stop_time is None:
            return datetime.now()-self.start_time
        else:
            return self.stop_time-self.start_time

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

    safe_trials = Property(Array('f'))
    warn_trials = Property(Array('f'))

    def _get_safe_trials(self):
        return self.trial_data[self.safe_indices]

    def _get_warn_trials(self):
        return self.trial_data[self.warn_indices]

    # Variables below are information derived from raw data, does not depend on
    # any sort of analysis that may be done on the raw data.

    total_trials = Property(Int, depends_on='curidx', store='attribute')

    par_count = Property(List(Int), depends_on='curidx', store='attribute')
    par_safe_count = Property(List(Int), depends_on='curidx', store='attribute')
    pars = Property(List(Int), depends_on='curidx')

    par_info = Property(store='table',
                        col_names=['par', 'safe_count', 'count'],
                        col_types=['f', 'i',  'i'])

    def _get_par_info(self):
        return zip(self.pars, self.par_safe_count, self.par_count)

    safe_par_mask = Property(List(Array(dtype='b')), depends_on='curidx')
    warn_par_mask = Property(List(Array(dtype='b')) , depends_on='curidx')

    updated = Event

    @cached_property
    def _get_total_trials(self):
        return len(self.warn_trials)

    @cached_property
    def _get_pars(self):
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

    @cached_property
    def _get_par_safe_count(self):
        return apply_mask(len, self.safe_trials, self.safe_par_mask)

class RawAversiveData_v0_1(BaseAversiveData):

    version = 0.1

    # This is a bit of a hack but I'm not sure of a better way to send the
    # datafile down the hierarchy.  We need access to this data file so we can
    # stream data to disk rather than storing it in a temporary buffer.
    store_node = Any

    contact_fs = Float

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

    # Stores raw contact data from optical and electrical sensors as well as
    # whether a trial is running.
    contact_data = Instance(FileMultiChannel, store='channel', 
                            store_path='contact')
    water_log = Any(store='automatic')
    trial_log = Any(store='automatic')
    trial_data_table = Any(store='automatic', store_path='trial_data')

    def _contact_data_default(self):
        names = ['digital', 'digital_mean', 'analog', 'trial_running']
        return FileMultiChannel(node=self.store_node, fs=self.contact_fs,
                           name='contact', dtype=np.float32, names=names,
                           channels=4, window_fill=0)

    def _water_log_default(self):
        description = np.recarray((0,), dtype=WATER_DTYPE)
        return append_node(self.store_node, 'water_log', 'table', description)

    def _trial_data_table_default(self):
        description = np.recarray((0,), dtype=TRIAL_DTYPE)
        return append_node(self.store_node, 'trial_data', 'table', description)

    def _trial_log_default(self):
        description = np.recarray((0,), dtype=LOG_DTYPE)
        return append_node(self.store_node, 'trial_log', 'table', description)

class RawAversiveData_v0_2(BaseAversiveData):

    version = 0.2

    store_node = Any
    contact_fs = Float

    contact_data = Any

    touch_digital = Instance(FileChannel, 
            store='channel', store_path='contact/touch_digital')
    touch_digital_mean = Instance(FileChannel, 
            store='channel', store_path='contact/touch_digital_mean')
    touch_analog = Instance(FileChannel, 
            store='channel', store_path='contact/touch_analog')
    optical_digital = Instance(FileChannel, 
            store='channel', store_path='contact/optical_digital')
    optical_digital_mean = Instance(FileChannel, 
            store='channel', store_path='contact/optical_digital_mean')
    optical_analog = Instance(FileChannel, 
            store='channel', store_path='contact/optical_analog')
    trial_running = Instance(FileChannel, 
            store='channel', store_path='contact/trial_running')

    # We can switch back and forth between touch and optical as needed
    contact_digital = Instance(FileChannel, 
            store='channel', store_path='contact/contact_digital')
    contact_digital_mean = Instance(FileChannel, 
            store='channel', store_path='contact/contact_digital_mean')

    contact_digital_memory = Instance(RAMChannel)
    contact_digital_mean_memory = Instance(RAMChannel)
    trial_running_memory = Instance(RAMChannel)

    water_log = Any(store='automatic')
    trial_log = Any(store='automatic')
    trial_data_table = Any(store='automatic', store_path='trial_data')

    # Stores raw contact data from optical and electrical sensors as well as
    # whether a trial is running.
    def _contact_data_default(self):
        targets = [self.touch_digital,
                   self.touch_digital_mean,
                   self.optical_digital,
                   self.optical_digital_mean,
                   broadcast((self.contact_digital,
                              self.contact_digital_memory)),
                   broadcast((self.contact_digital_mean,
                              self.contact_digital_mean_memory)),
                   broadcast((self.trial_running,
                              self.trial_running_memory)), ]
        return deinterleave(targets)

    def _create_channel(self, name, dtype):
        contact_node = get_or_append_node(self.store_node, 'contact')
        return FileChannel(node=contact_node, fs=self.contact_fs,
                           name=name, dtype=dtype)

    def _contact_digital_memory_default(self):
        return RAMChannel(fs=self.contact_fs, window=10)

    def _contact_digital_mean_memory_default(self):
        return RAMChannel(fs=self.contact_fs, window=10)

    def _trial_running_memory_default(self):
        return RAMChannel(fs=self.contact_fs, window=10)

    def _contact_digital_default(self):
        return self._create_channel('contact_digital', np.bool)

    def _contact_digital_mean_default(self):
        return self._create_channel('contact_digital_mean', np.float32)

    def _touch_digital_default(self):
        return self._create_channel('touch_digital', np.bool)

    def _touch_digital_mean_default(self):
        return self._create_channel('touch_digital_mean', np.float32)

    def _touch_analog_default(self):
        return self._create_channel('touch_analog', np.float32)

    def _optical_digital_default(self):
        return self._create_channel('optical_digital', np.bool)

    def _optical_digital_mean_default(self):
        return self._create_channel('optical_digital_mean', np.float32)

    def _optical_analog_default(self):
        return self._create_channel('optical_analog', np.float32)

    def _trial_running_default(self):
        return self._create_channel('trial_running', np.bool)

    def _water_log_default(self):
        description = np.recarray((0,), dtype=WATER_DTYPE)
        return append_node(self.store_node, 'water_log', 'table', description)

    def _trial_data_table_default(self):
        description = np.recarray((0,), dtype=TRIAL_DTYPE)
        return append_node(self.store_node, 'trial_data', 'table', description)

    def _trial_log_default(self):
        description = np.recarray((0,), dtype=LOG_DTYPE)
        return append_node(self.store_node, 'trial_log', 'table', description)

# For legacy reasons, we will let AversiveData = RawAversiveData_v0_1
#AversiveData = RawAversiveData_v0_1
AversiveData = RawAversiveData_v0_2

class AnalyzedAversiveData(AnalyzedData):

    data = Instance(BaseAversiveData, ())
    updated = Event

    # The next few pars will influence the analysis of the data,
    # specifically the "score".  Anytime these pars change, the data must
    # be reanalyzed.
    contact_offset = CFloat(0.9, store='attribute')
    contact_dur = CFloat(0.1, store='attribute')
    contact_fraction = Range(0.0, 1.0, 0.5, store='attribute')

    # Clip FA/HIT rate if it is < clip or > 1-clip (prevents unusually high
    # z-scores)
    clip = Float(0.05, store='attribute')

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
    par_z_hit = Property(List(Float), depends_on='curidx')
    par_z_fa = Property(List(Float), depends_on='curidx')
    par_dprime = Property(List(Float), depends_on='curidx, use_global_fa_frac')
    par_dprime_nonglobal = Property(List(Float), depends_on='curidx')
    par_dprime_global = Property(List(Float), depends_on='curidx')
    global_fa_frac = Property(Float, depends_on='curidx', store='attribute')

    use_global_fa_frac = Bool(False)

    par_info = Property(store='table',
                        col_names=['par', 'safe_trials', 'warn_trials',
                                   'hit_frac', 'fa_frac', 'd', 'd_global'],
                        col_types=['f', 'i', 'i', 'f', 'f', 'f', 'f'],)

    def _get_par_info(self):
        return zip(self.pars,
                   self.data.par_safe_count,
                   self.data.par_count,
                   self.par_hit_frac,
                   self.par_fa_frac, 
                   self.par_dprime_nonglobal,
                   self.par_dprime_global, )

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
        # need to check if timestamp is undefined because this apparently fires
        # when the class is initialized
        if timestamp is not Undefined:
            score = self.score_timestamp(timestamp)
            self._contact_scores[self.curidx] = score
            self.curidx += 1
            self.updated = True

    @cached_property
    def _get_fa_seq(self):
        return self.safe_scores < self.contact_fraction

    @cached_property
    def _get_hit_seq(self):
        return self.warn_scores < self.contact_fraction

    @cached_property
    def _get_remind_seq(self):
        return self.remind_scores < self.contact_fraction

    # We need to check curidx to see if there are any contact scores.  If curidx
    # is 0, this means that code somewhere has requested the value of these
    # properties before any data is available. 
    @cached_property
    def _get_safe_scores(self):
        if self.curidx == 0:
            return np.array([])
        return self.contact_scores[self.safe_indices]

    @cached_property
    def _get_warn_scores(self):
        if self.curidx == 0:
            return np.array([])
        return self.contact_scores[self.warn_indices]

    @cached_property
    def _get_remind_scores(self):
        if self.curidx == 0:
            return np.array([])
        return self.contact_scores[self.remind_indices]

    @cached_property
    def _get_par_fa_frac(self):
        return apply_mask(np.mean, self.fa_seq, self.data.safe_par_mask)

    @cached_property
    def _get_par_hit_frac(self):
        return apply_mask(np.mean, self.hit_seq, self.data.warn_par_mask)

    @cached_property
    def _get_par_z_hit(self):
        par_hit_frac = np.clip(self.par_hit_frac, self.clip, 1-self.clip)
        return norm.ppf(par_hit_frac)

    @cached_property
    def _get_par_z_fa(self):
        par_fa_frac = np.clip(self.par_fa_frac, self.clip, 1-self.clip)
        return norm.ppf(par_fa_frac)

    @cached_property
    def _get_par_dprime(self):
        if self.use_global_fa_frac:
            return self.par_dprime_global
        else:
            return self.par_dprime_nonglobal

    @cached_property
    def _get_par_dprime_nonglobal(self):
        return self.par_z_hit-self.par_z_fa

    @cached_property
    def _get_par_dprime_global(self):
        return self.par_z_hit-norm.ppf(self.global_fa_frac)

    @cached_property
    def _get_global_fa_frac(self):
        return self.fa_seq.mean()

if __name__ == '__main__':
    import tables
    f = tables.openFile('test2.h5', 'w')
    data = AversiveData(store_node=f.root)
    #analyzed = AnalyzedAversiveData(data=data)
    from cns.data.persistence import add_or_update_object
    add_or_update_object(data, f.root)