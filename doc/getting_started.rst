Getting Started
===============

Installing the code
-------------------

Installing Python
.................

 * Download and install Enthought Python Distribution (32-bit)

 * Download and install the correct version of PyQt4 (see what version of Python
   comes with Enthought Python Distribution.  As of 3/29/11 it was Python 2.7).
   You need to match both the Python number and the architecture (32-bit or
   64-bit).  Since you installed the 32-bit Enthought Python Distribution, you
   would download the 32-bit version of PyQt4.


Installing Neurobehavior
........................

All the standard Python approaches to getting set up will work.  However, I
recommend you install this as local copy that you can edit if you wish to create
new paradigms (e.g. add the root neurobehavior folder to the PYTHONPATH
environment variable).  Right now there is a hard-coded limitation (controlled
by :func:`experiments.loader.get_experiment`) that requires all experiment
paradigms to be inside the :mod:`paradigms` package.  

The approach I recommend is to use Python's pip tool.  First, let's make sure
that it's installed (PythonXY and Enthought's Python Distribution do not come
with this tool by default)::

    $ easy_install pip

Once it's installed, install a copy of Mercurial (Hg) if you haven't already.
The source code for TDTPy is managed via the Mercurial distributed version
control system and pip requires the Hg binary to checkout a copy of TDTPy::

    $ pip install mercurial

.. note::

    Installing Mercurial from source requires a working compiler.  If the above
    command fails with the error message, "unable to find vcvarsall.bat", you
    need to install a compiler.  On Windows, you can install Microsoft Visual
    Studio 2008 Express (the `version of Visual Studio`_ is important).
    Alternatively, it may be much easier to just install the TortoiseHg_
    binaries

.. _TortoiseHg: http://tortoisehg.bitbucket.org/
.. _version of Visual Studio: http://slacy.com/blog/2010/09/python-unable-to-find-vcvarsall-bat

Now, install a local (editable) copy of Neurobehavior::

    $ pip install -e hg+http://bitbucket.org/bburan/neurobehavior#egg=neurobehavior

Now, install the Neurobehavior dependencies::

    $ pip install hg+http://bitbucket.org/bburan/tdtpy
    $ pip install hg+http://bitbucket.org/bburan/new-era

Setting up for experiments
--------------------------

If you plan to run the code in the experiments or paradigms module, it is
recommended you set up a place on your hard disk to store the relevant files.
The suggested folder structure is below::

    data/
    settings/
        paradigm/
        physiology/
    calibration/
    temp/
    logs/

Once you've set up this folder, create an environment variable,
NEUROBEHAVIOR_BASE, that points to the folder containing the data, settings,
calibration, temp and logs folder, e.g.::

    setx NEUROBEHAVIOR_SETTINGS d:\\>

Overriding defaults defined in cns.settings
-------------------------------------------

Many configuratble settings are defined in cns.settings.  These can be overriden
on a per-computer (or per-user account basis) by creating your own
local_settings.py file containing the values of the settings you want to
override.  Note that local_settings.py is an actual Python file, so you can
compute the values of the settings using Python expressions.

If you create a custom settings file, you need to create an environment
variable, NEUROBEHAVIOR_SETTINGS, whose value is the full path to the settings
file.  There are several ways to do this, the simplest being to open a
command-lime prompt and type::

    setx NEUROBEHAVIOR_SETTINGS c:\users\sanesadmin\user_settings.py

Note that this only sets the environment variable for the current users.  If you
wish to set the value of the variable for all users (you'll have to open the
command shell as an administrator to do so)::

    setx NEUROBEHAVIOR_SETTINGS c:\users\sanesadmin\local_settings.py /m

.. note:: 

    Technically you can call your custom settings file anything you want, but
    Antje pointed out that naming it settings.py might be confusing so it's best
    to use a different name.

Example local_settings.py file to override the default syringe, calibration
file, and colors used in the experiments::

    CAL_PRIMARY = 'd:\\calibration\\110911_Vifa_Tweeter_1.cal'
    SYRINGE_DEFAULT = 'B-D 20cc (plastic)'

    # Those colors Brad chose for the trial log table are plain ugly.  Let's use
    # better colors.  Colors must be specified as RGB tuples.
    EXPERIMENT_COLORS  = {
        'GO_REMIND':    (0.32, 0.13, 0.45),
        'GO':           (0.11, 0.11, 0.11),
        'NOGO_REPEAT':  (0.32, 0.32, 0),
        'NOGO':         (1, 0, 1),
        }

.. note::

    You cannot import the cns module in your local_settings.py file because the
    import of cns will trigger a circular import (when importing cns, the module
    will attempt to import the local settings file so it can read the values
    stored in it).
