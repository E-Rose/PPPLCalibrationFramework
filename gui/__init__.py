
from PyQt5.QtWidgets import QSizePolicy
from pyforms import BaseWidget
from pyforms.Controls import ControlEmptyWidget, ControlLabel
from gui.axis import AxisTab
from gui.jog import JogTab
import motion

class ControllerWindow(BaseWidget):
    """
    A window to list the controllers
    """

    _update_functions = []

    def __init__(self):
        super().__init__("Calibration Controller")

        self._tabs = ControlEmptyWidget()

        self._tabs.value = TabWidget(self._update_events)

        self._viewer = ControlEmptyWidget()

        self.formset = [
            ('_tabs', '||', '_viewer')
        ]

    def add_update_function(self, event, function):
        """
        Add a function to be called when event 'event' happens
        Current events:
        'axis'
        'xaxis'
        'yaxis'
        """
        self._update_functions += (event, function)

    def _update_events(self, events):
        if isinstance(self._tabs.value, TabWidget):
            self._tabs.value.update_events(events)
        print(events)

    def before_close_event(self):
        motion.cleanup()

class TabWidget(BaseWidget):
    """
    A Widget for all the tabs
    """

    _update_function = None

    def __init__(self, update_function=None):
        super().__init__("TABS")

        self._update_function = update_function

        self._axis_tab = ControlEmptyWidget(
            label='Axis Tab'
        )

        self._axis_tab.value = AxisTab(self._update_function)

        self._points_tab = ControlEmptyWidget(
            label='Points Tab'
        )

        self._jog_tab = ControlEmptyWidget(
            label='Jog Tab'
        )

        self._jog_tab.value = JogTab()

        self.formset = [
            {
                "Axis": ['_axis_tab'],
                "Points": ['_points_tab'],
                "Jog": ['_jog_tab']
            }
        ]

    def update_events(self, events):
        """
        Updates events
        """
        if isinstance(self._jog_tab.value, JogTab):
            self._jog_tab.value.update_events(events)

    def init_form(self):
        super().init_form()
        size_policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        self.setSizePolicy(size_policy)
