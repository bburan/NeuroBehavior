from cns.widgets import icons
from cns.signal import Signal, type as st
from cns.signal.type import signal_types
from cns.signal.view_factory import signal_view_factory
from enthought.traits.api import HasTraits, Instance, Str, Bool, Button
from enthought.traits.ui.api import View, Item, InstanceEditor, Handler, spring
from enthought.traits.ui.instance_choice import InstanceFactoryChoice
from enthought.savage.traits.ui.svg_button import SVGButton

class SignalEditHandler(Handler):
    '''Handler that allows one to access the popup_view of the SignalSelector
    class via a handler button.
    '''

    from enthought.etsconfig.api import ETSConfig

    if ETSConfig.toolkit == 'wx':
        edit_signal = Button('E')
    else:
        edit_signal = SVGButton(filename=icons.configure, tooltip='Edit Signal',
                                height=24, width=24)

    def handler_edit_signal_changed(self, info):
        info.object.edit_traits(view='popup_view')

class StrictChoice(InstanceFactoryChoice):
    '''The default behavior is to return true if the selected object is a
    subclass of self.klass.  Since we use subclassing to generate various signal
    types (e.g.  AMTone is a subclass of Tone), we need to ensure that the
    object class is indeed the class represented by this option.
    '''

    allow_par = Bool(True)

    def is_compatible(self, object):
        return object.__class__ is self.klass

    def get_view(self):
        return signal_view_factory(self.klass, include_variable=self.allow_par)

class SignalSelector(HasTraits):
    '''Generates a signal selector dialog using the
    :module:`enthought.traits.ui.api.InstanceEditor` class.
    '''
    signal = Instance(Signal, st.Tone())
    title = Str('Edit Signal')
    allow_par = Bool(True)

    def traits_view(self, parent=None):
        return View(['signal{}~', spring, 'handler.edit_signal{}', '-'],
                    handler=SignalEditHandler)

    def popup_view(self, parent=None):
        choices = [StrictChoice(name=n, klass=s, allow_par=self.allow_par) \
                   for s, n in signal_types.items()]
        return View(Item('signal{}@', editor=InstanceEditor(values=choices)),
                    height=400,
                    resizable=True,
                    title=self.title,
                    kind='livemodal',
                    close_result=False,
                    buttons=['OK', 'Cancel'])

SignalDialog = SignalSelector

#popup_view = View('handler.edit_signal{}', handler=SignalEditHandler)

if __name__ == '__main__':
    class Test(HasTraits):
        selector = Instance(SignalDialog, ())
        def traits_view(self, parent=None):
            return View('selector@')

    t = Test()
    t.configure_traits()



    #sd = SignalDialog(signal=st.AMTone(), allow_par=False)
    #sd.configure_traits(view='dialog_selector_view')
    #sd.configure_traits()
    #from cns.signal.type import Tone
    #Tone().configure_traits(view=popup_view)
