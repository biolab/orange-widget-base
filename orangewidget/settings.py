"""Widget Settings and Settings Handlers

Settings are used to declare widget attributes that persist through sessions.
When widget is removed or saved to a schema file, its settings are packed,
serialized and stored. When a new widget is created, values of attributes
marked as settings are read from disk. When schema is loaded, attribute values
are set to one stored in schema.

Allowed setting types are
- str
- bool
- int (Integral values are converted to int when saving and kept int at load)
- float (Number values are converted to float when saving and kept int at load)
- bytes (implicitly b64encoded/decoded),
- IntEnum (implicitly encoded/decoded as int),

and the following generics, whose elements must be one of allowed types
- List
- Dict (keys must not be generics; values can be any allowed type)
- Set (converted to list and back)
- NamedTuple (implicitly converted to tuple and back)
- Tuple (converted to list and back)

Derived setting handlers may add additional types if the provide proper
conversion.

Unsupported types result in non-JSON-able settings and raise warnings - at best.

Each widget has its own SettingsHandler that takes care of serializing and
storing of settings and SettingProvider that is incharge of reading and
writing the setting values.

All widgets extending from OWBaseWidget use SettingsHandler, unless they
declare otherwise. SettingsHandler ensures that setting attributes
are replaced with default (last used) setting values when the widget is
initialized and stored when the widget is removed.

Widgets with settings whose values depend on the widget inputs use
settings handlers based on ContextHandler. These handlers have two
additional methods, open_context and close_context.

open_context is called when widgets receives new data. It finds a suitable
context and sets the widget attributes to the values stored in context.
If no suitable context exists, a new one is created and values from widget
are copied to it.

close_context stores values that were last used on the widget to the context
so they can be used alter. It should be called before widget starts modifying
(initializing) the value of the setting attributes.
"""

import base64
import sys
import copy
import os
import logging
import pickle
import pprint
import warnings
from enum import IntEnum
from numbers import Number, Integral
from operator import itemgetter
from typing import get_type_hints, \
    Any, List, Tuple, Dict, Union, BinaryIO, \
    Type, TypeVar, Callable, Generator, Optional, Iterator

from orangewidget.gui import OWComponent

log = logging.getLogger(__name__)

__all__ = [
    "Setting", "SettingsHandler", "SettingProvider",
    "ContextSetting", "Context", "ContextHandler", "IncompatibleContext",
    "SettingsPrinter", "rename_setting", "widget_settings_dir"
]

_IMMUTABLES = (str, int, bytes, bool, float, tuple)

VERSION_KEY = "__version__"

# protocol v4 is supported since Python 3.4, protocol v5 since Python 3.8
PICKLE_PROTOCOL = 4


__WIDGET_SETTINGS_DIR = None  # type: Optional[Tuple[str, str]]

_T = TypeVar("_T")


def _cname(obj: Any) -> str:
    if not isinstance(obj, type):
        obj = type(obj)
    return obj.__name__

# TODO: Remove parts of the below when we drop support for earlier versions
if sys.version_info >= (3, 8):
    from typing import get_origin, get_args

elif sys.version_info >= (3, 7):
    def get_args(tp):
        return getattr(tp, "__args__", None)

    def get_origin(tp):
        return getattr(tp, "__origin__", None)

else:
    assert sys.version_info[:2] == (3, 6)

    def get_args(tp):
        return getattr(tp, "__args__", None)

    def get_origin(tp):
        # Python 3.6's typing is an embarassing mess
        for base in getattr(tp, "__orig_bases__", ()):
            if type(base) is type:
                return base
        if hasattr(tp, "__origin__"):
            return tp.__origin__
        return None


def set_widget_settings_dir_components(basedir: str, versionstr: str) -> None:
    """
    Set the directory path components where widgets save their settings.

    This overrides the global current application name/version derived paths.

    Note
    ----
    This should be set early in the application startup before any
    `OWBaseWidget` subclasses are imported (because it is needed at class
    definition time).

    Parameters
    ----------
    basedir: str
        The application specific data directory.
    versionstr: str
        The application version string for the versioned path component.

    See Also
    --------
    widget_settings_dir
    """
    global __WIDGET_SETTINGS_DIR
    __WIDGET_SETTINGS_DIR = (basedir, versionstr)


def widget_settings_dir(versioned=True) -> str:
    """
    Return the effective directory where widgets save their settings.

    This is a composed path based on a application specific data directory
    and application version string (if `versioned` is True) with a final
    'widgets' path component added (e.g. `'~/.local/share/MyApp/9.9.9/widgets'`)

    By default `QCoreApplication.applicationName` and
    `QCoreApplication.applicationVersion` are used to derive suitable paths
    (with a fallback if they are not set).

    Note
    ----
    If the application sets the `applicationName`/`applicationVersion`, it
    should do this early in the application startup before any
    `OWBaseWidget` subclasses are imported (because it is needed at class
    definition time).

    Use `set_widget_settings_dir_components` to override the default paths.

    Parameters
    ----------
    versioned: bool
        Should the returned path include the application version component.

    See Also
    --------
    set_widget_settings_dir_components
    """
    if __WIDGET_SETTINGS_DIR is None:
        from orangewidget.workflow.config import data_dir
        return os.path.join(data_dir(versioned), "widgets")
    else:
        base, version = __WIDGET_SETTINGS_DIR
        if versioned:
            return os.path.join(base, version, "widgets")
        else:
            return os.path.join(base, "widgets")


