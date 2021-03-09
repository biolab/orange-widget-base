import copy
import itertools
import warnings
from functools import singledispatch
import inspect
from typing import NamedTuple, Union, Optional

from AnyQt.QtCore import Qt

from orangecanvas.registry.description import (
    InputSignal, OutputSignal, Single, Multiple, Default, NonDefault,
    Explicit, Dynamic
)


# increasing counter for ensuring the order of Input/Output definitions
# is preserved when going through the unordered class namespace of
# WidgetSignalsMixin.Inputs/Outputs.
_counter = itertools.count()


PartialSummary = NamedTuple(
    "PartialSummary", (("summary", Union[None, str, int]),
                       ("details", Optional[str])))


def base_summarize(_) -> PartialSummary:
    return PartialSummary(None, None)


summarize = singledispatch(base_summarize)

SUMMARY_STYLE = """
<style>
    ul {
        margin-left: 10px;
        margin-top: 2px;
        -qt-list-indent:0
    }

    li {
        margin-top: 3px;
    }

    th {
        text-align: right;
    }
</style>
"""


def can_summarize(type_, name):
    if not isinstance(type_, tuple):
        type_ = (type_, )
    instr = f"To silence this warning, set auto_sumarize of '{name}' to False."
    for a_type in type_:
        try:
            summarizer = summarize.dispatch(a_type)
        except TypeError:
            warnings.warn(f"{a_type.__name__} cannot be summarized. {instr}",
                          UserWarning)
            return False
        if summarizer is base_summarize:
            warnings.warn(
                f"register 'summarize' function for type {a_type.__name__}. "
                + instr, UserWarning)
            return False
    return True


class _Signal:
    @staticmethod
    def get_flags(multiple, default, explicit, dynamic):
        """Compute flags from arguments"""

        return (Multiple if multiple else Single) | \
                (Default if default else NonDefault) | \
                (explicit and Explicit) | \
                (dynamic and Dynamic)

    def bound_signal(self, widget):
        """
        Return a copy of the signal bound to a widget.

        Called from `WidgetSignalsMixin.__init__`
        """
        new_signal = copy.copy(self)
        new_signal.widget = widget
        return new_signal


def getsignals(signals_cls):
    # This function is preferred over getmembers because it returns the signals
    # in order of appearance
    return [(k, v)
            for cls in reversed(inspect.getmro(signals_cls))
            for k, v in cls.__dict__.items()
            if isinstance(v, _Signal)]


class Input(InputSignal, _Signal):
    """
    Description of an input signal.

    The class is used to declare input signals for a widget as follows
    (the example is taken from the widget Test & Score)::

        class Inputs:
            train_data = Input("Data", Table, default=True)
            test_data = Input("Test Data", Table)
            learner = Input("Learner", Learner, multiple=True)
            preprocessor = Input("Preprocessor", Preprocess)

    Every input signal must be used to decorate exactly one method that
    serves as the input handler, for instance::

        @Inputs.train_data
        def set_train_data(self, data):
            ...

    Parameters
    ----------
    name (str):
        signal name
    type (type):
        signal type
    id (str):
        a unique id of the signal
    doc (str, optional):
        signal documentation
    replaces (list of str):
        a list with names of signals replaced by this signal
    multiple (bool, optional):
        if set, multiple signals can be connected to this output
        (default: `False`)
    default (bool, optional):
        when the widget accepts multiple signals of the same type, one of them
        can set this flag to act as the default (default: `False`)
    explicit (bool, optional):
        if set, this signal is only used when it is the only option or when
        explicitly connected in the dialog (default: `False`)
    auto_summary (bool, optional):
        if changed to `False` (default is `True`) the signal is excluded from
        auto summary
    """
    def __init__(self, name, type, id=None, doc=None, replaces=None, *,
                 multiple=False, default=False, explicit=False,
                 auto_summary=True):
        flags = self.get_flags(multiple, default, explicit, False)
        super().__init__(name, type, "", flags, id, doc, replaces or [])
        self.auto_summary = auto_summary and can_summarize(type, name)
        self._seq_id = next(_counter)

    def __call__(self, method):
        """
        Decorator that stores decorated method's name in the signal's
        `handler` attribute. The method is returned unchanged.
        """
        if self.flags & Multiple:
            def summarize_wrapper(widget, value, id=None):
                widget.set_partial_input_summary(
                    self.name, summarize(value), id=id)
                method(widget, value, id)
        else:
            def summarize_wrapper(widget, value):
                widget.set_partial_input_summary(
                    self.name, summarize(value))
                method(widget, value)

        # Re-binding with the same name can happen in derived classes
        # We do not allow re-binding to a different name; for the same class
        # it wouldn't work, in derived class it could mislead into thinking
        # that the signal is passed to two different methods
        if self.handler and self.handler != method.__name__:
            raise ValueError("Input {} is already bound to method {}".
                             format(self.name, self.handler))
        self.handler = method.__name__
        return summarize_wrapper if self.auto_summary else method


