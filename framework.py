"""
The framework for stepping and scanning axis and measuring the sensor values
"""

import time
import csv
from enum import Enum, auto
from abc import ABC, abstractmethod
from PyQt5.QtCore import QTimer
from pyforms import BaseWidget
from pyforms.Controls import ControlCombo, ControlLabel

import cv2


class AxisType(Enum):
    """
    A type of axis as used for movement
    """
    X_Axis = "X Axis"
    Y_Axis = "Y Axis"
    Auxiliary_Axis = "Aux Axis"


class ControlAxis(ABC):

    """
    Controls a single axis used for calibration

    An Axis is anything that gets changed while scanning.
    For example, The X/Y Axis of an area, the power of the laser, etc

    Each Axis has a list of points it goes to
    There should be the same number of points in every axis

    Must be subclassed for each actual axis being used
    Any subclasses that are imported into main.py will show up in the drop downs

    The _write_value(self, value) method must be overrided in the subclass to actually move the axis
    Everything else can be overrided if needed
    """

    points = None

    _value = 0
    _name = ""
    _type = None

    _max = 0
    _min = 0

    def __init__(self, name):
        self._name = name
        self.points = []

    # This method must be overrided in subclasses
    @abstractmethod
    def _write_value(self, value):
        """
        Write the value to the physical device
        Returns whether the write was successful
        """
        pass

    # These can be overrided if needed
    def update(self):
        """
        Gets called very quickly repeatedly while scanning
        """
        pass

    def is_done(self):
        """
        Returns whether the axis is done moving. Also gets called quickely while scanning
        """
        return True

    def get_custom_config(self):
        """
        Gets a custom pywidgets BaseWidget to display in the axis configuation area of the gui when this axis is selected
        """
        return None

    def goto_home(self):
        """
        Homes the axis to go to the endstop
        """
        self.goto_value(0)

    # These methods should not be overrided unless absolutly required
    def set_min(self, min_value):
        """
        Sets the min value
        """
        self._min = min_value

    def set_max(self, max_value):
        """
        Sets the max value
        """
        self._max = max_value

    def get_min(self):
        """
        Gets the min value
        """
        return self._min

    def get_max(self):
        """
        Gets the max value
        """
        return self._max

    def get_value(self):
        """
        Gets the target value
        """
        return self._value

    def get_current_value(self):
        """
        Gets the current value (may not be the target)
        """
        return self._value

    def goto_value(self, value):
        """
        Gots to a specified value, clipping to the min and max
        Returns if successful
        """
        if value < self._min:
            value = self._min

        if value > self._max:
            value = self._max

        self._value = value
        return self._write_value(self._value)

    def get_name(self):
        """
        Gets the name of this axis
        """
        return self._name

    def set_name(self, name):
        """
        Sets the name of this axis
        """
        self._name = name


class OutputDevice(ABC):
    """
    The thing that gets enabled when measuring

    This class must be subclassed for each output device
    """

    @abstractmethod
    def set_enabled(self, enable=True):
        """
        Set the output to enabled or disabled
        """
        pass

    def get_enabled(self):
        """
        Get enabled
        """
        return False

    def get_custom_config(self):
        """
        Get the GUI config for this output device
        """
        return None


class Sensor(ABC):

    """
    The thing that is being calibrated
    
    This must be subclasses for each sensor
    """

    def get_custom_config(self):
        """
        Get the GUI config for this output device
        """
        return None

    def update(self):
        """
        Gets called repeatedly while scanning
        """
        pass

    def begin_measuring(self):
        """
        Begin measuring during update()
        """
        pass

    def is_done(self):
        """
        Returns whether the sensor is done measuring
        """
        return True

    def get_data(self):
        """
        Returns the measured data as a list
        """
        return []


class AxisControllerState(Enum):
    """
    The state for the AxisController
    """
    BEGIN_STEP = 'beginstep'
    WAIT_STEP = 'waitstep'
    BEGIN_ENABLE = 'beginsensor'
    WAIT_ENABLE = 'waitsensor'
    BEGIN_PRE_DELAY = 'beginpredelay'
    WAIT_PRE_DELAY = 'waitpredelay'
    BEGIN_POST_DELAY = 'beginpostdelay'
    WAIT_POST_DELAY = 'waitpostdelay'
    DONE = 'done'


