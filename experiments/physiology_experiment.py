import numpy as np
from enthought.enable.api import Component, ComponentEditor
from enthought.chaco.api import (LinearMapper, DataRange1D,
        OverlayPlotContainer)
from enthought.traits.ui.api import VGroup, HGroup, Item, Include, View, \
        InstanceEditor, RangeEditor, HSplit, Tabbed
from enthought.traits.api import Instance, HasTraits, Float, DelegatesTo, \
     Bool, on_trait_change, Int, on_trait_change, Any, Range, Event, Property,\
     Tuple, List
from enthought.traits.ui.editors import RangeEditor

from physiology_paradigm import PhysiologyParadigm
from physiology_data import PhysiologyData
from physiology_controller import PhysiologyController

from enthought.chaco.api import PlotAxis, VPlotContainer, PlotAxis
from enthought.chaco.tools.api import ZoomTool
from cns.chaco_exts.tools.window_tool import WindowTool
from cns.chaco_exts.helpers import add_default_grids, add_time_axis
from cns.chaco_exts.channel_data_range import ChannelDataRange
from cns.chaco_exts.timeseries_plot import TimeseriesPlot
from cns.chaco_exts.extremes_channel_plot import ExtremesChannelPlot
from cns.chaco_exts.ttl_plot import TTLPlot
from cns.chaco_exts.channel_range_tool import MultiChannelRangeTool
from cns.chaco_exts.channel_number_overlay import ChannelNumberOverlay
from cns.chaco_exts.snippet_channel_plot import SnippetChannelPlot
from cns import get_config

from cns.chaco_exts.spike_overlay import SpikeOverlay
from cns.chaco_exts.threshold_overlay import ThresholdOverlay

CHANNELS = get_config('PHYSIOLOGY_CHANNELS')
VOLTAGE_SCALE = 1e3
scale_formatter = lambda x: "{:.2f}".format(x*VOLTAGE_SCALE)

from enthought.traits.ui.menu import MenuBar, Menu, ActionGroup, Action

def create_menubar():
    actions = ActionGroup(
            Action(name='Load settings', action='load_settings'),
            Action(name='Save settings as', action='saveas_settings'),
            )
    menu = Menu(actions, name='&Physiology')
    return MenuBar(menu)

def ptt(event_times, trig_times):
    return np.concatenate([event_times-tt for tt in trig_times])

#class Histogram(HasTraits):
    
#    channel = Range(1, CHANNELS, 1)
    #spikes = Any
    #timeseries = Any
    #bin_size = Float(0.25)
    #bin_lb = Float(-1)
    #bin_ub = Float(5)
    
    #bins = Property(depends_on='bin_+')
    
    #def _get_bins(self):
        #return np.arange(self.bin_lb, self.bin_ub, self.bin_size)
    
    #def _get_counts(self):
        #spikes = self.spikes[self.channel-1]
        #et = spikes.timestamps
        #return np.histogram(ptt(self.channel.times
    
    #def _get_histogram(self):
        #self.spikes.timestamps[:]

