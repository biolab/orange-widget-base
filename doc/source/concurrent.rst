.. currentmodule:: orangewidget.utils.concurrent

:mod:`orangewidget.utils.concurrent`
------------------------------------

.. automodule:: orangewidget.utils.concurrent

.. autoclass:: FutureWatcher
    :show-inheritance:
    :members:
    :exclude-members:
        done, finished, cancelled, resultReady, exceptionReady

    .. autoattribute:: done(future: Future)

    .. autoattribute:: finished(future: Future)

    .. autoattribute:: cancelled(future: Future)

    .. autoattribute:: resultReady(result: Any)

    .. autoattribute:: exceptionReady(exception: BaseException)


.. autoclass:: FutureSetWatcher
    :show-inheritance:
    :members:
    :exclude-members:
        doneAt, finishedAt, cancelledAt, resultReadyAt, exceptionReadyAt,
        progressChanged, doneAll

    .. autoattribute:: doneAt(index: int, future: Future)

    .. autoattribute:: finishedAt(index: int, future: Future)

    .. autoattribute:: cancelledAt(index: int, future: Future)

    .. autoattribute:: resultReadyAt(index: int, result: Any)

    .. autoattribute:: exceptionReadyAt(index: int, exception: BaseException)

    .. autoattribute:: progressChanged(donecount: int, count: int)

    .. autoattribute:: doneAll()


.. autoclass:: methodinvoke
    :members:

