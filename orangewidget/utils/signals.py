import copy
import itertools
import warnings
from functools import singledispatch
import inspect

from orangecanvas.registry.description import (
    InputSignal, OutputSignal, Single, Multiple, Default, NonDefault,
    Explicit, Dynamic
)


# increasing counter for ensuring the order of Input/Output definitions
# is preserved when going through the unordered class namespace of
# WidgetSignalsMixin.Inputs/Outputs.
_counter = itertools.count()


def base_summarize(_):
    return None, None

summarize = singledispatch(base_summarize)

def can_summarize(type_, name):
    if summarize.dispatch(type_) is base_summarize:
        warnings.warn(
            f"declare 'summarize' for type {type_.__name__};"
            f"to silence this warning, set auto_sumarize of signal '{name}' to"
            "False",
            UserWarning)
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
        def summarize_wrapper(widget, value, *args, **kwargs):
            if self.auto_summary:
                if value is None:
                    summary, details = widget.info.NoInput, ""
                else:
                    summary, details = summarize(value)
                    if summary is None:
                        return
                widget.set_partial_input_summary(self.name, summary, details)
            method(widget, value, *args, **kwargs)

        if self.handler:
            raise ValueError("Input {} is already bound to method {}".
                             format(self.name, self.handler))
        self.handler = method.__name__
        return summarize_wrapper


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

        if self.auto_summary:
            if value is None:
                summary, details = self.widget.info.NoOutput, ""
            else:
                summary, details = summarize(value)
                if summary is None:
                    return
            self.widget.set_partial_output_summary(self.name, summary, details)

        signal_manager = self.widget.signalManager
        if signal_manager is not None:
            signal_manager.send(self.widget, self.name, value, id)

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
        from orangewidget.widget import StateInfo

        for direction, summaries, empty in (
                ("Inputs", self.input_summaries, StateInfo.NoInput),
                ("Outputs", self.output_summaries, StateInfo.NoOutput)):
            bound_cls = getattr(self, direction)
            bound_signals = bound_cls()
            for name, signal in getsignals(bound_cls):
                setattr(bound_signals, name, signal.bound_signal(self))
                if signal.auto_summary:
                    summaries[signal.name] = (empty, "")
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

    def set_partial_input_summary(self, name, summary, details):
        self.input_summaries[name] = [summary, details]
        self._update_summary(self.info.set_input_summary, self.input_summaries)

    def set_partial_output_summary(self, name, summary, details):
        self.output_summaries[name] = (summary, details)
        self._update_summary(self.info.set_output_summary, self.output_summaries)

    @staticmethod
    def _update_summary(setter, summaries):
        from orangewidget.widget import StateInfo

        def format_short(short):
            if short is None or isinstance(short, StateInfo.Empty):
                return "-"
            if isinstance(short, int):
                return StateInfo.format_number(short)
            if isinstance(short, str):
                return short
            raise ValueError("summary must be None, empty, string or int; got "
                             + type(short).__name__)

        def format_detail(short, detail):
            if short is None or isinstance(short, StateInfo.Empty):
                return "-"
            return str(detail or short)

        if not summaries:
            return
        shorts, details = zip(*summaries.values())
        if len(summaries) == 1 \
                or all(isinstance(short, StateInfo.Empty) for short in shorts):
            # If all are empty, the output should be shown as empty
            # If there is just one output, skip the empty line and signal name
            summary, detail = shorts[0], details[0]
        else:
            summary = " | ".join(map(format_short, shorts))
            detail = "\n".join(
                f"\n{name}:\n{format_detail(short, detail)}"
                for name, short, detail in zip(summaries, shorts, details))
        setter(summary, detail)


class AttributeList(list):
    """Signal type for lists of attributes (variables)"""
