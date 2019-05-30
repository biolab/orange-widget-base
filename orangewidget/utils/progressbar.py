import time
import warnings

from AnyQt.QtCore import pyqtProperty, pyqtSignal, pyqtSlot


class ProgressBarMixin:
    __progressBarValue = 0
    __progressState = 0
    startTime = -1  # used in progressbar
    captionTitle = ""

    def setCaption(self, caption):
        self.captionTitle = caption
        self.setWindowTitle(caption)

    @pyqtSlot()
    def progressBarInit(self):
        """
        Initialize the widget's progress (i.e show and set progress to 0%).
        """
        self.startTime = time.time()
        self.setWindowTitle(self.captionTitle + " (0% complete)")

        if self.__progressState != 1:
            self.__progressState = 1
            self.processingStateChanged.emit(1)

        self.progressBarSet(0)

    @pyqtSlot(float)
    def progressBarSet(self, value):
        """
        Set the current progress bar to `value`.

        Parameters
        ----------
        value : float
            Progress value.
        """
        old = self.__progressBarValue
        self.__progressBarValue = value

        if value > 0:
            if self.__progressState != 1:
                warnings.warn("progressBarSet() called without a "
                              "preceding progressBarInit()",
                              stacklevel=2)
                self.__progressState = 1
                self.processingStateChanged.emit(1)

            usedTime = max(1., time.time() - self.startTime)
            totalTime = 100.0 * usedTime / value
            remainingTime = max(0, int(totalTime - usedTime))
            hrs = remainingTime // 3600
            mins = (remainingTime % 3600) // 60
            secs = remainingTime % 60
            if hrs > 0:
                text = "{}:{:02}:{:02}".format(hrs, mins, secs)
            else:
                text = "{}:{}:{:02}".format(hrs, mins, secs)
            self.setWindowTitle("{} ({:d}%, ETA: {})"
                                .format(self.captionTitle, int(value), text))
        else:
            self.setWindowTitle(self.captionTitle + " (0% complete)")

        if old != value:
            self.progressBarValueChanged.emit(value)

    def progressBarValue(self):
        """
        Return the state (value) of the progress bar
        """
        return self.__progressBarValue

    progressBarValueChanged = pyqtSignal(float)
    progressBarValue = pyqtProperty(
        float, fset=progressBarSet, fget=progressBarValue,
        notify=progressBarValueChanged
    )
    processingStateChanged = pyqtSignal(int)
    processingState = pyqtProperty(
        int,
        fget=lambda self: self.__progressState,
        notify=processingStateChanged
    )

    @pyqtSlot(float)
    def progressBarAdvance(self, value):
        """
        Advance the progress bar by `value`.

        Parameters
        ----------
        value : float
            Progress value increment.
        """
        self.progressBarSet(self.__progressBarValue + value)

    @pyqtSlot()
    def progressBarFinished(self):
        """
        Stop the widget's progress (i.e hide the progress bar).

        Parameters
        ----------
        value : float
            Progress value increment.
        """
        self.setWindowTitle(self.captionTitle)
        if self.__progressState != 0:
            self.__progressState = 0
            self.processingStateChanged.emit(0)
