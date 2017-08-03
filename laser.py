"""
ControlAxis for use with a laser controlled by a power supply and a signal generator
"""
import time
import visa
from visa import VisaIOError
from pyforms import BaseWidget
from pyforms.Controls import ControlNumber, ControlCombo
from framework import ControlAxis, LightSource

RESOURCE_MANAGER = visa.ResourceManager()

LASER = None


def get_devices():
    """
    Gets pyvisa resources to be used for a laser
    """
    resources = RESOURCE_MANAGER.list_resources()

    devices = {"Power Supply": [], "Signal Generator": []}

    for resource in resources:

        try:
            open_resource = RESOURCE_MANAGER.open_resource(resource)
            open_resource.timeout = 100
            name = open_resource.query("*IDN?").strip()
            open_resource.close()
        except VisaIOError as err:
            print("Could not talk to", resource)
            print(err)
            continue

        # Only add if it is a known power supply or signal generator
        if 'AFG-3021' in name:
            devices["Signal Generator"].append((name, resource))
        elif 'GPD-4303S' in name:
            devices["Power Supply"].append((name, resource))

    return devices


DEVICES = get_devices()

WIDGET = None


def laser_custom_config():
    """
    Get the GUI config to configure the laser
    The GUI is the same for each laser axis and for the laser lightsource
    """
    global WIDGET

    if WIDGET is None:
        widget = BaseWidget("Laser Config")

        widget.power_supply = ControlCombo(
            label="Power Supply"
        )

        widget.power_supply += ('None', None)

        for power in DEVICES['Power Supply']:
            widget.power_supply += power

        widget.power_supply.current_index_changed_event = update_laser

        widget.power_channel = ControlNumber(
            label="Power Supply Channel",
            default=1,
            minimum=1,
            maximum=4
        )

        widget.signal_generator = ControlCombo(
            label="Signal Generator"
        )

        widget.signal_generator += ('None', None)

        for signal in DEVICES['Signal Generator']:
            widget.signal_generator += signal

        widget.signal_generator.current_index_changed_event = update_laser

        widget.formset = [
            "h5:Laser Using",
            'power_supply',
            'power_channel',
            'signal_generator',
            "(All laser axis use the same laser)"
        ]

        WIDGET = widget

    return WIDGET


def update_laser(_):
    """
    Update the current laser with the power supply and signal generator
    from the GUI
    """
    global LASER
    global WIDGET
    power = WIDGET.power_supply.value
    signal = WIDGET.signal_generator.value
    channel = WIDGET.power_channel.value
    print(power)
    print(signal)
    # Only update if both are selected
    if power is not None and power != 'None' and signal is not None and signal != 'None':
        print("Making Laser")
        power_resource = RESOURCE_MANAGER.open_resource(power)
        signal_resource = RESOURCE_MANAGER.open_resource(signal)
        LASER = Laser(power_resource, channel, signal_resource)


def cleanup():
    global WIDGET
    if isinstance(WIDGET, BaseWidget):
        for item in WIDGET.power_supply.items:
            if isinstance(item, tuple):
                resource = item[1]
                if isinstance(resource, visa.Resource):
                    resource.close()

    RESOURCE_MANAGER.close()


