==============
Jupyter-Remote
==============

`Jupyter-Remote <https://github.com/aaronkollasch/jupyter-remote>`_
is a command-line tool that automatically runs Jupyter on a remote server.

It aims to streamline remote Jupyter usage for a range of remote configurations, from
simple servers to SLURM clusters that require request forwarding to a compute node.
It is derived from `Jupyter-O2 <https://github.com/aaronkollasch/jupyter-o2>`_.

Installation
------------------------------

Set up Jupyter on the remote server.

Next, install Jupyter-Remote.

.. code-block:: console

    pip install jupyter-remote

Then, generate the config file.

.. code-block:: console

    jupyter-remote --generate-config

Follow the printed path to ``jupyter-remote.cfg`` and edit to suit your needs.

For more info on setting up Jupyter and troubleshooting Jupyter-Remote, see the `jupyter-remote tips`_.

.. _jupyter-remote tips: https://github.com/aaronkollasch/jupyter-remote/blob/master/jupyter_remote_tips.rst

Usage
------------------------------

.. code-block:: console

    jupyter-remote [subcommand]

If Jupyter is installed on your machine, Jupyter-Remote can be run as a Jupyter subcommand:

.. code-block:: console

    jupyter remote lab

Jupyter-Remote works great with `JupyterLab <https://github.com/jupyterlab/jupyterlab>`__!

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

TODOs
------------------------------
* shortcut for selectable server profiles and configurations
* add a use_x11 option to make X11 optional (unnecessary for some configurations)
