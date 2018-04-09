==============
Jupyter-Remote
==============

`Jupyter-Remote <https://github.com/aaronkollasch/jupyter-remote>`_
is a command-line tool that automatically runs Jupyter on a remote server.
It is derived from `Jupyter-O2 <https://github.com/aaronkollasch/jupyter-o2>`_.

Installation
------------------------------

Set up Jupyter on the remote server.
If running on O2, follow the `O2 wiki's procedure <https://wiki.rc.hms.harvard.edu/display/O2/Jupyter+on+O2>`_.

Next, install Jupyter-Remote.

.. code-block:: console

    pip install jupyter-remote

Then, generate the config file.

.. code-block:: console

    jupyter-remote --generate-config

Follow the printed path to ``jupyter-remote.cfg`` and edit according to its instructions, particularly the fields
``DEFAULT_USER``, ``DEFAULT_HOST``, ``MODULE_LOAD_CALL``, ``SOURCE_JUPYTER_CALL``, and ``INIT_JUPYTER_COMMANDS``.

For more info on setting up Jupyter and troubleshooting Jupyter-Remote, see the `jupyter-remote tips`_.

.. _jupyter-remote tips: https://github.com/aaronkollasch/jupyter-remote/blob/master/jupyter_remote_tips.rst

Usage
------------------------------
.. code-block:: console

    jupyter-remote [subcommand]

Examples: ``jupyter-remote notebook`` or ``jupyter-remote lab``
(try `JupyterLab <https://github.com/jupyterlab/jupyterlab>`__!)

If Jupyter is installed on your machine, Jupyter-Remote can also be run as a Jupyter subcommand:

.. code-block:: console

    jupyter remote lab

For info on the Jupyter-Remote command-line options, use ``jupyter-remote --help``.

Requirements and compatibility
------------------------------
* python 2.7 or 3.6
* pexpect.pxssh
* POSIX: Jupyter-Remote has been tested on MacOS. It may work on Linux, and on Windows it will
  require Cygwin and Cygwin's version of Python.

Optional installs
------------------------------
* pinentry (a command line tool used instead of getpass)