class Laser:
    """
    Controls the laser and holds the LaserPowerAxis and Laser Frequency Axis
    """

    power_resource = None
    signal_resource = None

    power_channel = 0

    enabled_voltage = 8
    disabled_voltage = 0
    max_current = 0.5

    low_signal = -0.2
    high_signal = 1.0

    power = 0.0
    frequency = 0.0
    enabled = False

    delay = 0.01
    last_write = 0

    # Whether to use the external trigger to ensure outpout is synced
    # Requires wiring the power supply output to the external trigger port of the AFG
    _ext_trigger = True

    def __init__(self, power_resource, power_channel, signal_resource):
        """
        Create a Laser
        :param power_resource: The pyvisa resource for the laser power supply (Must be a GPD-4303S for now)
        :param power_channel: The channel on the power supply to use
        :param signal_resource: The pyvisa resource for the laser signal generator (Must be an AFG-3021 for now)
        """

        print("Signal Generator:", signal_resource.query('*IDN?'))
        print("Power Supply:", power_resource.query('*IDN?'))

        self.power_resource = power_resource
        self.power_channel = power_channel
        self.signal_resource = signal_resource

        # Turn on the outputs
        self.power_resource.write('OUT1')

        # Set the voltage to 8 volts
        self.power_resource.write('VSET{0}:8'.format(self.power_channel))

        # Set the current to 0.5 amps
        self.power_resource.write('ISET{0}:0.5'.format(self.power_channel))

        # Turn on the signal
        self.signal_resource.write('OUTPUT ON')

        self.set_power(1)

    def __del__(self):
        self.enabled = False
        self.offset = self.low_signal
        self.update_laser()
        self.power_resource.close()
        self.signal_resource.close()

    def update_laser(self):
        """
        Updates the laser to current power, frequency, and enabled
        """

        if time.time() - self.last_write > self.delay:
            if self.frequency > 0:
                amplitude = self.power * \
                    (self.high_signal - self.low_signal) * 2
                offset = self.low_signal

                if self._ext_trigger:
                    self.signal_resource.write("SOURCE1:BURST:STATE ON")
                    self.signal_resource.write(
                        "SOURCE1:APPLY:SQUARE {0}HZ,{1},{2}".format(self.frequency, amplitude, offset))
                    self.signal_resource.write("SOURCE1:BURST:MODE GATE")
                    self.signal_resource.write("SOURCE1:BURST:PHASE 0")
                    self.signal_resource.write("SOURCE1:BURST:TRIGGER EXT")
                else:
                    self.signal_resource.write(
                        "SOURCE1:APPLY:SQUARE {0}HZ,{1},{2}".format(self.frequency, amplitude, offset))

            else:
                offset = self.power * \
                    (self.high_signal - self.low_signal) + self.low_signal
                self.signal_resource.write("SOURCE1:BURST:STATE OFF")
                self.signal_resource.write(
                    "SOURCE1:APPLY:DC DEFAULT,DEFAULT,{0}".format(offset))

            if self.enabled:
                self.power_resource.write("OUT1")
            else:
                self.power_resource.write("OUT0")

            self.last_write = time.time()

    def set_enabled(self, enable=True):
        """
        Enables or disables the power supply
        :param enable: Enables if True, disables if false
        :return: nothing
        """
        self.enabled = enable
        time.sleep(0.1)
        self.update_laser()

    def get_enabled(self):
        """
        Gets if the laser is enabled
        """
        return self.enabled

    def set_frequency(self, frequency):
        """
        Sets the frequency to pulse the laser at
        :param frequency: The frequency in hertz
        :return: nothing
        """
        self.frequency = frequency
        self.update_laser()

    def get_frequency(self):
        """
        Get the frequency
        """
        return self.frequency

    def set_power(self, power):
        """
        Sets the power to the laser by adjusting the amplitude and DC offset of the signal
        :param power: The power to apply between 0.0 and 1.0
        :return: nothing
        """
        self.power = power
        self.update_laser()

    def get_power(self):
        """
        Get the power
        """
        return self.power

    def get_signal_generator(self):
        """
        Returns the signal generator resource in use
        """
        return self.signal_resource

    def get_power_supply(self):
        """
        Returns the power supply resource in use
        """
        return self.power_resource


class LaserLightSource(LightSource):
    """
    Can enable/disable the laser
    """

    def get_custom_config(self):
        return laser_custom_config()

    def get_enabled(self):
        global LASER
        if isinstance(LASER, Laser):
            return LASER.get_enabled()
        else:
            return False

    def set_enabled(self, enable=True):
        global LASER
        print("Setting Laser Enabled", enable)
        if isinstance(LASER, Laser):
            LASER.set_enabled(enable)


class LaserPowerAxis(ControlAxis):
    """
    A ControlAxis to control the power to the laser
    """

    def get_custom_config(self):
        return laser_custom_config()

    def get_current_value(self):
        global LASER
        if isinstance(LASER, Laser):
            return LASER.get_power()
        else:
            return 0.0

    def _write_value(self, value):
        global LASER
        if isinstance(LASER, Laser):
            LASER.set_power(value)
            print("Setting laser power to: {}".format(value))

    def get_units(self):
        return "0-1"


class LaserFequencyAxis(ControlAxis):
    """
    A ControlAxis to control the frequency to the laser
    """

    def get_custom_config(self):
        return laser_custom_config()

    def get_current_value(self):
        global LASER
        if isinstance(LASER, Laser):
            return LASER.get_frequency()
        else:
            return 0.0

    def _write_value(self, value):
        global LASER
        if isinstance(LASER, Laser):
            LASER.set_frequency(value)
            print("Setting laser frequency to: {}".format(value))

    def get_units(self):
        return "Hz"
