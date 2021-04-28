import os.path
import traceback

from AnyQt.QtWidgets import QMessageBox
from AnyQt.QtCore import QSettings

from orangewidget.utils import filedialogs


# noinspection PyBroadException
def save_plot(data, file_formats, start_dir="", filename=""):
    _LAST_DIR_KEY = "directories/last_graph_directory"
    _LAST_FILTER_KEY = "directories/last_graph_filter"
    settings = QSettings()
    start_dir = settings.value(_LAST_DIR_KEY, start_dir)
    if not start_dir or \
            (not os.path.exists(start_dir) and
             not os.path.exists(os.path.split(start_dir)[0])):
        start_dir = os.path.expanduser("~")
    last_filter = settings.value(_LAST_FILTER_KEY, "")
    if filename:
        start_dir = os.path.join(start_dir, filename)
    filename, writer, filter = \
        filedialogs.open_filename_dialog_save(start_dir, last_filter, file_formats)
    if not filename:
        return
    try:
        writer.write(filename, data)
    except OSError as e:
        mb = QMessageBox(
            None,
            windowTitle="Error",
            text='Error occurred while saving file "{}": {}'.format(filename, e),
            detailedText=traceback.format_exc(),
            icon=QMessageBox.Critical)
        mb.exec()
    else:
        settings.setValue(_LAST_DIR_KEY, os.path.split(filename)[0])
        settings.setValue(_LAST_FILTER_KEY, filter)


def main():  # pragma: no cover
    from AnyQt.QtWidgets import QApplication
    from orangewidget.widget import OWBaseWidget
    app = QApplication([])
    save_plot(None, OWBaseWidget.graph_writers)


if __name__ == "__main__":  # pragma: no cover
    main()