class Setting:
    """Description of a setting.
    """

    # Settings are automatically persisted to disk
    packable = True

    # Setting is only persisted to schema (default value does not change)
    schema_only = False

    # Setting can be None
    nullable = False

    def __new__(cls, default, *args, **kwargs):
        """A misleading docstring for providing type hints for Settings

        :type: default: T
        :rtype: T
        """
        return super().__new__(cls)

    def __init__(self, default, **data):
        self.name = None  # Name gets set in widget's meta class
        self.default = default
        if default is None:
            self.nullable = True  # if default is None, assume this is OK
            self.type = None
        else:
            self.type = type(default)
        self.__dict__.update(data)

    def __str__(self):
        if self.name is None:
            return "Unbound {_cname(self)}"
        return f'{_cname(self)} "{self.name}"'

    __repr__ = __str__

    def __getnewargs__(self):
        return (self.default, )


# Pylint ignores type annotations in assignments. For
# TODO: Check whether this is still the case; if not, remove this hack
#
#    x: int = Setting(0)
#
# it ignores `int` and assumes x is of type `Setting`. Annotations in
# comments ( # type: int) also don't work. The only way to annotate x is
#
#    x: int
#    x = Setting(0)
#
# but we don't want to clutter the code with extra lines of annotations. Hence
# we disable checking the type of `Setting` by confusing pylint with an extra
# definition that is never executed.
if 1 == 0:
    class Setting:  # pylint: disable=function-redefined
        pass


class SettingProvider:
    """A hierarchical structure keeping track of settings belonging to
    a class and child setting providers.

    At instantiation, it creates a dict of all Setting and SettingProvider
    members of the class. This dict is used to get/set values of settings
    from/to the instances of the class this provider belongs to.
    """

    def __init__(self, provider_class: Type[OWComponent]):
        """
        Construct a new instance of SettingProvider.

        Traverse provider_class members and store all instances of
        Setting and SettingProvider.

        Args:
            provider_class (OWComponent): class containing settings definitions
        """
        self.name = ""
        self.provider_class = provider_class
        self.providers: Dict[str, SettingProvider] = {}
        self.settings: Dict[str, Setting] = {}
        self.initialization_data = {}

        try:
            type_hints = get_type_hints(provider_class)
        except Exception as exc:
            type_hints = None
            warnings.warn(
                f"{_cname(provider_class)} has invalid annotations: {exc}")

        def set_type():
            if type_hints is None:
                return
            # type hint has precedence over type deduced from default value
            # (but if they mismatch, we will complain later, at packing)
            value.type = type_hints.get(name, value.type)
            if get_origin(value.type) is Union:
                args = get_args(value.type)
                if len(args) == 2 and args[1] is type(None):
                    value.type = args[0]
                    value.nullable = True

        for name in dir(provider_class):
            value = getattr(provider_class, name, None)
            if isinstance(value, Setting):
                value = copy.deepcopy(value)
                value.name = name
                set_type()
                self.settings[name] = value
            if isinstance(value, SettingProvider):
                value = copy.deepcopy(value)
                value.name = name
                self.providers[name] = value

    def initialize(self, component: OWComponent, data: Optional[dict] = None) \
            -> None:
        """
        Initialize instance settings to given data or to defaults.

        Mutable values are (shallow) copied before they are assigned to the
        widget. Immutable are used as-is.

        Args:
            component (OWComponent): widget or component to initialize
            data (dict or None): data used to override the defaults
        """
        if data is None:
            data = self.initialization_data

        for name, setting in self.settings.items():
            value = data.get(name, setting.default)
            if not isinstance(value, _IMMUTABLES):
                value = copy.copy(value)
            setattr(component, name, value)

        for name, provider in self.providers.items():
            if name not in data:
                continue

            member = getattr(component, name, None)
            if member is None or isinstance(member, SettingProvider):
                provider.store_initialization_data(data[name])
            else:
                provider.initialize(member, data[name])

    def reset_to_original(self, instance):
        self.initialize(instance)

    def store_initialization_data(self, initialization_data: dict) -> None:
        """
        Store initialization data for later use.

        Used when settings handler is initialized, but member for this
        provider does not exists yet, because handler.initialize is called in
        __new__, but member will be created in __init__.

        Args:
            initialization_data (dict):
                data for initialization of a new component
        """
        self.initialization_data = initialization_data

    @classmethod
    def default_packer(cls,
                       setting: Setting,
                       component: OWComponent,
                       handler: "SettingsHandler") -> Iterator[Tuple[str, Any]]:
        """Yield setting name and value for packable (= non-context) setting."""
        if setting.packable:
            value = getattr(component, setting.name)
            if handler.is_allowed_type(setting.type) \
                    and not handler.check_warn_type(value, setting, component):
                value = handler.pack_value(value, setting.type)
            yield setting.name, value

    PackerType = Callable[[Setting, OWComponent, "SettingsHandler"],
                          Iterator[Tuple[str, Any]]]

    def pack(self, widget: "OWBaseWidget",
             packer: Optional[PackerType] = None) -> dict:
        """
        Pack instance settings in a name:value dict.

        Args:
            widget (OWBaseWidget): widget instance
        """
        if packer is None:
            packer = self.default_packer
        handler = widget.settingsHandler
        return self._pack_component(widget, handler, packer)

    def _pack_component(
            self, component: OWComponent, handler: "SettingsHandler",
            packer: PackerType) -> dict:

        packed_settings = {}
        comp_name = _cname(component)
        for setting in self.settings.values():
            for name, value in packer(setting, component, handler):
                packed_settings[setting.name] = value

        for name, provider in self.providers.items():
            if not hasattr(component, name):
                warnings.warn(f"{name} is declared as setting provider "
                              f"on {comp_name}, but not present on instance.")
                continue
            instance = getattr(component, name)
            packed_settings[name] = \
                provider._pack_component(instance, handler, packer)
        return packed_settings

    def unpack(self, widget: "OWBaseWidget", packed_data: dict) -> None:
        """Restore settings from packed_data to widget instance."""
        handler = widget.settingsHandler
        for setting, data_, inst in self.traverse_settings(packed_data, widget):
            if setting.name in data_ and inst is not None:
                handler._apply_setting(setting, inst, data_[setting.name])

    def get_provider(self, provider_class: Type[OWComponent]) \
            -> Union["SettingProvider", None]:
        """Return provider for the given provider_class."""
        if issubclass(provider_class, self.provider_class):
            return self

        for subprovider in self.providers.values():
            provider = subprovider.get_provider(provider_class)
            if provider:
                return provider
        return None

    def traverse_settings(self,
                          data: Optional[dict] = None,
                          instance: Optional[OWComponent] = None) \
            -> Generator[Tuple[Setting, dict, OWComponent], None, None]:
        """
        Iterate over settings of this component and its child providers.

        Generator returns tuples (setting, data, instance)

        Args:
            data (dict): dictionary with values for this component and children
            instance (OWComponent): instance matching setting_provider
        """
        if data is None:
            data = {}

        for setting in self.settings.values():
            yield setting, data, instance

        for provider in self.providers.values():
            data_ = data.get(provider.name, {})
            instance_ = getattr(instance, provider.name, None)
            yield from provider.traverse_settings(data_, instance_)