class Output(OutputSignal, _Signal):
    """
    Description of an output signal.

    The class is used to declare output signals for a widget as follows
    (the example is taken from the widget Test & Score)::

        class Outputs:
            predictions = Output("Predictions", Table)
            evaluations_results = Output("Evaluation Results", Results)

    The signal is then transmitted by, for instance::

        self.Outputs.predictions.send(predictions)

    Parameters
    ----------
    name (str):
        signal name
    type (type):
        signal type
    id (str):
        a unique id of the signal
    doc (str, optional):
        signal documentation
    replaces (list of str):
        a list with names of signals replaced by this signal
    default (bool, optional):
        when the widget accepts multiple signals of the same type, one of them
        can set this flag to act as the default (default: `False`)
    explicit (bool, optional):
        if set, this signal is only used when it is the only option or when
        explicitly connected in the dialog (default: `False`)
    dynamic (bool, optional):
        Specifies that the instances on the output will in general be subtypes
        of the declared type and that the output can be connected to any input
        signal which can accept a subtype of the declared output type
        (default: `True`)
    auto_summary (bool, optional):
        if changed to `False` (default is `True`) the signal is excluded from
        auto summary
    """
    def __init__(self, name, type, id=None, doc=None, replaces=None, *,
                 default=False, explicit=False, dynamic=True,
                 auto_summary=True):
        flags = self.get_flags(False, default, explicit, dynamic)
        super().__init__(name, type, flags, id, doc, replaces or [])
        self.auto_summary = auto_summary and can_summarize(type, name)
        self.widget = None
        self._seq_id = next(_counter)

    def send(self, value, id=None):
        """Emit the signal through signal manager."""
        assert self.widget is not None
        signal_manager = self.widget.signalManager
        if signal_manager is not None:
            signal_manager.send(self.widget, self.name, value, id)
        if self.auto_summary:
            self.widget.set_partial_output_summary(
                self.name, summarize(value), id=id)

    def invalidate(self):
        """Invalidate the current output value on the signal"""
        assert self.widget is not None
        signal_manager = self.widget.signalManager
        if signal_manager is not None:
            signal_manager.invalidate(self.widget, self.name)


