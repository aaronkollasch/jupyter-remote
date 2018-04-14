==============
Jupyter-Remote
==============

`Jupyter-Remote <https://github.com/aaronkollasch/jupyter-remote>`_
is a command-line tool that automatically runs Jupyter on a remote server.
It is derived from `Jupyter-O2 <https://github.com/aaronkollasch/jupyter-o2>`_.

Jupyter-Remote aims to streamline remote Jupyter usage for a range of remote configurations,
from simple servers to SLURM clusters that require request forwarding to a compute node.

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

    jupyter-remote [profile] [subcommand]

Both arguments are optional.

If Jupyter is installed on your machine, Jupyter-Remote can be run as a Jupyter subcommand:

.. code-block:: console

    jupyter remote o2 lab

Be sure to try out `JupyterLab <https://github.com/jupyterlab/jupyterlab>`__!

For more info on the Jupyter-Remote command-line options, use ``jupyter-remote --help``.

Profiles
------------------------------
Make a copy of ``jupyter-remote.cfg`` and name it ``jupyter-remote-[profile name].cfg``.
See ``example_cfgs/jupyter-remote-o2.cfg``.

Note: Both the profile and subcommand option are optional.
If only one is provided, Jupyter-Remote will first look for a profile with that name,
and if none is found, it will use the default profile with the given subcommand.

Requirements and compatibility
------------------------------
* python 2.7 or 3.6
* pexpect.pxssh
* POSIX: Jupyter-Remote has been tested on MacOS and Linux, while on Windows it will
  require Cygwin and Cygwin's version of Python.

Optional installs
------------------------------
* pinentry (a command line tool used instead of getpass)