class SettingsHandler:
    """Reads widget setting files and passes them to appropriate providers."""

    def __init__(self):
        """Create a setting handler template.

        Used in class definition. Bound instance will be created
        when SettingsHandler.create is called.
        """
        self.widget_class: Union[Type["OWWidgetBase"], None] = None  #
        self.provider: Union[SettingProvider, None] = None
        self.defaults = {}
        self.known_settings = {}

    @staticmethod
    def create(widget_class: Type["OWWidgetBase"],
               template: Optional["SettingsHandler"] = None) \
            -> "SettingsHandler":
        """
        Return a new handler based on the template and bound to widget_class.

        Args:
            widget_class (WidgetMetaClass): widget class
            template (SettingsHandler): SettingsHandler to copy setup from
        """

        if template is None:
            template = SettingsHandler()

        setting_handler = copy.copy(template)
        setting_handler.defaults = {}
        setting_handler.bind(widget_class)
        return setting_handler

    def bind(self, widget_class: Type["OWWidgetBase"]) -> None:
        """Bind settings handler instance to widget_class."""
        self.widget_class = widget_class
        self.provider = SettingProvider(widget_class)
        self.known_settings = {}
        self.analyze_settings(self.provider, "", _cname(widget_class))
        self.read_defaults()

    def analyze_settings(self,
                         provider: SettingProvider,
                         prefix: str, class_name: str) -> None:
        """
        Analyze settings at and below the provider

        Args:
            provider (SettingProvider): setting provider
            prefix (str): prefix (relative to widget) that matches the provider
        """
        for setting in provider.settings.values():
            self.analyze_setting(prefix, setting, class_name)

        for name, sub_provider in provider.providers.items():
            new_prefix = f"{prefix}{name}."
            self.analyze_settings(sub_provider, new_prefix, class_name)

    def analyze_setting(self, prefix: str, setting: Setting, class_name:str) \
            -> None:
        """Perform any initialization tasks related to setting."""
        sname = prefix + setting.name
        tname = _cname(setting.type)
        if setting.type is None:
            warnings.warn(f"type for setting '{class_name}.{sname}' "
                          "is unknown; annotate it.")
        elif setting.type in (list, tuple, dict, set):
            warnings.warn(f"type for items in the {tname} "
                          f"in '{class_name}.{sname}' is unknown; "
                          f"annotate it with {tname.title()}[<type>]")
            setting.type = None
        elif not self.is_allowed_type(setting.type):
            warnings.warn(f"{_cname(self)} does not support {tname} used "
                          f"in {class_name}.{sname}) ")
            setting.type = None

        self.known_settings[prefix + setting.name] = setting

    def read_defaults(self) -> None:
        """
        Read (global) defaults for this widget class from a file.

        Opens a file and calls :obj:`read_defaults_file`.
        Derived classes should overload the latter."""
        filename = self._get_settings_filename()
        if os.path.isfile(filename):
            with open(filename, "rb") as settings_file:
                try:
                    self.read_defaults_file(settings_file)
                # Unpickling exceptions can be of any type
                except Exception as ex:  # pylint: disable=broad-except
                    warnings.warn(
                        "Error reading defaults for "
                        f"{_cname(self.widget_class)}:\n\n{ex}")

    def read_defaults_file(self, settings_file: BinaryIO) -> None:
        """Read (global) defaults for this widget class from a file."""
        def no_settings(impure):
            pure = {}
            for key, value in impure.items():
                if isinstance(value, dict):
                    pure[key] = no_settings(value)
                elif isinstance(value, Setting):
                    pure[key] = value.default
                else:
                    pure[key] = value
            return pure

        defaults = pickle.load(settings_file)
        self.defaults = no_settings(defaults)
        self._migrate_settings(self.defaults)

    def write_defaults(self) -> None:
        """
        Write (global) defaults for this widget class to a file.
        Opens a file and calls :obj:`write_defaults_file`. Derived classes
        should overload the latter."""
        filename = self._get_settings_filename()
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        try:
            with open(filename, "wb") as settings_file:
                self.write_defaults_file(settings_file)
        except PermissionError as ex:
            log.error("Could not write default settings for %s (%s).",
                      self.widget_class, type(ex).__name__)
        except (EOFError, IOError, pickle.PicklingError) as ex:
            log.error("Error writing defaults for %s (%s).",
                      _cname(self.widget_class), type(ex).__name__)
            os.remove(filename)

    def write_defaults_file(self, settings_file: BinaryIO) -> None:
        """Write defaults for this widget class to a file."""
        defaults = dict(self.defaults)
        defaults[VERSION_KEY] = self.widget_class.settings_version
        pickle.dump(defaults, settings_file, protocol=PICKLE_PROTOCOL)

    def _get_settings_filename(self) -> str:
        """Return the name of the file with default settings for the widget"""
        cls = self.widget_class
        return os.path.join(widget_settings_dir(),
                            f"{cls.__module__}.{cls.__qualname__}.pickle")

    def initialize(self,
                   component: OWComponent,
                   data: Union[bytes, dict, None] = None) -> None:
        """
        Set widget's or component's settings to default

        Args:
            widget (OWBaseWidget): widget to initialize
            data (dict or bytes): data or bytes that unpickle to data
        """
        provider: SettingProvider = self._select_provider(component)

        if isinstance(data, bytes):
            data = pickle.loads(data)
        for setting, data_, _ in provider.traverse_settings(data):
            name = setting.name
            if setting.name in data_ and self.is_allowed_type(setting.type):
                data_[name] = self.unpack_value(data_[name], setting.type)
        self._migrate_settings(data)

        if provider is self.provider:
            data = self._add_defaults(data)

        provider.initialize(component, data)

    def reset_to_original(self, widget: "OWBaseWidget") -> None:
        provider = self._select_provider(widget)
        provider.reset_to_original(widget)

    def _migrate_settings(self, settings: dict) -> None:
        """Let widget migrate settings to the latest version."""
        if not settings:
            return

        try:
            self.widget_class.migrate_settings(
                settings, settings.pop(VERSION_KEY, 0))
        except Exception:  # pylint: disable=broad-except
            sys.excepthook(*sys.exc_info())
            settings.clear()

    def _select_provider(self, instance: "OWBaseWidget") -> SettingProvider:
        provider = self.provider.get_provider(instance.__class__)
        if provider is None:
            warnings.warn(
                f"{_cname(instance)} has not been declared as setting provider"
                f"in {_cname(self.widget_class)}. Settings will not be"
                f"saved/loaded properly. Defaults will be used instead.")
            provider = SettingProvider(instance.__class__)
        return provider

    def _add_defaults(self, data: Optional[dict] = None) -> dict:
        if data is None:
            return self.defaults

        new_data = self.defaults.copy()
        new_data.update(data)
        return new_data

    def _prepare_defaults(self, widget: "OWBaseWidget") -> None:
        self.defaults = self.provider.pack(widget)
        for setting, data, _ in self.provider.traverse_settings(data=self.defaults):
            if setting.schema_only:
                data.pop(setting.name, None)

    def pack_data(self, widget: "OWBaseWidget") -> dict:
        """
        Pack the settings for the given widget. This method is used when
        saving schema, so that when the schema is reloaded the widget is
        initialized with its proper data and not the class-based defaults.
        See :obj:`SettingsHandler.initialize` for detailed explanation of its
        use.

        Inherited classes add other data, in particular widget-specific
        local contexts.
        """
        widget.settingsAboutToBePacked.emit()
        packed_settings = self.provider.pack(widget)
        packed_settings[VERSION_KEY] = self.widget_class.settings_version
        return packed_settings

    def update_defaults(self, widget: "OWBaseWidget") -> None:
        """
        Writes widget instance's settings to class defaults. Called when the
        widget is deleted.
        """
        widget.settingsAboutToBePacked.emit()
        self._prepare_defaults(widget)
        self.write_defaults()

    def reset_settings(self, widget: "OWBaseWidget") -> None:
        """Reset widget settings to defaults"""
        for setting, _, inst \
                in self.provider.traverse_settings(instance=widget):
            if setting.packable:
                self._apply_setting(setting, inst, setting.default)

    @classmethod
    def _apply_setting(cls,
                       setting: Setting, instance: OWComponent, value: Any
                       ) -> None:
        """
        Set `setting` of widget `instance` to the given `value`, in place if
        possible.

        If old and new values are of the same type, and the type is either a list
        or has methods `clear` and `update`, setting is updated in place. Otherwise
        the function calls `setattr`.
        """
        cls.check_warn_type(value, setting, instance)
        target = getattr(instance, setting.name, None)
        if type(target) is type(value):
            if isinstance(value, list):
                target[:] = value
                return
            elif hasattr(value, "clear") and hasattr(value, "update"):
                target.clear()
                target.update(value)
                return
        setattr(instance, setting.name, value)

    @staticmethod
    def _non_none(args):
        return [tp_ for tp_ in args if tp_ is not type(None)][0]

    @classmethod
    def is_allowed_type(cls, tp) -> bool:
        if tp in (str, bool, bytes, float, int):
            return True
        if isinstance(tp, type):
            if issubclass(tp, IntEnum):
                return True
            # When we drop support for Python 3.6, remove the second test
            if issubclass(tp, tuple) and not hasattr(tp, "__origin__"):
                # If it's tuple, it must be a NamedTuple of allowed types
                args = getattr(tp, "__annotations__", None)
                return args is not None \
                       and all(map(cls.is_allowed_type, args.values()))

        orig, args = get_origin(tp), get_args(tp)
        if orig is None:
            return False
        if orig is Union:
            return len(args) == 2 and type(None) in args \
                   and cls.is_allowed_type(cls._non_none(args))
        if orig in (list, set) \
                or orig is tuple and len(args) == 2 and args[1] is ...:
            return cls.is_allowed_type(args[0])
        if orig is tuple:
            return all(map(cls.is_allowed_type, args))
        if orig is dict:
            return args[0] in (str, bool, int, float) \
                   and cls.is_allowed_type(args[1])

    @classmethod
    def check_type(cls, value, tp) -> bool:
        # To do: This would be much more elegant if singledispatchmethod
        # (backported from Python 3.8) worked with classmethods.
        # It should, but the example from Python documentation crashes
        # (https://bugs.python.org/issue39679)
        if value is None:
            return tp is type(None) \
                   or isinstance(tp, Setting) and tp.nullable \
                   or get_origin(tp) is Union and type(None) in tp.__args__

        if isinstance(tp, Setting):
            tp = tp.type

        if not cls.is_allowed_type(tp):
            # We take no responsibility for invalid types
            return True

        # Simple types
        if tp in (str, bytes):
            return isinstance(value, tp)

        # Numeric types that can be safely converted
        if tp is int:
            return isinstance(value, Integral)
        if tp is float:
            return isinstance(value, Number)
        if tp is bool:
            # (0, 1) also covers False and True
            return value in (0, 1) and not isinstance(value, float)

        # Named tuple: a tuple with annotations
        # TODO: Simplify when we drop support for Python 3.6
        if sys.version_info[:2] > (3, 6) and isinstance(tp, type) or \
                sys.version_info[:2] == (3, 6) \
                and (tp in (str, bytes)
                     or (isinstance(tp, type)
                         and (issubclass(tp, IntEnum)
                              or (issubclass(tp, tuple)
                                  and hasattr(tp, "__annotations__")
                                  )
                              )
                         )
                ):
            if issubclass(tp, tuple):
                assert hasattr(tp, "__annotations__")
                return isinstance(value, tp) \
                    and all(isinstance(x, tp_)
                            for x, tp_ in zip(value, tp.__annotations__.values())
                            )
            return isinstance(value, tp)

        # Common type check for generic classes
        orig, args = get_origin(tp), get_args(tp)

        if orig is Union:
            assert len(args) == 2 and type(None) in args
            return value is None or cls.check_type(value, cls._non_none(args))

        if not isinstance(value, orig):
            return False

        # set, list and tuple of homogenous type with variable length
        if orig in (set, list) \
                or orig is tuple and len(args) == 2 and args[1] is ...:
            tp1 = args[0]
            return all(cls.check_type(x, tp1) for x in value)
        # tuple with fixed length and types
        if orig is tuple:
            return len(value) == len(args) \
                   and all(cls.check_type(x, tp1)
                           for x, tp1 in zip(value, args))
        # dicts
        if orig is dict:
            keytype, valuetype = args
            return all(isinstance(k, keytype) and cls.check_type(v, valuetype)
                       for k, v in value.items())

    @classmethod
    def check_warn_type(cls, value,
                        setting: Setting,
                        component: OWComponent) -> None:
        if value is None:
            if not setting.nullable:
                warnings.warn(
                    f"a non-nullable {_cname(component)}.{setting.name} is None"
                )
        elif not cls.check_type(value, setting.type):
            sname = f"{_cname(component)}.{setting.name}"
            if isinstance(setting.type, type):
                decl = _cname(setting.type)
            else:
                decl = str(setting.type).replace("typing.", "")
            act = repr(value)
            if len(act) > 300:
                act = act[:300] + " (...)"
            warnings.warn(
                f"setting {sname} is declared as {decl} but contains {act}")
            return True
        return False

    @classmethod
    def check_warn_pure_type(cls, value, type_: type, name: str):
        if cls.check_type(value, type_):
            return False
        if isinstance(type_, type):
            decl = _cname(type_)
        else:
            decl = str(type_).replace("typing.", "")
        act = repr(value)
        if len(act) > 30:
            act = act[:30] + " (...)"
        warnings.warn(f"'{name}' is declared as {decl} but contains {act}")
        return True

    @classmethod
    def pack_value(cls, value, tp=None):
        if tp is None:
            if isinstance(value, (tuple, set)):
                return list(value)
            else:
                return value

        if value is None:
            return None
        if tp is float and isinstance(value, int):
            return value
        if tp is bool:
            return bool(value) if value in (False, True, 0, 1) else value
        if tp is str:
            return value  # if value is not our string, it's not our problem
        if tp in (int, float):
            try:
                return tp(value)
            except ValueError:
                return value
        if tp is bytes:
            return base64.b64encode(value).decode("ascii")
        if isinstance(tp, type):
            if issubclass(tp, IntEnum):
                return int(value)
            if issubclass(tp, tuple) and hasattr(tp, "__annotations__"):
                return [cls.pack_value(x, tp_)
                        for x, tp_ in zip(value, tp.__annotations__)]

        orig, args = get_origin(tp), get_args(tp)
        if orig is Union:
            return cls.pack_value(value, cls._non_none(args))
        if orig in (set, list) \
                or orig is tuple and len(args) == 2 and args[1] is ...:
            tp_ = args[0]
            return [cls.pack_value(x, tp_) for x in value]
        if orig is tuple:
            return [cls.pack_value(x, tp_) for x, tp_ in zip(value, args)]
        if orig is dict:
            kt, vt = args
            return {cls.pack_value(k, kt): cls.pack_value(v, vt)
                    for k, v in value.items()}

        # Shouldn't come to this, but ... what the heck.
        return value

    @classmethod
    def unpack_value(cls, value, tp):
        if value is None or tp in (int, bool, float, str):
            return value
        if tp is bytes:
            return base64.b64decode(value.encode("ascii"))
        if isinstance(tp, type):
            if issubclass(tp, IntEnum):
                return tp(value)
            if issubclass(tp, tuple) and hasattr(tp, "__annotations__"):
                return tuple(cls.unpack_value(x, tp_)
                             for x, tp_ in zip(value, tp.__annotations__))

        orig, args = get_origin(tp), get_args(tp)
        if orig is Union:
            return cls.unpack_value(value, cls._non_none(args))
        if orig in (set, list) \
                or orig is tuple and len(args) == 2 and args[1] is ...:
            tp_ = args[0]
            return orig(cls.unpack_value(x, tp_) for x in value)
        if orig is tuple:
            return tuple(cls.unpack_value(x, tp_) for x, tp_ in zip(value, args))
        if orig is dict:
            kt, vt = args
            return {cls.unpack_value(k, kt): cls.unpack_value(v, vt)
                    for k, v in value.items()}

        # Shouldn't come to this, but ... what the heck.
        return value