class WidgetSignalsMixin:
    """Mixin for managing widget's input and output signals"""
    class Inputs:
        pass

    class Outputs:
        pass

    def __init__(self):
        self.input_summaries = {}
        self.output_summaries = {}
        self._bind_signals()

    def _bind_signals(self):
        for direction, summaries in (("Inputs", self.input_summaries),
                                     ("Outputs", self.output_summaries)):
            bound_cls = getattr(self, direction)
            bound_signals = bound_cls()
            for name, signal in getsignals(bound_cls):
                setattr(bound_signals, name, signal.bound_signal(self))
                if signal.auto_summary:
                    summaries[signal.name] = {}
            setattr(self, direction, bound_signals)

    def send(self, signalName, value, id=None):
        """
        Send a `value` on the `signalName` widget output.

        An output with `signalName` must be defined in the class ``outputs``
        list.
        """
        if not any(s.name == signalName for s in self.outputs):
            raise ValueError('{} is not a valid output signal for widget {}'.format(
                signalName, self.name))
        if self.signalManager is not None:
            self.signalManager.send(self, signalName, value, id)

    def handleNewSignals(self):
        """
        Invoked by the workflow signal propagation manager after all
        signals handlers have been called.
        Reimplement this method in order to coalesce updates from
        multiple updated inputs.
        """
        pass

    # Methods used by the meta class
    @classmethod
    def convert_signals(cls):
        """
        Convert tuple descriptions into old-style signals for backwards
        compatibility, and check the input handlers exist.
        The method is called from the meta-class.
        """
        def signal_from_args(args, signal_type):
            if isinstance(args, tuple):
                return signal_type(*args)
            elif isinstance(args, signal_type):
                return copy.copy(args)

        if hasattr(cls, "inputs") and cls.inputs:
            cls.inputs = [signal_from_args(input_, InputSignal)
                          for input_ in cls.inputs]
        if hasattr(cls, "outputs") and cls.outputs:
            cls.outputs = [signal_from_args(output, OutputSignal)
                           for output in cls.outputs]

        cls._check_input_handlers()

    @classmethod
    def _check_input_handlers(cls):
        unbound = [signal.name
                   for _, signal in getsignals(cls.Inputs)
                   if not signal.handler]
        if unbound:
            raise ValueError("unbound signal(s) in {}: {}".
                             format(cls.__name__, ", ".join(unbound)))

        missing_handlers = [signal.handler for signal in cls.inputs
                            if not hasattr(cls, signal.handler)]
        if missing_handlers:
            raise ValueError("missing handlers in {}: {}".
                             format(cls.__name__, ", ".join(missing_handlers)))

    @classmethod
    def get_signals(cls, direction, ignore_old_style=False):
        """
        Return a list of `InputSignal` or `OutputSignal` needed for the
        widget description. For old-style signals, the method returns the
        original list. New-style signals are collected into a list.

        Parameters
        ----------
        direction (str): `"inputs"` or `"outputs"`

        Returns
        -------
        list of `InputSignal` or `OutputSignal`
        """
        old_style = cls.__dict__.get(direction, None)
        if old_style and not ignore_old_style:
            return old_style

        signal_class = getattr(cls, direction.title())
        signals = [signal for _, signal in getsignals(signal_class)]
        return list(sorted(signals, key=lambda s: s._seq_id))

    def update_summaries(self):
        info = self.info
        if self.input_summaries:
            self._update_summary(self.input_summaries,
                                 self.info.set_input_summary, info.NoInput)
        if self.output_summaries:
            self._update_summary(self.output_summaries,
                                 self.info.set_output_summary, info.NoOutput)

    def set_partial_input_summary(self, name, partial_summary, *, id=None):
        self._set_and_update_summary(
            self.input_summaries, name, id, partial_summary,
            self.info.set_input_summary, self.info.NoInput)

    def set_partial_output_summary(self, name, partial_summary, *, id=None):
        self._set_and_update_summary(
            self.output_summaries, name, id, partial_summary,
            self.info.set_output_summary, self.info.NoOutput)

    @classmethod
    def _set_and_update_summary(cls, summaries, name, id, partial_summary,
                                setter, empty_obj):
        if partial_summary.summary is None:
            if id in summaries[name]:
                del summaries[name][id]
        else:
            summaries[name][id] = partial_summary
        cls._update_summary(summaries, setter, empty_obj)

    @staticmethod
    def _update_summary(summaries, setter, empty_obj):
        from orangewidget.widget import StateInfo

        def format_short(partial):
            summary = partial.summary
            if summary is None:
                return "-"
            if isinstance(summary, int):
                return StateInfo.format_number(summary)
            if isinstance(summary, str):
                return summary
            raise ValueError("summary must be None, string or int; "
                             f"got {type(summary).__name__}")

        def format_detail(partial):
            if partial.summary is None:
                return "-"
            return str(partial.details or partial.summary)

        def join_multiples(partials):
            if not partials:
                return "-", "-"
            shorts = " ".join(map(format_short, partials.values()))
            if len(partials) == 1:
                details = format_detail(next(iter(partials.values())))
            else:
                details = "<ul>" \
                          + "".join(f"<li>{format_detail(partial)}</li>"
                                    for partial in partials.values()) \
                          + "</ul>"
            return shorts, details

        if not any(summaries.values()):
            summary, detail = empty_obj, ""
        else:
            summary, details = zip(*map(join_multiples, summaries.values()))
            summary = " | ".join(summary)
            detail = "<hr/><table>" \
                     + "".join(f"<tr><th><nobr>{name}</nobr>: "
                               f"</th><td>{detail}</td></tr>"
                               for name, detail in zip(summaries, details)) \
                     + "</table>"
        if detail:
            setter(summary, SUMMARY_STYLE + detail, format=Qt.RichText)
        else:
            setter(summary)


class AttributeList(list):
    """Signal type for lists of attributes (variables)"""