class AxisController:
    """
    Controls many ControlAxis to scan a grid
    """

    _axis = []
    _sensor = None
    _output = None

    _state = AxisControllerState.BEGIN_STEP

    _pre_delay = 0
    _post_delay = 0
    _start_delay = 0

    _data = []

    _measuring = False

    _outfile = None

    _step = 0
    _timer = QTimer()

    def __init__(self, control_axis, sensor, output, pre_delay, post_delay, outfile=None):
        """
        Creates a new Axis Controller with a list of ControlAxis to control
        :param control_axis: a list of ControlAxis in the order that they should be controlled
        """

        self._axis = control_axis
        self._sensor = sensor
        self._output = output
        self._pre_delay = pre_delay
        self._post_delay = post_delay
        self._outfile = outfile

    def begin(self):
        """
        Starts scanning
        """
        self._output.set_enabled(False)
        self._step = 0
        self._state = AxisControllerState.BEGIN_STEP
        self._timer.timeout.connect(self._scan)
        self._timer.start()

    def _scan(self):
        """
        Scans through all of the axis given in the constructor in order
        :return: Nothing
        """

        if (self._state == AxisControllerState.BEGIN_PRE_DELAY
                or self._state == AxisControllerState.WAIT_PRE_DELAY
                or self._state == AxisControllerState.BEGIN_ENABLE
                or self._state == AxisControllerState.WAIT_ENABLE
                or self._state == AxisControllerState.BEGIN_POST_DELAY
                or self._state == AxisControllerState.WAIT_POST_DELAY):
            datarow = [time.time()]
            for axis in self._axis:
                datarow.append(axis.get_current_value())

            datarow += self._sensor.update()

            self._data.append(datarow)

        # Begin Step
        if self._state == AxisControllerState.BEGIN_STEP:
            print("Moving to step:", self._step)
            done = True
            for axis in self._axis:
                if len(axis.points) > self._step:
                    axis.goto_value(axis.points[self._step])
                    done = False

            if done:
                self._state = AxisControllerState.DONE
            else:
                self._state = AxisControllerState.WAIT_STEP

        # Wait Step
        elif self._state == AxisControllerState.WAIT_STEP:
            print('.', end='')
            done = True
            for axis in self._axis:
                if not axis.is_done():
                    done = False

            if done:
                print()
                self._state = AxisControllerState.BEGIN_PRE_DELAY

        # Begin Pre Delay
        elif self._state == AxisControllerState.BEGIN_PRE_DELAY:
            print("Pre Delay")
            self._start_delay = time.time()
            self._state = AxisControllerState.WAIT_PRE_DELAY

        # Wait Pre Delay
        elif self._state == AxisControllerState.WAIT_PRE_DELAY:
            print('.', end='')
            if time.time() - self._start_delay > self._pre_delay:
                print()
                self._state = AxisControllerState.BEGIN_ENABLE

        # Begin Measuring
        elif self._state == AxisControllerState.BEGIN_ENABLE:
            print("Taking measurement")
            self._output.set_enabled(True)
            self._sensor.begin_measuring()
            self._state = AxisControllerState.WAIT_ENABLE

        # Wait Measuring
        elif self._state == AxisControllerState.WAIT_ENABLE:
            print('.', end='')

            if self._sensor.is_done():
                print()

                self._state = AxisControllerState.BEGIN_POST_DELAY
                self._output.set_enabled(False)

        # Begin Post Delay
        elif self._state == AxisControllerState.BEGIN_POST_DELAY:
            print("Post Delay")
            self._start_delay = time.time()
            self._state = AxisControllerState.WAIT_POST_DELAY

        # Wait Post Delay
        elif self._state == AxisControllerState.WAIT_POST_DELAY:
            print('.', end='')
            if time.time() - self._start_delay > self._post_delay:
                print()
                self._step += 1
                self._state = AxisControllerState.BEGIN_STEP

        elif self._state == AxisControllerState.DONE:
            print("Done.")

            if self._outfile is not None and self._outfile is not '':
                with open(self._outfile, 'w', newline='') as csvfile:
                    csvwriter = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
                    csvwriter.writerows(self._data)

            self._timer.stop()
