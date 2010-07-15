from .experiment_controller import ExperimentController
from cns import choice, equipment
from cns.data.persistence import append_node, append_date_node, \
    add_or_update_object, get_or_append_node
from cns.experiment.data import AversiveData
from cns.experiment.paradigm import AversiveParadigm
from cns.widgets import icons
from cns.widgets.toolbar import ToolBar
from datetime import timedelta
from enthought.etsconfig.etsconfig import ETSConfig
from enthought.pyface.api import error
from enthought.pyface.timer.api import Timer
from enthought.savage.traits.ui.svg_button import SVGButton
from enthought.traits.api import Any, Instance, CInt, CFloat, Str, Float, \
    Property, HasTraits, Bool, on_trait_change, Dict, Button, Event
from enthought.traits.ui.api import HGroup, spring, Item, View
import logging
import time

log = logging.getLogger(__name__)

class AversiveToolBar(ToolBar):

    handler = Any
    size = 24, 24

    if ETSConfig.toolkit == 'qt4':
        kw = dict(height=24, width=24)
        apply = SVGButton('Apply', filename=icons.apply,
                          tooltip='Apply settings', **kw)
        revert = SVGButton('Revert', filename=icons.undo,
                          tooltip='Revert settings', **kw)
        start = SVGButton('Run', filename=icons.start,
                          tooltip='Begin experiment', **kw)
        pause = SVGButton('Pause', filename=icons.pause,
                          tooltip='Pause', **kw)
        resume = SVGButton('Resume', filename=icons.resume,
                          tooltip='Resume', **kw)
        stop = SVGButton('Stop', filename=icons.stop,
                          tooltip='stop', **kw)
        remind = SVGButton('Remind', filename=icons.warn,
                          tooltip='Remind', **kw)

        item_kw = dict(show_label=False)

    else:
        # The WX backend renderer for SVG buttons is ugly, so let's use text
        # buttons instead.
        apply = Button('A')
        start = Button('>>')
        pause = Button('||')
        stop = Button('X')
        remind = Button('!')
        item_kw = dict(show_label=False, height= -22, width= -22)

    group = HGroup(Item('apply',
                        enabled_when="object.handler.pending_changes<>{}",
                        **item_kw),
                   Item('revert',
                        enabled_when="object.handler.pending_changes<>{}",
                        **item_kw),
                   Item('start',
                        enabled_when="object.handler.state=='halted'",
                        **item_kw),
                   '_',
                   Item('remind',
                        enabled_when="object.handler.state=='paused'",
                        **item_kw),
                   Item('pause',
                        enabled_when="object.handler.state=='running'",
                        **item_kw),
                   Item('resume',
                        enabled_when="object.handler.state=='paused'",
                        **item_kw),
                   Item('stop',
                        enabled_when="object.handler.state in " +\
                                     "['running', 'paused', 'manual']",
                        **item_kw),
                   spring,
                   springy=True,
                   )

    trait_view = View(group, kind='subpanel')

    def _apply_fired(self):
        self.handler.apply()

    def _revert_fired(self):
        self.handler.revert()

    def _remind_fired(self):
        self.handler.remind()

    def _start_fired(self):
        self.handler.run()

    def _pause_fired(self):
        self.handler.pause()

    def _resume_fired(self):
        self.handler.resume()

    def _stop_fired(self):
        self.handler.stop()