class ContextSetting(Setting):
    """Description of a context dependent setting"""

    OPTIONAL = 0
    REQUIRED = 2

    # Context settings are not persisted, but are stored in context instead.
    packable = False

    # These flags are not general - they assume that the setting has to do
    # something with the attributes. Large majority does, so this greatly
    # simplifies the declaration of settings in widget at no (visible)
    # cost to those settings that don't need it
    def __init__(self, default, *, required=2,
                 exclude_attributes=False, exclude_metas=False, **data):
        super().__init__(default, **data)
        self.exclude_attributes = exclude_attributes
        self.exclude_metas = exclude_metas
        self.required = required


class Context:
    """Class for data that defines context and
    values that should be applied to widget if given context
    is encountered."""
    def __init__(self, **argkw):
        self.values = {}
        self.__dict__.update(argkw)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


if not hasattr(Context, "__annotations__"):
    Context.__annotations__ = {}
Context.__annotations__[VERSION_KEY] = Optional[int]


class ContextHandler(SettingsHandler):
    """Base class for setting handlers that can handle contexts.

    Classes deriving from it need to implement method `match`.
    """

    NO_MATCH = 0
    MATCH = 1
    PERFECT_MATCH = 2

    MAX_SAVED_CONTEXTS = 50

    ContextType = Context

    def __init__(self):
        super().__init__()
        self.global_contexts = []

    def initialize(self, instance: "OWBaseWidget", data=None):
        """Initialize the widget: call the inherited initialization and
        add an attribute 'context_settings' to the widget. This method
        does not open a context."""
        instance.current_context = None
        super().initialize(instance, data)
        if data and "context_settings" in data:
            instance.context_settings = [
                self.unpack_context(context)
                for context in data["context_settings"]]
            for context in instance.context_settings:
                self.unpack_context_values(context)
            self._migrate_contexts(instance.context_settings)
        else:
            instance.context_settings = []

    def read_defaults_file(self, settings_file: BinaryIO) -> None:
        """Call the inherited method, then unpickle and migrate contexts"""
        super().read_defaults_file(settings_file)
        self.global_contexts = pickle.load(settings_file)
        self._migrate_contexts(self.global_contexts)

    def _migrate_contexts(self, contexts: List[Context]) -> None:
        i = 0
        while i < len(contexts):
            context = contexts[i]
            try:
                self.widget_class.migrate_context(
                    context, context.values.pop(VERSION_KEY, 0))
            except IncompatibleContext:
                del contexts[i]
            except Exception:  # pylint: disable=broad-except
                sys.excepthook(*sys.exc_info())
                del contexts[i]
            else:
                i += 1

    def write_defaults_file(self, settings_file: BinaryIO) -> None:
        """Call the inherited method, then add global context to the pickle."""
        super().write_defaults_file(settings_file)

        def with_version(context: Context):
            context = copy.copy(context)
            context.values = dict(context.values)
            context.values[VERSION_KEY] = self.widget_class.settings_version
            return context

        pickle.dump([with_version(context) for context in self.global_contexts],
                    settings_file, protocol=PICKLE_PROTOCOL)

    def pack_data(self, widget: "OWBaseWidget") -> dict:
        """Call the inherited method, then add local contexts to the dict."""
        data = super().pack_data(widget)
        self.settings_from_widget(widget)
        context_settings = list(map(self.pack_context, widget.context_settings))
        for context in context_settings:
            context["values"][VERSION_KEY] = self.widget_class.settings_version
        data["context_settings"] = context_settings
        return data

    def update_defaults(self, widget: "OWBaseWidget"):
        """
        Reimplemented from SettingsHandler

        Merge the widgets local contexts into the global contexts and persist
        the settings (including the contexts) to disk.
        """
        widget.settingsAboutToBePacked.emit()
        self.settings_from_widget(widget)
        globs = self.global_contexts
        assert widget.context_settings is not globs
        new_contexts = []
        for context in widget.context_settings:
            context = copy.deepcopy(context)
            for setting, data, _ in self.provider.traverse_settings(data=context.values):
                if setting.schema_only:
                    data.pop(setting.name, None)
            if context not in globs:
                new_contexts.append(context)
        globs[:0] = reversed(new_contexts)
        del globs[self.MAX_SAVED_CONTEXTS:]

        # Save non-context settings. Do not call super().update_defaults, so that
        # settingsAboutToBePacked is emitted once.
        self._prepare_defaults(widget)
        self.write_defaults()

    def new_context(self, *args) -> Context:
        """Create a new context."""
        return self.ContextType()

    def open_context(self, widget: "OWBaseWidget", *args) -> None:
        """Open a context by finding one and setting the widget data or
        creating one and fill with the data from the widget."""
        widget.current_context, is_new = \
            self.find_or_create_context(widget, *args)
        if is_new:
            self.settings_from_widget(widget, *args)
        else:
            self.settings_to_widget(widget, *args)

    def match(self, context: Context, *args):
        """Return the degree to which the stored `context` matches the data
        passed in additional arguments).
        When match returns 0 (ContextHandler.NO_MATCH), the context will not
        be used. When it returns ContextHandler.PERFECT_MATCH, the context
        is a perfect match so no further search is necessary.

        If imperfect matching is not desired, match should only
        return ContextHandler.NO_MATCH or ContextHandler.PERFECT_MATCH.

        Derived classes must overload this method.
        """
        raise NotImplementedError

    def find_or_create_context(self, widget: "OWBaseWidget", *args) \
            -> Tuple[Context, bool]:
        """Find the best matching context or create a new one if nothing
        useful is found. The returned context is moved to or added to the top
        of the context list."""

        # First search the contexts that were already used in this widget instance
        best_context, best_score = self.find_context(
            widget.context_settings, args, move_up=True)
        # If the exact data was used, reuse the context
        if best_score == self.PERFECT_MATCH:
            return best_context, False

        # Otherwise check if a better match is available in global_contexts
        best_context, best_score = self.find_context(
            self.global_contexts, args, best_score, best_context)
        if best_context:
            context = self.clone_context(best_context, *args)
        else:
            context = self.new_context(*args)
        # Store context in widget instance. It will be pushed to global_contexts
        # when (if) update defaults is called.
        self.add_context(widget.context_settings, context)
        return context, best_context is None

    def find_context(self, known_contexts: List[Context], args,
                     best_score=0, best_context: Optional[Context] = None,
                     move_up=False) -> Tuple[Optional[Context], int]:
        """
        Search the given list of contexts and return the context that
        best matches the given args.

        best_score and best_context can be used to provide base_values.
        """

        best_idx = None
        for i, context in enumerate(known_contexts):
            score = self.match(context, *args)
            if score > best_score:  # NO_MATCH is not OK!
                best_context, best_score, best_idx = context, score, i
                if score == self.PERFECT_MATCH:
                    break
        if best_idx is not None and move_up:
            self.move_context_up(known_contexts, best_idx)
        return best_context, best_score

    @staticmethod
    def move_context_up(contexts: List[Context], index: int) -> None:
        """Move the context to the top of the list"""
        contexts.insert(0, contexts.pop(index))

    def add_context(self, contexts: List[Context], setting: Context):
        """Add the context to the top of the list."""
        contexts.insert(0, setting)
        del contexts[self.MAX_SAVED_CONTEXTS:]

    def clone_context(self, old_context: Context, *args) -> Context:
        """Construct a copy of the context settings suitable for the context
        described by additional arguments. The method is called by
        find_or_create_context with the same arguments. A class that overloads
        :obj:`match` to accept additional arguments must also overload
        :obj:`clone_context`."""
        context = self.new_context(*args)
        context.values = copy.deepcopy(old_context.values)

        traverse = self.provider.traverse_settings
        for setting, data, _ in traverse(data=context.values):
            if not isinstance(setting, ContextSetting):
                continue

            self.filter_value(setting, data, *args)
        return context

    @staticmethod
    def filter_value(setting: Context, data: dict, *args) -> None:
        """Remove values related to setting that are invalid given args."""

    def close_context(self, widget: "OWBaseWidget") -> None:
        """Close the context by calling :obj:`settings_from_widget` to write
        any relevant widget settings to the context."""
        if widget.current_context is None:
            return

        self.settings_from_widget(widget)
        widget.current_context = None

    def settings_to_widget(self, widget: "OWBaseWidget", *args) -> None:
        """Apply context settings from currently opened context to the widget"""
        context = widget.current_context
        if context is None:
            return

        widget.retrieveSpecificSettings()

        for setting, data, instance in \
                self.provider.traverse_settings(data=context.values, instance=widget):
            if not isinstance(setting, ContextSetting) or setting.name not in data:
                continue
            value = self.decode_setting(setting, data[setting.name], *args)
            self._apply_setting(setting, instance, value)

    def settings_from_widget(self, widget: "OWBaseWidget", *args) -> None:
        """Update the current context with the setting values from the widget.
        """

        context = widget.current_context
        if context is None:
            return

        widget.storeSpecificSettings()

        def packer(setting: Setting, component: OWComponent, handler: ContextHandler):
            if isinstance(setting, ContextSetting) \
                    and hasattr(component, setting.name):
                value = orig_value = getattr(component, setting.name)
                handler.check_warn_type(value, setting, component)
                value = self.encode_setting(context, setting, value)
                # if encode_setting encoded a value, we assume the type is
                # supported - just convert sets and tuples to lists
                value = self.pack_value(
                    value, setting.type if value is orig_value else None)
                yield setting.name, self.encode_setting(context, setting, value)

        context.values = self.provider.pack(widget, packer=packer)

    @staticmethod
    def update_packed_data(data: dict, name: str, value) -> None:
        """Updates setting value stored in data dict"""
        *prefixes, name = name.split('.')
        for prefix in prefixes:
            data = data.setdefault(prefix, {})
        data[name] = value

    def encode_setting(self,
                       context: Context, setting: Setting, value: _T) -> _T:
        """Encode value to be stored in settings dict"""
        return copy.copy(value)

    def decode_setting(self, setting: Setting, value, *args):
        """Decode settings value from the setting dict format"""
        return value

    @classmethod
    def pack_context(cls, context: Context):
        ctx_dict = context.__dict__.copy()
        annotations = getattr(cls.ContextType, "__annotations__", {})
        for name, type_ in annotations.items():
            if name in ctx_dict \
                    and not cls.check_warn_pure_type(
                        ctx_dict[name], type_, f"{_cname(context)}.{name}"):
                ctx_dict[name] = cls.pack_value(ctx_dict[name], type_)
            else:
                warnings.warn(f"{_cname(cls.ContextType)}.{name} is not set.")
        for name in ctx_dict:
            if name not in "values" and name not in annotations:
                warnings.warn(
                    f"{_cname(cls.ContextType)}.{name} must be annotated")
        return ctx_dict

    @classmethod
    def unpack_context(cls, context: Union[dict, Context]):
        if isinstance(context, Context):
            return context

        annotations = getattr(cls.ContextType, "__annotations__", {})
        for name, type_ in annotations.items():
            if name in context and cls.is_allowed_type(type_):
                context[name] = cls.unpack_value(context[name], type_)
        return Context(**context)

    def unpack_context_values(self, context: Context):
        provider = self.provider
        for setting, data, _ in provider.traverse_settings(context.values):
            if setting.name in data and self.is_allowed_type(setting.type):
                data[setting.name] = \
                    self.unpack_value(data[setting.name], setting.type)


