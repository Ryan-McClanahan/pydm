import logging
logger = logging.getLogger(__name__)

from qtpy.QtWidgets import QFrame, QLabel, QSlider, QVBoxLayout, QHBoxLayout, QSizePolicy, QWidget
from qtpy.QtCore import Qt, Signal, Slot, Property
from .base import PyDMWritableWidget, TextFormatter
import numpy as np


class PyDMSlider(QFrame, TextFormatter, PyDMWritableWidget):
    """
    A QSlider with support for Channels and more from PyDM.

    Parameters
    ----------
    parent : QWidget
        The parent widget for the Label
    init_channel : str, optional
        The channel to be used by the widget.
    """
    actionTriggered = Signal(int)
    rangeChanged = Signal(float, float)
    sliderMoved = Signal(float)
    sliderPressed = Signal()
    sliderReleased = Signal()
    valueChanged = Signal(float)

    def __init__(self, parent=None, init_channel=None):
        QFrame.__init__(self, parent)
        PyDMWritableWidget.__init__(self, init_channel=init_channel)
        self.alarmSensitiveContent = True
        self.alarmSensitiveBorder = False
        # Internal values for properties
        self._ignore_mouse_wheel = True
        self._show_limit_labels = True
        self._show_value_label = True
        self._user_defined_limits = False
        self._needs_limit_info = True
        self._minimum = None
        self._maximum = None
        self._user_minimum = -10.0
        self._user_maximum = 10.0
        self._num_steps = 101
        self._orientation = Qt.Horizontal
        # Set up all the internal widgets that make up a PyDMSlider.
        # We'll add all these things to layouts when we call setup_widgets_for_orientation
        label_size_policy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.low_lim_label = QLabel(self)
        self.low_lim_label.setObjectName("lowLimLabel")
        self.low_lim_label.setSizePolicy(label_size_policy)
        self.low_lim_label.setAlignment(Qt.AlignLeft | Qt.AlignTrailing | Qt.AlignVCenter)
        self.value_label = QLabel(self)
        self.value_label.setObjectName("valueLabel")
        self.value_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.high_lim_label = QLabel(self)
        self.high_lim_label.setObjectName("highLimLabel")
        self.high_lim_label.setSizePolicy(label_size_policy)
        self.high_lim_label.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self._slider = QSlider(parent=self)
        self._slider.setOrientation(Qt.Horizontal)

        self._orig_wheel_event = self._slider.wheelEvent
        self._slider.wheelEvent = self.wheelEvent

        self._slider.sliderMoved.connect(self.internal_slider_moved)
        self._slider.sliderPressed.connect(self.internal_slider_pressed)
        self._slider.sliderReleased.connect(self.internal_slider_released)
        self._slider.valueChanged.connect(self.internal_slider_value_changed)
        # self.vertical_layout.addWidget(self._slider)
        # Other internal variables and final setup steps
        self._slider_position_to_value_map = None
        self._mute_internal_slider_changes = False
        self.setup_widgets_for_orientation(self._orientation)
        self.reset_slider_limits()

    def wheelEvent(self, e):
        #We specifically want to ignore mouse wheel events.
        if self._ignore_mouse_wheel:
            e.ignore()
        else:
            super(PyDMSlider, self).wheelEvent(e)
        return

    def init_for_designer(self):
        """
        Method called after the constructor to tweak configurations for
        when using the widget with the Qt Designer
        """
        self.value = 0.0

    @Property(Qt.Orientation)
    def orientation(self):
        """
        The slider orientation (Horizontal or Vertical)

        Returns
        -------
        int
            Qt.Horizontal or Qt.Vertical
        """
        return self._orientation

    @orientation.setter
    def orientation(self, new_orientation):
        """
        The slider orientation (Horizontal or Vertical)

        Parameters
        ----------
        new_orientation : int
            Qt.Horizontal or Qt.Vertical
        """
        self._orientation = new_orientation
        self.setup_widgets_for_orientation(new_orientation)

    def setup_widgets_for_orientation(self, new_orientation):
        """
        Reconstruct the widget given the orientation.

        Parameters
        ----------
        new_orientation : int
            Qt.Horizontal or Qt.Vertical
        """
        if new_orientation not in (Qt.Horizontal, Qt.Vertical):
            logger.error("Invalid orientation '{0}'. The existing layout will not change.".format(new_orientation))
            return

        layout = None
        if new_orientation == Qt.Horizontal:
            layout = QVBoxLayout()
            layout.setContentsMargins(4, 0, 4, 4)
            label_layout = QHBoxLayout()
            label_layout.addWidget(self.low_lim_label)
            label_layout.addStretch(0)
            label_layout.addWidget(self.value_label)
            label_layout.addStretch(0)
            label_layout.addWidget(self.high_lim_label)
            layout.addLayout(label_layout)
            self._slider.setOrientation(new_orientation)
            layout.addWidget(self._slider)
        elif new_orientation == Qt.Vertical:
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 4, 4, 4)
            label_layout = QVBoxLayout()
            label_layout.addWidget(self.high_lim_label)
            label_layout.addStretch(0)
            label_layout.addWidget(self.value_label)
            label_layout.addStretch(0)
            label_layout.addWidget(self.low_lim_label)
            layout.addLayout(label_layout)
            self._slider.setOrientation(new_orientation)
            layout.addWidget(self._slider)

        if self.layout() is not None:
            # Trick to remove the existing layout by re-parenting it in an empty widget.
            QWidget().setLayout(self.layout())
        self.setLayout(layout)

    def update_labels(self):
        """
        Update the limits and value labels with the correct values.
        """
        def set_label(value, label_widget):
            if value is None:
                label_widget.setText("")
            else:
                label_widget.setText(self.format_string.format(value))

        set_label(self.minimum, self.low_lim_label)
        set_label(self.maximum, self.high_lim_label)
        set_label(self.value, self.value_label)

    def reset_slider_limits(self):
        """
        Reset the limits and adjust the labels properly for the slider.
        """
        logger.debug("Running reset_slider_limits.")
        if self.minimum is None or self.maximum is None:
            self._needs_limit_info = True
            logger.debug("Need both limits before reset_slider_limits can work.")
            self.set_enable_state()
            return
        logger.debug("Has both limits, proceeding.")
        self._needs_limit_info = False
        self._slider.setMinimum(0)
        self._slider.setMaximum(self._num_steps - 1)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(10)
        self._slider_position_to_value_map = np.linspace(self.minimum, self.maximum, num=self._num_steps)
        self.update_labels()
        self.set_slider_to_closest_value(self.value)
        self.rangeChanged.emit(self.minimum, self.maximum)
        self.set_enable_state()

    def find_closest_slider_position_to_value(self, val):
        """
        Find and returns the index for the closest position on the slider
        for a given value.

        Parameters
        ----------
        val : float

        Returns
        -------
        int
        """
        diff = abs(self._slider_position_to_value_map - float(val))
        logger.debug("The closest value to %f is: %f", val, self._slider_position_to_value_map[np.argmin(diff)])
        return np.argmin(diff)

    def set_slider_to_closest_value(self, val):
        """
        Set the value for the slider according to a given value.

        Parameters
        ----------
        val : float
        """
        if val is None or self._needs_limit_info:
            logger.debug("Not setting slider to closest value because we need limits.")
            return
        # When we set the slider to the closest value, it may end up at a slightly
        # different position than val (if val is not in self._slider_position_to_value_map)
        # We don't want that slight difference to get broacast out and put the channel
        # somewhere new.    For example, if the slider can only be at 0.4 or 0.5, but a
        # new value comes in of 0.45, its more important to keep the 0.45 than to change
        # it to where the slider gets set.  Therefore, we mute the internal slider changes
        # so that its valueChanged signal doesn't cause us to emit a signal to PyDM to change
        # the value of the channel.
        logger.debug("Setting slider to closest value.")
        self._mute_internal_slider_changes = True
        self._slider.setValue(self.find_closest_slider_position_to_value(val))
        self._mute_internal_slider_changes = False

    def connection_changed(self, connected):
        """
        Callback invoked when the connection state of the Channel is changed.
        This callback acts on the connection state to enable/disable the widget
        and also trigger the change on alarm severity to ALARM_DISCONNECTED.

        Parameters
        ----------
        connected : int
            When this value is 0 the channel is disconnected, 1 otherwise.
        """
        super(PyDMSlider, self).connection_changed(connected)
        self.set_enable_state()

    def write_access_changed(self, new_write_access):
        """
        Callback invoked when the Channel has new write access value.
        This callback calls check_enable_state so it can act on the widget
        enabling or disabling it accordingly

        Parameters
        ----------
        new_write_access : bool
            True if write operations to the channel are allowed.
        """
        super(PyDMSlider, self).write_access_changed(new_write_access)
        self.set_enable_state()

    def value_changed(self, new_val):
        """
        Callback invoked when the Channel value is changed.

        Parameters
        ----------
        new_val : int or float
            The new value from the channel.
        """
        PyDMWritableWidget.value_changed(self, new_val)
        if hasattr(self, "value_label"):
            logger.debug("Setting text for value label.")
            self.value_label.setText(self.format_string.format(self.value))
        if not self._slider.isSliderDown():
            self.set_slider_to_closest_value(self.value)
        self.update_format_string()

    def ctrl_limit_changed(self, which, new_limit):
        """
        Callback invoked when the Channel receives new control limit
        values.

        Parameters
        ----------
        which : str
            Which control limit was changed. "UPPER" or "LOWER"
        new_limit : float
            New value for the control limit
        """
        logger.debug("%s limit changed to %f", which, new_limit)
        PyDMWritableWidget.ctrl_limit_changed(self, which, new_limit)
        if not self.userDefinedLimits:
            self.reset_slider_limits()

    def update_format_string(self):
        """
        Reconstruct the format string to be used when representing the
        output value.

        Returns
        -------
        format_string : str
            The format string to be used including or not the precision
            and unit
        """
        fs = super(PyDMSlider, self).update_format_string()
        self.update_labels()
        return fs

    def set_enable_state(self):
        """
        Determines wether or not the widget must be enabled or not depending
        on the write access, connection state and presence of limits information
        """
        # Even though by documentation disabling parent QFrame (self), should disable internal
        # slider, in practice it still remains interactive (PyQt 5.12.1). Disabling explicitly, solves
        # the problem.
        should_enable = self._write_access and self._connected and not self._needs_limit_info
        self.setEnabled(should_enable)
        self._slider.setEnabled(should_enable)

    @Slot(int)
    def internal_slider_action_triggered(self, action):
        self.actionTriggered.emit(action)

    @Slot(int)
    def internal_slider_moved(self, val):
        """
        Method invoked when the slider is moved.

        Parameters
        ----------
        val : float
        """
        self.sliderMoved.emit(self.value)

    @Slot()
    def internal_slider_pressed(self):
        """
        Method invoked when the slider is pressed
        """
        self.sliderPressed.emit()

    @Slot()
    def internal_slider_released(self):
        """
        Method invoked when the slider is released
        """
        self.sliderReleased.emit()

    @Slot(int)
    def internal_slider_value_changed(self, val):
        """
        Method invoked when a new value is selected on the slider.
        This will cause the new value to be emitted to the signal
        unless `mute_internal_slider_changes` is True.

        Parameters
        ----------
        val : int
        """        
        # Avoid potential crash if limits are undefined
        if self._slider_position_to_value_map is None:
            return
        if not self._mute_internal_slider_changes:
            self.value = self._slider_position_to_value_map[val]
            self.send_value_signal[float].emit(self.value)

    @Property(bool)
    def tracking(self):
        """
        If tracking is enabled (the default), the slider emits new values
        while the slider is being dragged.  If tracking is disabled, it will
        only emit new values when the user releases the slider.  Tracking can
        cause PyDM to rapidly send new values to the channel.  If you are using
        the slider to control physical hardware, consider whether the device
        you want to control can handle large amounts of changes in a short
        timespan.
        """
        return self._slider.hasTracking()
        
    @tracking.setter
    def tracking(self, checked):
        self._slider.setTracking(checked)
    
    def hasTracking(self):
        """
        An alternative function to get the tracking property, to match what
        Qt provides for QSlider.
        """
        return self.tracking
    
    def setTracking(self, checked):
        """
        An alternative function to set the tracking property, to match what
        Qt provides for QSlider.
        """
        self.tracking = checked

    @Property(bool)
    def ignoreMouseWheel(self):
        """
        If true, the mouse wheel will not change the value of the slider.
        This is useful if you want to put sliders inside a scroll view, and
        don't want to accidentally change the slider as you are scrolling.
        """
        return self._ignore_mouse_wheel
    
    @ignoreMouseWheel.setter
    def ignoreMouseWheel(self, checked):
        self._ignore_mouse_wheel = checked
        if checked:
            self._slider.wheelEvent = self.wheelEvent
        else:
            self._slider.wheelEvent = self._orig_wheel_event

    @Property(bool)
    def showLimitLabels(self):
        """
        Whether or not the high and low limits should be displayed on the slider.

        Returns
        -------
        bool
        """
        return self._show_limit_labels

    @showLimitLabels.setter
    def showLimitLabels(self, checked):
        """
        Whether or not the high and low limits should be displayed on the slider.

        Parameters
        ----------
        checked : bool
        """
        self._show_limit_labels = checked
        if checked:
            self.low_lim_label.show()
            self.high_lim_label.show()
        else:
            self.low_lim_label.hide()
            self.high_lim_label.hide()

    @Property(bool)
    def showValueLabel(self):
        """
        Whether or not the current value should be displayed on the slider.

        Returns
        -------
        bool
        """
        return self._show_value_label

    @showValueLabel.setter
    def showValueLabel(self, checked):
        """
        Whether or not the current value should be displayed on the slider.

        Parameters
        ----------
        checked : bool
        """
        self._show_value_label = checked
        if checked:
            self.value_label.show()
        else:
            self.value_label.hide()

    @Property(QSlider.TickPosition)
    def tickPosition(self):
        """
        Where to draw tick marks for the slider.

        Returns
        -------
        QSlider.TickPosition
        """
        return self._slider.tickPosition()

    @tickPosition.setter
    def tickPosition(self, position):
        """
        Where to draw tick marks for the slider.

        Parameter
        ---------
        position : QSlider.TickPosition
        """
        self._slider.setTickPosition(position)

    @Property(bool)
    def userDefinedLimits(self):
        """
        Wether or not to use limits defined by the user and not from the
        channel

        Returns
        -------
        bool
        """
        return self._user_defined_limits

    @userDefinedLimits.setter
    def userDefinedLimits(self, user_defined_limits):
        """
        Wether or not to use limits defined by the user and not from the
        channel

        Parameters
        ----------
        user_defined_limits : bool
        """
        self._user_defined_limits = user_defined_limits
        self.reset_slider_limits()

    @Property(float)
    def userMinimum(self):
        """
        Lower user defined limit value

        Returns
        -------
        float
        """
        return self._user_minimum

    @userMinimum.setter
    def userMinimum(self, new_min):
        """
        Lower user defined limit value

        Parameters
        ----------
        new_min : float
        """
        self._user_minimum = float(new_min) if new_min is not None else None
        if self.userDefinedLimits:
            self.reset_slider_limits()

    @Property(float)
    def userMaximum(self):
        """
        Upper user defined limit value

        Returns
        -------
        float
        """
        return self._user_maximum

    @userMaximum.setter
    def userMaximum(self, new_max):
        """
        Upper user defined limit value

        Parameters
        ----------
        new_max : float
        """
        self._user_maximum = float(new_max) if new_max is not None else None
        if self.userDefinedLimits:
            self.reset_slider_limits()

    @property
    def minimum(self):
        """
        The current value being used for the lower limit

        Returns
        -------
        float
        """
        if self.userDefinedLimits:
            return self._user_minimum
        return self._lower_ctrl_limit

    @property
    def maximum(self):
        """
        The current value being used for the upper limit

        Returns
        -------
        float
        """
        if self.userDefinedLimits:
            return self._user_maximum
        return self._upper_ctrl_limit

    @Property(int)
    def num_steps(self):
        """
        The number of steps on the slider

        Returns
        -------
        int
        """
        return self._num_steps

    @num_steps.setter
    def num_steps(self, new_steps):
        """
        The number of steps on the slider

        Parameters
        ----------
        new_steps : int
        """
        self._num_steps = int(new_steps)
        self.reset_slider_limits()