class CurrentSettings(HasTraits):

    paradigm = Instance(AversiveParadigm)
    
    '''Tracks the trial index for comparision with the circuit index'''
    idx = CInt(0)

    '''Number of safe trials''' 
    safe_trials = CInt
    '''The trial we are going to, or currently, presenting'''
    trial = CInt

    '''Parameter to present'''
    par = CFloat
    par_remind = CFloat

    _choice_num_safe = Any
    _choice_par = Any
    _signal_warn_cache = {}
    _shock_level_cache = {}

    signal_warn = Property
    signal_remind = Property
    shock_warn = Property
    shock_remind = Property

    def __init__(self, **kw):
        super(CurrentSettings, self).__init__(**kw)
        self.initialize(self.paradigm)

    def reset(self):
        self.initialize(self.paradigm)

    def initialize(self, paradigm):
        self._choice_par = self._get_choice_par(paradigm)
        self._choice_num_safe = self._get_choice_num_safe(paradigm)
        self.build_signal_cache(paradigm)
        self.build_shock_level_cache(paradigm)
        self.par_remind = paradigm.par_remind
        self.next()

    def next(self):
        self.par = self._choice_par.next()
        self.safe_trials = self._choice_num_safe.next()
        self.trial = 1
        self.shock_level = self.paradigm.shock_settings.get_level(self.par)

    #===========================================================================
    # Helpers for run-time control of experiment
    #===========================================================================
    def _get_signal_warn(self):
        return self._signal_warn_cache[self.par]

    def _get_signal_remind(self):
        return self._signal_warn_cache[self.par_remind]

    def _get_shock_warn(self):
        return 0
        #return self._shock_level_cache[self.par]

    def _get_shock_remind(self):
        return 0
        #return self._shock_level_cache[self.par_remind]

    def _get_choice_num_safe(self, paradigm):
        trials = range(paradigm.min_safe, paradigm.max_safe + 1)
        return choice.get('pseudorandom', trials)

    def _get_choice_par(self, paradigm):
        # Always pass a copy of pars to other functions that may modify the content of the list
        return choice.get(paradigm.par_order, paradigm.pars[:])

    def _generate_signal(self, template, parameter):
        signal = template.__class__()
        errors = signal.copy_traits(template)
        if errors:
            raise BaseException('Unable to copy traits to new signal')
        signal.set_variable(parameter)
        return signal

    def build_signal_cache(self, paradigm):
        self._signal_warn_cache = {}
        for par in paradigm.pars:
            signal = self._generate_signal(paradigm.signal_warn, par)
            self._signal_warn_cache[par] = signal
        signal = self._generate_signal(paradigm.signal_warn, paradigm.par_remind)
        self._signal_warn_cache[paradigm.par_remind] = signal

    def build_shock_level_cache(self, paradigm):
        self._shock_level_cache = {}
        for setting in paradigm.shock_settings.levels:
            self._shock_level_cache[setting.par] = setting.level
        remind_shock = paradigm.shock_settings.max_shock
        self._shock_level_cache[paradigm.par_remind] = remind_shock

