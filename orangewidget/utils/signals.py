import copy
import itertools
import warnings
from functools import singledispatch
import inspect
from typing import (
    NamedTuple, Union, Optional, Iterable, Dict, Tuple, Any, Sequence,
    Callable
)

from AnyQt.QtCore import Qt

from orangecanvas.registry.description import (
    InputSignal, OutputSignal, Single, Multiple, Default, NonDefault,
    Explicit, Dynamic
)
from orangewidget.workflow.utils import WeakKeyDefaultDict


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
summarize.__doc__ = """
Function for summarizing the input or output data.

The function must be decorated with `@summarize.register`. It accepts an
argument of arbitrary type and returns a `PartialSummary`, which is a tuple
consisting of two strings: a short summary (usually a number) and details.
"""


SUMMARY_STYLE = """
<style>
    ul {
        margin-left: 4px;
        margin-top: 2px;
        -qt-list-indent:1
    }

    li {
        margin-bottom: 3px;
    }

    th {
        text-align: right;
    }
</style>
"""


def can_summarize(type_, name, explicit):
    if explicit is not None:
        return explicit
    if not isinstance(type_, tuple):
        type_ = (type_, )
    instr = f"To silence this warning, set auto_summary of '{name}' to False."
    for a_type in type_:
        if isinstance(a_type, str):
            warnings.warn(
                f"Output is specified with qualified name ({a_type}). "
                "To enable auto summary, set auto_summary to True. "
                + instr, UserWarning)
            return False
        if summarize.dispatch(a_type) is base_summarize:
            warnings.warn(
                f"register 'summarize' function for type {a_type.__name__}. "
                + instr, UserWarning)
            return False
    return True


Closed = type(
    "Closed", (object,), {
        "__doc__": "Explicit connection closing sentinel.",
        "__repr__": lambda self: "Closed",
        "__str__": lambda self: "Closed",
    }
)()


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
        by default, the input is reflected in widget's summary for all types
        with registered `summarize` function. This can be overridden by
        explicitly setting `auto_summary` to `False` or `True`. Explicitly
        setting this argument will also silence warnings for types without
        the summary function and for types defined with a fully qualified
        string instead of an actual type object.
    """
    Closed = Closed

    def __init__(self, name, type, id=None, doc=None, replaces=None, *,
                 multiple=False, default=False, explicit=False,
                 auto_summary=None, closing_sentinel=None):
        flags = self.get_flags(multiple, default, explicit, False)
        super().__init__(name, type, "", flags, id, doc, replaces or [])
        self.auto_summary = can_summarize(type, name, auto_summary)
        self._seq_id = next(_counter)
        self.closing_sentinel = closing_sentinel

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


class MultiInput(Input):
    """
    A special multiple input descriptor.

    This type of input has explicit set/insert/remove interface to maintain
    fully ordered sequence input. This should be preferred to the
    plain `Input(..., multiple=True)` descriptor.

    This input type must register three methods in the widget implementation
    class corresponding to the insert, set/update and remove input commands::

        class Inputs:
            values = MultiInput("Values", object)
        ...
        @Inputs.values
        def set_value(self, index: int, value: object):
            "Set/update the value at index"
            ...
        @Inputs.values.insert
        def insert_value(self, index: int, value: object):
            "Insert value at specified index"
            ...
        @Inputs.values.remove
        def remove_value(self, index: int):
            "Remove value at index"
            ...

    Parameters
    ----------
    filter_none: bool
        If `True` any `None` values sent by workflow execution
        are implicitly converted to 'remove' notifications. When the value
        again changes to non-None the input is re-inserted into its proper
        position.


    .. versionadded:: 4.13.0
    """
    insert_handler: str = None
    remove_handler: str = None

    def __init__(self, *args, filter_none=False, **kwargs):
        multiple = kwargs.pop("multiple", True)
        if not multiple:
            raise ValueError("multiple cannot be set to False")
        super().__init__(*args, multiple=True, **kwargs)
        self.filter_none = filter_none
        self.closing_sentinel = Closed

    __summary_ids_mapping = WeakKeyDefaultDict(dict)
    __id_gen = itertools.count()

    def __get_summary_ids(self, widget: 'WidgetSignalsMixin'):
        ids = self.__summary_ids_mapping[widget]
        return ids.setdefault(self.name, [])

    def __call__(self, method):
        def summarize_wrapper(widget, index, value):
            ids = self.__get_summary_ids(widget)
            widget.set_partial_input_summary(
                self.name, summarize(value), id=ids[index], index=index)
            method(widget, index, value)
        _ = super().__call__(method)
        return summarize_wrapper if self.auto_summary else method

    def insert(self, method):
        """Register the method as the insert handler"""
        def summarize_wrapper(widget, index, value):
            ids = self.__get_summary_ids(widget)
            ids.insert(index, next(self.__id_gen))
            widget.set_partial_input_summary(
                self.name, summarize(value), id=ids[index], index=index)
            method(widget, index, value)
        self.insert_handler = method.__name__
        return summarize_wrapper if self.auto_summary else method

    def remove(self, method):
        """"Register the method as the remove handler"""
        def summarize_wrapper(widget, index):
            ids = self.__get_summary_ids(widget)
            id_ = ids.pop(index)
            widget.set_partial_input_summary(
                self.name, summarize(None), id=id_)
            method(widget, index)
        self.remove_handler = method.__name__
        return summarize_wrapper if self.auto_summary else method

    def bound_signal(self, widget):
        if self.insert_handler is None:
            raise RuntimeError('insert_handler is not set')
        if self.remove_handler is None:
            raise RuntimeError('remove_handler is not set')
        return super().bound_signal(widget)