class IncompatibleContext(Exception):
    """Raised when a required variable in context is not available in data."""


class SettingsPrinter(pprint.PrettyPrinter):
    """Pretty Printer that knows how to properly format Contexts."""

    def _format(self, obj, stream, indent, allowance, context, level):
        if not isinstance(obj, Context):
            super()._format(obj, stream, indent, allowance, context, level)
            return

        stream.write("Context(")
        for key, value in sorted(obj.__dict__.items(), key=itemgetter(0)):
            if key == "values":
                continue
            stream.write(key)
            stream.write("=")
            stream.write(self._repr(value, context, level + 1))
            stream.write(",\n")
            stream.write(" " * (indent + 8))
        stream.write("values=")
        stream.write(" ")
        self._format(obj.values, stream, indent+15,
                     allowance+1, context, level + 1)
        stream.write(")")


def rename_setting(settings: Union[Context, dict],
                   old_name: str, new_name: str) -> None:
    """
    Rename setting from `old_name` to `new_name`. Used in migrations.

    The argument `settings` can be `dict` or `Context`.
    """
    if isinstance(settings, Context):
        rename_setting(settings.values, old_name, new_name)
    else:
        settings[new_name] = settings.pop(old_name)


_apply_setting = SettingsHandler._apply_setting  # backward compatibility