class AversiveController(ExperimentController):
    """Primary controller for TDT System 3 hardware.  This class must be
    configured with a model that contains the appropriate parameters (e.g.
    Paradigm) and a view to show these parameters.

    As changes are applied to the view, the necessary changes to the hardware
    (e.g. RX6 tags and PA5 attenuation) will be made and the model will be
    updated.

    For a primer on model-view-controller architecture and its relation to the
    Enthought libraries (e.g. Traits), refer to the Enthought Tool Suite
    documentation online at:
    https://svn.enthought.com/enthought/wiki/UnderstandingMVCAndTraitsUI
    """
    toolbar = Instance(AversiveToolBar, ())

    backend = Any
    circuit = Any
    pump = Any

    exp_node = Any
    data_node = Any

    # Will be used to poll the state of the hardware every few milliseconds and
    # update the view as needed (i.e. download lick data, upload new signal
    # waveforms, etc).  See timer_tick.
    fast_timer = Instance(Timer)
    slow_timer = Instance(Timer)

    # These are variables tracked by the controller to assist with providing
    # feedback to the user via the view.  While these could be stored in the
    # model (i.e. the paradigm object), they are transient variables that are
    # needed to track the system's state (i.e. what trial number are we on and
    # what is the next parameter that needs to be presented) and are not needed
    # once the experiment is done.  A good rule of thumb: if the parameter is
    # used as a placeholder for transient data (to better compute variables
    # needed for the view), it should be left out of the "model".  Hence, we
    # keep them here instead.
    current = Instance(CurrentSettings)

    # A coroutine pipeline that acquires contact data from the RX6 and sends it
    # to the TrialData object
    data_pipe = Any
    start_time = Float
    completed = Bool(False)
    water_infused = Float(0)

    status = Property(Str, depends_on='current.trial, current.par, current.safe_trials, state')
    time_elapsed = Property(Str, depends_on='slow_tick', label='Time')

    slow_tick = Event
    fast_tick = Event

    def init(self, info):
        # Install the toolbar handler
        self.model = info.object
        self.toolbar.install(self, info)
        try:
            self.init_equipment(info)
        except equipment.EquipmentError, e:
            self.state = 'disconnected'
            error(info.ui.control, str(e))

    def init_equipment(self, info):
        self.pump = equipment.pump().Pump()
        self.backend = equipment.dsp()
        self.circuit = self.backend.load('aversive-behavior', 'RX6')
        #self.atten = equipment.attenuator()

    def configure_circuit(self, circuit, paradigm):
        if circuit is None:
            return
        elif circuit.running:
            raise SystemError, 'Cannot configure circuit while it is running'

        # This is an example of the "handler" approach.  The model
        # ('paradigm') does not have to concern itself about how the
        # equipment needs to be configured.  If we ever get a new set of
        # hardware, this code would be the only stuff that needs changing.
        circuit.reload()

        circuit.lick_th.value = paradigm.lick_th
        circuit.shock_n.set(0.3, src_unit='s')
        circuit.shock_delay_n.set(paradigm.shock_delay, src_unit='s')
        circuit.lick_nPer.set(paradigm.requested_lick_fs, 'fs')

        circuit.trial_buf.initialize(fs=circuit.fs)
        circuit.int_buf.initialize(fs=circuit.fs)
        circuit.int_buf.set(paradigm.signal_safe)
        circuit.contact_buf.initialize(channels=4, sf=1, fs=circuit.lick_nPer.get('fs'))
        circuit.pause_state.value = True
        self.backend.set_attenuation(paradigm.signal_safe.attenuation, 'PA5')
        
        #self.atten.register(paradigm.signal_safe)

    def initialize_data(self, model):
        model.exp_node = append_date_node(model.store_node, pre='aversive_date_')
        model.data_node = append_node(model.exp_node, 'Data')

        # This is a hack.  The buffer objects should just communicate their fs directly.
        model.data = AversiveData(contact_fs=self.circuit.lick_nPer.get('fs'),
                                  store_node=model.data_node)

    def run(self):
        if not self.model.paradigm.is_valid():
            mesg = 'Please correct the following errors first:\n'
            mesg += self.model.paradigm.err_messages()
            error(self.info.ui.control, mesg)
            return

        try:
            # Order is important.  The data depends on several properties set in the circuit, so initialize_data must be called after initialize_circuit
            self.configure_circuit(self.circuit, self.model.paradigm)
            self.initialize_data(self.model)

            #===================================================================
            # Initialize parameters
            #===================================================================
            self.current = CurrentSettings(paradigm=self.model.paradigm)
            self.circuit.trial_buf.set(self.current.signal_warn)

            #===================================================================
            # Finally, everything's a go!
            #===================================================================
            self.fast_timer = Timer(250, self.tick, 'fast')
            self.slow_timer = Timer(1000, self.tick, 'slow')
            self.start_time = time.time()

            # Setting state to paused should be one of the last things we do to
            # prevent the UI from changing the controls to the 'running' state.
            self.state = 'paused'
            self.circuit.start()
            self.model.trial_blocks += 1

        except BaseException, e:
            self.state = 'halted'
            error(self.info.ui.control, str(e))
            raise

    def remind(self, info=None):
        self.state = 'manual'
        # The actual sequence is important.  We must finish uploading the signal
        # before we set the circuit flags to allow commencement of a trial.
        self.circuit.trial_buf.set(self.current.signal_remind)
        self.backend.set_attenuation(self.current.signal_remind.attenuation, 'PA5')
        self.circuit.shock_level.value = self.current.shock_remind
        print self.circuit.shock_level.value
        print self.circuit.actual_shock.value
        #self.circuit.trigger(1) # Go into warning on next trial
        self.circuit.pause_state.value = False # Everything's ready. GO!
        self.circuit.trigger(2)
        self.circuit.trigger(1)

    def pause(self, info=None):
        self.state = 'paused'
        self.circuit.pause_state.value = True

    def resume(self, info=None):
        #self.circuit.trigger(1)
        self.state = 'running'
        self.circuit.pause_state.value = False
        self.circuit.trigger(1)

    def stop(self):
        self.state = 'halted'
        self.slow_timer.stop()
        self.fast_timer.stop()
        self.circuit.stop()
        self.pending_changes = {}
        self.old_values = {}

        # Save the data in our newly created node
        add_or_update_object(self.model.paradigm, self.model.exp_node, 'Paradigm')
        add_or_update_object(self.model.data, self.model.exp_node, 'Data')
        analyzed_node = get_or_append_node(self.model.data.store_node, 'Analyzed')
        add_or_update_object(self.model.analyzed, analyzed_node)

    #===========================================================================
    # Tasks driven by the slow and fast timers
    #===========================================================================
    @on_trait_change('slow_tick')
    def task_update_pump(self):
        infused = self.pump.infused
        self.model.data.log_water(self.circuit.ts_n.value, infused)
        self.water_infused = infused
        
    @on_trait_change('fast_tick')
    def task_update_data(self):
        data = self.circuit.contact_buf.read()
        self.model.data.contact_data.send(data)

    @on_trait_change('fast_tick')
    def task_monitor_signal_safe(self):
        if self.circuit.int_buf.block_processed():
            samples = self.model.paradigm.signal_safe.read_block()
            self.circuit.int_buf.write(samples)

    @on_trait_change('fast_tick')
    def task_monitor_circuit(self):
        if self.circuit.idx.value > self.current.idx:
            self.current.idx += 1
            ts = self.circuit.lick_ts_trial_start_n.value

            # Process "reminder" signals
            if self.state == 'manual':
                self.pause()
                self.model.data.update(ts,
                                       self.current.par_remind,
                                       self.current.shock_remind,
                                       'remind')
                self.circuit.trial_buf.set(self.current.signal_warn)
                self.backend.set_attenuation(self.current.signal_warn.attenuation, 'PA5')
                self.circuit.shock_level.value = self.current.shock_level

            # Warning was just presented.
            else:
                last_trial = self.current.trial
                self.current.trial += 1     # reminders do not count
                # We are now looking at the current trial that will be presented.  
                # What do we need to do to get ready?
                
                if last_trial == self.current.safe_trials + 1:
                #if self.current.trial == self.current.safe_trials + 1:
                    log.debug('processing warning trial')
                    self.model.data.update(ts,
                                           self.current.par,
                                           self.current.shock_warn,
                                           'warn')
                    self.current.next()
                elif last_trial == self.current.safe_trials: 
                    self.model.data.update(ts, self.current.par, 0, 'safe')
                    self.circuit.trial_buf.set(self.current.signal_warn)
                    self.backend.set_attenuation(self.current.signal_warn.attenuation, 'PA5')
                    self.circuit.shock_level.value = self.current.shock_warn
                    self.circuit.trigger(2)
                elif last_trial < self.current.safe_trials:
                    self.model.data.update(ts, self.current.par, 0, 'safe')
                else:
                    raise SystemError, 'There is a mismatch.'
                    # TODO: Data has not been lost so we should not halt execution.
                    # However an appropriate warning should be sent.
                    
            # Signal to the circuit that data processing is done and it can commence execution
            self.circuit.trigger(1)

    def _get_time_elapsed(self):
        if self.state is 'halted':
            seconds = 0
        else:
            seconds = int(time.time() - self.start_time)
        return '%s' % timedelta(seconds=seconds)

    def _get_status(self):
        if self.state == 'disconnected':
            return 'Cannot connect to equipment'
        if self.state == 'halted':
            return 'System is halted'
        if self.state == 'manual':
            return 'PAUSED: presenting reminder (%r)' % self.current.par

        if self.current.trial > self.current.safe_trials:
            status = 'WARNING (%r)' % self.current.par
        else:
            mesg = 'SAFE %d of %d (%r)'
            status = mesg % (self.current.trial, self.current.safe_trials, self.current.par)
        if self.state == 'paused':
            status = 'PAUSED: next trial is %s' % status
        return status

    pending_changes = Dict({})
    old_values = Dict({})

    @on_trait_change('model.paradigm.+', 'model.paradigm.signal_safe.+',
                     'model.paradigm.signal_warn.+', 'model.paradigm.shock_settings.+',
                     'model.paradigm.shock_settings.levels.level')
    def log_changes(self, object, name, old, new):
        #log.debug('log_changes: %r, %r, %r, %r', object, name, old, new)
        if self.state <> 'halted':
            key = object, name
            if key not in self.old_values:
                self.old_values[key] = old
                self.pending_changes[key] = new
            elif new == self.old_values[key]:
                del self.pending_changes[key]
                del self.old_values[key]
            else:
                self.pending_changes[key] = new

    def apply(self):
        reset_settings = False
        ts = self.circuit.ts_n.value
        for (object, name), value in self.pending_changes.items():
            log.debug('Value changed during experiment: %s = %r', name, value)
            if name == 'lick_th':
                self.circuit.lick_th.value = value
                self.model.data.log(ts, name, value)
            elif name in ('par_order', 'par_remind', 'pars'):
                reset_settings = True
                self.model.data.log(ts, name, value)
            elif name == 'pars':
                reset_settings = True
                self.model.data.log(ts, name, value)
            elif name == 'level' or name == 'max_shock':
                reset_settings = True
            elif name == 'levels_items':
                reset_settings = True
            else:
                raise ValueError, 'Cannot change parameter %s while running' % name
            del self.pending_changes[(object, name)]
            del self.old_values[(object, name)]
        if reset_settings:
            self.current.reset()

    def revert(self):
        log.debug('reverting changes')
        for (object, name), value in self.old_values.items():
            log.debug('reverting changes for %s', name)
            setattr(object, name, value)
        self.old_values = {}
        self.pending_changes = {}
        
    count = CInt(0)
    
    def close(self, info, is_ok):
        if self.state != 'halted':
            mesg = 'Please halt experiment before attempting to close window.'
            error(info.ui.control, mesg)
            return False
        else:
            return True