class SortWindow(HasTraits):

    settings    = Any
    channels    = Any
    channel     = Range(1, CHANNELS, 1)
    
    plot        = Instance(SnippetChannelPlot)
    threshold   = Property(Float, depends_on='channel')
    windows     = Property(List(Tuple(Float, Float, Float)), depends_on='channel')
    tool        = Instance(WindowTool)
    
    def _get_threshold(self):
        return self.settings[self.channel-1].spike_threshold*VOLTAGE_SCALE
    
    def _set_threshold(self, value):
        self.settings[self.channel-1].spike_threshold = value/VOLTAGE_SCALE
        
    def _get_windows(self):
        if self.settings is None:
            return []
        return self.settings[self.channel-1].spike_windows
    
    def _set_windows(self, value):
        if self.settings is None:
            return
        self.settings[self.channel-1].spike_windows = value

    def _channel_changed(self, new):
        self.plot.channel = self.channels[new-1]

    def _plot_default(self):
        # Create the plot
        index_mapper = LinearMapper(range=DataRange1D(low=0, high=0.0012))
        value_mapper = LinearMapper(range=DataRange1D(low=-0.00025, high=0.00025))
        plot = SnippetChannelPlot(history=20,
                channel=self.channels[self.channel-1],
                value_mapper=value_mapper, 
                index_mapper=index_mapper,
                bgcolor='white', padding=[60, 10, 10, 40])
        add_default_grids(plot, major_index=1e-3, minor_index=1e-4,
                major_value=1e-3, minor_value=1e-4)

        # Add the axes labels
        axis = PlotAxis(orientation='left', component=plot,
                tick_label_formatter=scale_formatter, title='Volts (mV)')
        plot.overlays.append(axis)
        axis = PlotAxis(orientation='bottom', component=plot, title='Time (ms)',
                tick_label_formatter=scale_formatter)
        plot.overlays.append(axis)

        # Add the tools
        zoom = ZoomTool(plot, drag_button=None, axis="value")
        plot.overlays.append(zoom)
        self.tool = WindowTool(component=plot)
        plot.overlays.append(self.tool)
        
        # Whenever we draw a window, the settings should immediately be updated!
        self.sync_trait('windows', self.tool)
        return plot

    traits_view = View(
            VGroup(
                Item('channel'),
                Item('threshold', editor=RangeEditor(low=0*VOLTAGE_SCALE, 
                                                     high=5e-4*VOLTAGE_SCALE)),
                Item('plot', editor=ComponentEditor(width=250, height=250)),
                show_labels=False,
                ),
            )

