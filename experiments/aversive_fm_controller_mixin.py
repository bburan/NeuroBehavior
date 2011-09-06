from tdt import DSPCircuit
from cns import get_config
from os.path import join

class AversiveFMControllerMixin(object):

    def _setup_circuit(self, info):
        # AversiveFMController needs to change the initialization sequence a
        # little (i.e. it needs to use different microcode and the microcode
        # does not contain int and trial buffers).
        circuit = join(get_config('RCX_ROOT'), 'aversive-behavior-FM')
        self.iface_behavior = self.process.load_circuit(circuit, 'RZ6')
        self.buffer_TTL = self.iface_behavior.get_buffer('TTL', 'r',
                src_type='int8', dest_type='int8', block_size=24)
        self.buffer_contact = self.iface_behavior.get_buffer('contact', 'r',
                src_type='int8', dest_type='float32', block_size=24)
        self.setup_shock(info)

    # We are overriding the three signal update methods (remind, warn, safe) to
    # work with the specific circuit we constructed
    def update_remind(self):
        pass

    def update_warn(self):
        pass

    def update_safe(self):
        pass

    def set_depth(self, value):
        self.iface_behavior.set_tag('depth', value)

    def set_cf(self, value):
        self.iface_behavior.set_tag('cf', value)

    def set_fm(self, value):
        self.iface_behavior.set_tag('fm', value)