Orange Widget Base
==================

Orange Widget Base provides a base widget component for a interactive GUI
based workflow. It is primarily used in the [Orange] data mining application.

[Orange]: http://orange.biolab.si/

Orange Widget Base requires Python 3.6 or newer.

Installing with pip
-------------------

    # Create a separate Python environment for Orange and its dependencies ...
    python3 -m venv orangevenv
    # ... and make it the active one
    source orangevenv/bin/activate

    # Clone the repository and move into it
    git clone https://github.com/biolab/orange-widget-base.git
    cd orange-widget-base

    # Install Qt dependencies for the GUI
    pip install PyQt5 PyQtWebEngineCore

    # Finally install this in editable/development mode.
    pip install -e .

Starting the GUI
----------------

Start a default workflow editor GUI with

    python -m orangecanvas --config orangewidget.workflow.config.Config