class PhysiologyExperiment(HasTraits):

    settings                 = Instance(PhysiologyParadigm, ())
    data                     = Instance(PhysiologyData)

    physiology_container     = Instance(Component)
    physiology_plot          = Instance(Component)
    physiology_index_range   = Instance(ChannelDataRange)
    physiology_value_range   = Instance(DataRange1D, ())

    physiology_channel_span  = Float(0.5e-3)

    physiology_window_1      = Instance(SortWindow)
    physiology_window_2      = Instance(SortWindow)
    physiology_window_3      = Instance(SortWindow)
    
    visualize_sorting        = Bool(False)
    
    spike_overlay            = Instance(SpikeOverlay)
    threshold_overlay        = Instance(ThresholdOverlay)
    parent                   = Any

    def _physiology_sort_map_default(self):
        return [(0.0001, []) for i in range(16)]

    @on_trait_change('data')
    def _physiology_sort_plots(self):
        settings = self.settings.channel_settings
        channels = self.data.physiology_spikes
        
        window = SortWindow(channel=1, settings=settings, channels=channels)
        self.physiology_window_1 = window
        window = SortWindow(channel=5, settings=settings, channels=channels)
        self.physiology_window_2 = window
        window = SortWindow(channel=9, settings=settings, channels=channels)
        self.physiology_window_3 = window

    @on_trait_change('physiology_plot.channel_visible, physiology_channel_span')
    def _physiology_value_range_update(self):
        span = self.physiology_channel_span
        visible = len(self.physiology_plot.channel_visible)
        self.physiology_value_range.high_setting = visible*span
        self.physiology_value_range.low_setting = 0
        self.physiology_plot.channel_offset = span/2.0
        self.physiology_plot.channel_spacing = span

    def _physiology_channel_span_changed(self):
        self._physiology_value_range_update()

    def _physiology_channel_span_changed(self):
        self._physiology_value_range_update()

    @on_trait_change('data, parent')
    def _generate_physiology_plot(self):
        # Padding is in left, right, top, bottom order
        container = OverlayPlotContainer(padding=[50, 20, 20, 50])

        # Create the index range shared by all the plot components
        self.physiology_index_range = ChannelDataRange(span=5, trig_delay=1,
                timeseries=self.data.physiology_ts,
                sources=[self.data.physiology_processed])

        # Create the TTL plot
        index_mapper = LinearMapper(range=self.physiology_index_range)
        value_mapper = LinearMapper(range=DataRange1D(low=0, high=1))
        plot = TTLPlot(channel=self.data.physiology_sweep,
                index_mapper=index_mapper, value_mapper=value_mapper,
                reference=0, fill_color=(0.25, 0.41, 0.88, 0.1),
                line_color='transparent', rect_center=0.5, rect_height=1.0)
        add_default_grids(plot, major_index=1, minor_index=0.25)
        container.add(plot)

        # Create the neural plots
        value_mapper = LinearMapper(range=self.physiology_value_range)
        plot = ExtremesChannelPlot(channel=self.data.physiology_processed, 
                index_mapper=index_mapper, value_mapper=value_mapper)
        plot.overlays.append(ChannelNumberOverlay(plot=plot))
        container.add(plot)
        add_default_grids(plot, major_index=1, minor_index=0.25,
                major_value=1e-3, minor_value=1e-4)
        axis = PlotAxis(component=plot, orientation='left',
                tick_label_formatter=scale_formatter, title='Volts (mV)')
        plot.underlays.append(axis)
        add_time_axis(plot, 'bottom', fraction=True)
        self.physiology_plot = plot

        tool = MultiChannelRangeTool(component=plot)
        plot.tools.append(tool)

        overlay = SpikeOverlay(plot=plot, spikes=self.data.physiology_spikes)
        self.sync_trait('visualize_sorting', overlay, 'visible', mutual=False)
        plot.overlays.append(overlay)
        self.spike_overlay = overlay
        overlay = ThresholdOverlay(plot=plot, visible=False)
        self.sync_trait('visualize_sorting', overlay, 'visible', mutual=False)
        self.settings.sync_trait('spike_thresholds', overlay, 'thresholds',
                mutual=False)
        plot.overlays.append(overlay)
        self.threshold_overlay = overlay

        # Hack alert.  Can we separate this out into a separate function?
        if self.parent is not None:
            self.parent._add_behavior_plots(index_mapper,
                    self.physiology_container)

        self.physiology_container = container
        self._physiology_value_range_update()

    physiology_settings_group = VGroup(
            Item('settings', style='custom',
                editor=InstanceEditor(view='physiology_view')),
            Include('physiology_view_settings_group'),
            show_border=True,
            show_labels=False,
            label='Channel settings'
            )

    physiology_view_settings_group = VGroup(
            Item('object.physiology_index_range.update_mode', 
                label='Trigger mode'),
            Item('object.physiology_index_range.span',
                label='X span',
                editor=RangeEditor(low=0.1, high=30.0)),
            Item('object.physiology_index_range.trig_delay',
                label='Trigger delay',
                editor=RangeEditor(low=0.0, high=10.0)),
            Item('physiology_channel_span', label='Y span',
                editor=RangeEditor(low=0, high=5e-3)),
            label='Plot Settings',
            show_border=True,
            )

    physiology_view = View(
            HSplit(
                Tabbed(
                    Include('physiology_settings_group'),
                    VGroup(
                        Item('visualize_sorting', label='Show spike sort overlay?'),
                        Item('physiology_window_1', style='custom', width=250),
                        Item('physiology_window_2', style='custom', width=250),
                        Item('physiology_window_3', style='custom', width=250),
                        show_labels=False,
                        label='Sort settings'
                        ),
                    VGroup(
                        Item('object.threshold_overlay', style='custom'),
                        Item('object.spike_overlay', style='custom'),
                        show_labels=False,
                        label='GUI settings'
                        ),
                    ),
                Item('physiology_container', 
                    editor=ComponentEditor(width=1200, height=800), 
                    width=1200,
                    resizable=True),
                show_labels=False,
                ),
            menubar=create_menubar(),
            handler=PhysiologyController,
            resizable=True)

if __name__ == '__main__':
    import tables
    from cns import get_config
    from os.path import join
    tempfile = join(get_config('TEMP_ROOT'), 'test_physiology.h5')
    datafile = tables.openFile(tempfile, 'w')
    data = PhysiologyData(store_node=datafile.root)
    PhysiologyExperiment(data=data).configure_traits()