_not_set = object()


def _parse_call_id_arg(id=_not_set):
    if id is _not_set:
        return None
    else:
        warnings.warn(
            "`id` parameter is deprecated and will be removed in the "
            "future", FutureWarning, stacklevel=3,
        )
        return id


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
        by default, the output is reflected in widget's summary for all types
        with registered `summarize` function. This can be overridden by
        explicitly setting `auto_summary` to `False` or `True`. Explicitly
        setting this argument will also silence warnings for types without
        the summary function and for types defined with a fully qualified
        string instead of an actual type object.
    """
    def __init__(self, name, type, id=None, doc=None, replaces=None, *,
                 default=False, explicit=False, dynamic=True,
                 auto_summary=None):
        flags = self.get_flags(False, default, explicit, dynamic)
        super().__init__(name, type, flags, id, doc, replaces or [])
        self.auto_summary = can_summarize(type, name, auto_summary)
        self.widget = None
        self._seq_id = next(_counter)

    def send(self, value, *args, **kwargs):
        """Emit the signal through signal manager."""
        assert self.widget is not None
        id = _parse_call_id_arg(*args, **kwargs)
        signal_manager = self.widget.signalManager
        if signal_manager is not None:
            if id is not None:
                extra_args = (id,)
            else:
                extra_args = ()
            signal_manager.send(self.widget, self.name, value, *extra_args)
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

    def send(self, signalName, value, *args, **kwargs):
        """
        Send a `value` on the `signalName` widget output.

        An output with `signalName` must be defined in the class ``outputs``
        list.
        """
        id = _parse_call_id_arg(*args, **kwargs)
        if not any(s.name == signalName for s in self.outputs):
            raise ValueError('{} is not a valid output signal for widget {}'.format(
                signalName, self.name))

        if self.signalManager is not None:
            if id is not None:
                extra_args = (id,)
            else:
                extra_args = ()
            self.signalManager.send(self, signalName, value, *extra_args)

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
        self._update_summary(self.input_summaries)
        self._update_summary(self.output_summaries)

    def set_partial_input_summary(self, name, partial_summary, *, id=None, index=None):
        self.__set_part_summary(self.input_summaries[name], id, partial_summary, index=index)
        self._update_summary(self.input_summaries)

    def set_partial_output_summary(self, name, partial_summary, *, id=None):
        self.__set_part_summary(self.output_summaries[name], id, partial_summary)
        self._update_summary(self.output_summaries)

    @staticmethod
    def __set_part_summary(summary, id, partial_summary, index=None):
        if partial_summary.summary is None:
            if id in summary:
                del summary[id]
        else:
            if index is None or id in summary:
                summary[id] = partial_summary
            else:
                # Insert inplace at specified index
                items = list(summary.items())
                items.insert(index, (id, partial_summary))
                summary.clear()
                summary.update(items)

    def _update_summary(self, summaries):
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
            details = "<br/>".join(format_detail(partial) for partial in partials.values())
            return shorts, details

        info = self.info
        is_input = summaries is self.input_summaries
        assert is_input or summaries is self.output_summaries

        if not summaries:
            return
        if not any(summaries.values()):
            summary = info.NoInput if is_input else info.NoOutput
            detail = ""
        else:
            summary, details = zip(*map(join_multiples, summaries.values()))
            summary = " | ".join(summary)
            detail = "<hr/><table>" \
                     + "".join(f"<tr><th><nobr>{name}</nobr>: "
                               f"</th><td>{detail}</td></tr>"
                               for name, detail in zip(summaries, details)) \
                     + "</table>"

        setter = info.set_input_summary if is_input else info.set_output_summary
        if detail:
            setter(summary, SUMMARY_STYLE + detail, format=Qt.RichText)
        else:
            setter(summary)


def get_input_meta(widget: WidgetSignalsMixin, name: str) -> Optional[Input]:
    """
    Return the named input meta description from widget (if it exists).
    """
    def as_input(obj):
        if isinstance(obj, Input):
            return obj
        elif isinstance(obj, InputSignal):
            rval = Input(obj.name, obj.type, obj.id, obj.doc, obj.replaces,
                         multiple=not obj.single, default=obj.default,
                         explicit=obj.explicit)
            rval.handler = obj.handler
            return rval
        elif isinstance(obj, tuple):
            return as_input(InputSignal(*obj))
        else:
            raise TypeError

    inputs: Iterable[Input] = map(as_input, widget.get_signals("inputs"))
    for input_ in inputs:
        if input_.name == name:
            return input_
    return None


def get_widget_inputs(
        widget: WidgetSignalsMixin
) -> Dict[str, Sequence[Tuple[Any, Any]]]:
    state: Dict[str, Sequence[Tuple[Any, Any]]]
    state = widget.__dict__.setdefault(
        "_WidgetSignalsMixin__input_state", {}
    )
    return state


@singledispatch
def notify_input_helper(
        input: Input, widget: WidgetSignalsMixin, obj, key=None, index=-1
) -> None:
    """
    Set the input to the `widget` in a way appropriate for the `input` type.
    """
    raise NotImplementedError


@notify_input_helper.register(Input)
def set_input_helper(
        input: Input, widget: WidgetSignalsMixin, obj, key=None, index=-1
):
    handler = getattr(widget, input.handler)
    if input.single:
        args = (obj,)
    else:
        args = (obj, key)
    handler(*args)


@notify_input_helper.register(MultiInput)
def set_multi_input_helper(
        input: MultiInput, widget: WidgetSignalsMixin, obj, key=None, index=-1,
):
    """
    Set/update widget's input for a `MultiInput` input to obj.

    `key` must be a unique for an input slot to update.
    `index` defines the position where a new input (key that did not
    previously exist) is inserted. The default -1 indicates that the
    new input should be appended to the end. An input is removed by using
    inout.closing_sentinel as the obj.
    """
    inputs_ = get_widget_inputs(widget)
    inputs = list(inputs_.setdefault(input.name, ()))
    filter_none = input.filter_none

    signal_old = None
    key_to_pos = {key: i for i, (key, _) in enumerate(inputs)}
    update = key in key_to_pos
    new = key not in key_to_pos
    remove = obj is input.closing_sentinel
    if new:
        if not 0 <= index < len(inputs):
            index = len(inputs)
    else:
        index = key_to_pos.get(key)
        assert index is not None

    if new:
        inputs.insert(index, (key, obj))
    elif remove:
        signal_old = inputs.pop(index)
    else:
        signal_old = inputs[index]
        inputs[index] = (key, obj)

    inputs_[input.name] = tuple(inputs)

    if filter_none:
        def filter_f(obj):
            return obj is None
    else:
        filter_f = None

    def local_index(
            key: Any, inputs: Sequence[Tuple[Any, Any]],
            filter: Optional[Callable[[Any], bool]] = None,
    ) -> Optional[int]:
        i = 0
        for k, obj in inputs:
            if key == k:
                return i
            elif filter is not None:
                i += int(not filter(obj))
            else:
                i += 1
        return None

    if filter_none:
        # normalize signal.value is None to Close signal.
        filtered = filter_f(obj)
        if new and filtered:
            # insert in inputs only (done above)
            return
        elif new:
            # Some inputs before this might be filtered invalidating the
            # effective index. Find appropriate index for insertion
            index = len([obj for _, obj in inputs[:index] if not filter_f(obj)])
        elif remove:
            if filter_f(signal_old[1]):
                # was already notified as removed, only remove from inputs (done above)
                return
        elif update and filtered:
            if filter_f(signal_old[1]):
                # did not change; remains filtered
                return
            else:
                # remove it
                remove = True
                new = False
                index = local_index(key, inputs, filter_f)
                assert index is not None
        elif update:
            index = local_index(key, inputs, filter_f)

        if signal_old is not None and filter_f(signal_old[1]) and not filtered:
            # update with non-none value, substitute as new signal
            new = True
            remove = False
            index = local_index(key, inputs, filter_f)

    if new:
        handler = input.insert_handler
        args = (index, obj)
    elif remove:
        handler = input.remove_handler
        args = (index, )
    else:
        handler = input.handler
        args = (index, obj)
    assert index is not None
    handler = getattr(widget, handler)
    handler(*args)
