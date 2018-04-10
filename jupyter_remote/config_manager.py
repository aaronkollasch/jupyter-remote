import os
import sys
from errno import EEXIST
try:
    from ConfigParser import SafeConfigParser as ConfigParser
except ImportError:
    from configparser import ConfigParser
import argparse

DNS_SERVER_GROUPS = []
# test that you can access the login nodes (on macs) with nslookup login01.o2.rc.hms.harvard.edu <DNS>

JRMT_DEFAULTS = {
    "DEFAULT_USER": "",
    "DEFAULT_HOST": "o2.hms.harvard.edu",
    "DEFAULT_JP_PORT": 8887,
    "DEFAULT_JP_TIME": "0-12:00",
    "DEFAULT_JP_MEM": "1G",
    "DEFAULT_JP_CORES": 1,
    "DEFAULT_JP_SUBCOMMAND": "notebook",

    "MODULE_LOAD_CALL": "",
    "SOURCE_JUPYTER_CALL": "",
    "INIT_JUPYTER_COMMANDS": "",
    "RUN_JUPYTER_CALL_FORMAT": "jupyter {subcommand} --port={port} --no-browser",
    "PORT_RETRIES": 10,
    "FORCE_GETPASS": False,

    "USE_INTERNAL_INTERACTIVE_SESSION": True,
    "INTERACTIVE_CALL_FORMAT": "srun -t {time} --mem {mem} -c {cores} --pty -p interactive --x11 /bin/bash",
    "PASSWORD_REQUEST_PATTERN": "[\w-]+@[\w-]+'s password:",
    "DNS_SERVER_GROUPS": DNS_SERVER_GROUPS,
    "FORWARD_X11": True,
}
JRMT_DEFAULTS_STR = {key: str(value) for key, value in JRMT_DEFAULTS.items()}

CFG_FILENAME = "jupyter-remote.cfg"
CFG_DIR = "jupyter-remote"


def _generate_search_locations(dirname=CFG_DIR, filename=CFG_FILENAME):
    return [                                                    # In order of increasing priority:
        os.path.join("/etc", dirname, filename),                    # /etc/jupyter-remote/jupyter-remote.cfg
        os.path.join("/usr/local/etc", dirname, filename),          # /usr/local/etc/jupyter-remote/jupyter-remote.cfg
        os.path.join(sys.prefix, "etc", dirname, filename),         # etc/jupyter-remote/jupyter-remote.cfg
        os.path.join(os.path.expanduser("~"), "." + filename),  # ~/.jupyter-remote.cfg
        filename,                                               # ./jupyter-remote.cfg
    ]


CFG_SEARCH_LOCATIONS = _generate_search_locations()


def generate_config_file(config_dir=None):
    """Write the default configuration file. Overwrites any existing config file.
    :param config_dir: The directory to place the config file,
    or None or True to use the default directory.
    :return: The config file location
    """
    from pkg_resources import resource_string

    if config_dir is None or config_dir is True:
        config_dir = os.path.join(sys.prefix, "etc", CFG_DIR)
    elif config_dir is False:
        return

    config_path = os.path.join(config_dir, CFG_FILENAME)

    resource_package = __name__
    resource_path = '/'.join((CFG_FILENAME,))

    # py27-compatible version of os.makedirs(config_dir, exist_ok=True)
    try:
        os.makedirs(config_dir)
    except OSError as e:
        if e.errno != EEXIST:
            raise

    default_config = resource_string(resource_package, resource_path)

    with open(config_path, 'wb') as config_file:
        config_file.write(default_config)

    return config_path


def get_base_arg_parser():
    parser = argparse.ArgumentParser(description='Launch and connect to a Jupyter session on a remote server')
    parser.add_argument("profile", type=str, nargs='?', help="the config profile (optional)")
    parser.add_argument("subcommand", type=str, nargs='?', help="the subcommand to launch (optional)")
    parser.add_argument("-u", "--user", default=JRMT_DEFAULTS.get("DEFAULT_USER"), type=str,
                        help="your remote username")
    parser.add_argument("--host", type=str, default=JRMT_DEFAULTS.get("DEFAULT_HOST"),
                        help="host to connect to")
    parser.add_argument("-p", "--port", dest="jp_port", metavar="PORT", type=int,
                        default=JRMT_DEFAULTS.get("DEFAULT_JP_PORT"),
                        help="available port on your system")
    parser.add_argument("-t", "--time", dest="jp_time", metavar="TIME", type=str,
                        default=JRMT_DEFAULTS.get("DEFAULT_JP_TIME"),
                        help="maximum time for Jupyter session")
    parser.add_argument("-m", "--mem", dest="jp_mem", metavar="MEM", type=str,
                        default=JRMT_DEFAULTS.get("DEFAULT_JP_MEM"),
                        help="memory to allocate for Jupyter")
    parser.add_argument("-c", "-n", dest="jp_cores", metavar="CORES", type=int,
                        default=JRMT_DEFAULTS.get("DEFAULT_JP_CORES"),
                        help="cores to allocate for Jupyter")
    parser.add_argument("-k", "--keepalive", default=False, action='store_true',
                        help="keep interactive session alive after exiting Jupyter")
    parser.add_argument("--kq", "--keepxquartz", dest="keepxquartz", default=False, action='store_true',
                        help="do not quit XQuartz")
    parser.add_argument("--force-getpass", dest="forcegetpass", action='store_true',
                        default=JRMT_DEFAULTS.get("FORCE_GETPASS"),
                        help="use getpass instead of pinentry for password entry")
    parser.add_argument('--no-browser', dest="no_browser", action='store_true',
                        help="run without opening the browser")
    parser.add_argument("-X", "--ForwardX11", dest="forwardx11", default=JRMT_DEFAULTS.get("FORWARD_X11"),
                        action='store_true',
                        help="enable X11 forwarding, equivalent to ssh -X")
    parser.add_argument("-Y", "--ForwardX11Trusted", dest="forwardx11trusted", default=False,
                        action='store_true',
                        help="enable trusted X11 forwarding, equivalent to ssh -Y")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="increase verbosity level")
    parser.add_argument('--version', action='store_true',
                        help="show the current version and exit")
    parser.add_argument('--paths', action='store_true',
                        help="show configuration paths and exit")
    parser.add_argument('--generate-config', action='store_true',
                        help="generate the default configuration file")
    return parser


class ConfigManager(object):
    def __init__(self):
        self.config = ConfigParser(defaults=JRMT_DEFAULTS_STR)
        self.config.add_section('Defaults')
        self.config.add_section('Settings')
        self.config.add_section('Remote Environment Settings')
        self.cfg_locations = self.config.read(CFG_SEARCH_LOCATIONS)

    def read_profile(self, profile):
        if profile:
            filename = CFG_FILENAME.split('.')[0] + "-" + profile + "." + CFG_FILENAME.split('.')[1]
            new_locations = self.config.read(_generate_search_locations(filename=filename))
            self.cfg_locations.extend(new_locations)
            return new_locations
        else:
            return None

    def get_arg_parser(self):
        """Get an arg parser populated with this ConfigManager's defaults."""
        parser = get_base_arg_parser()
        parser.set_defaults(
            user=self.config.get('Defaults', 'DEFAULT_USER'),
            host=self.config.get('Defaults', 'DEFAULT_HOST'),
            jp_port=self.config.getint('Defaults', 'DEFAULT_JP_PORT'),
            jp_time=self.config.get('Defaults', 'DEFAULT_JP_TIME'),
            jp_mem=self.config.get('Defaults', 'DEFAULT_JP_MEM'),
            jp_cores=self.config.getint('Defaults', 'DEFAULT_JP_CORES'),
            forcegetpass=self.config.getboolean('Settings', 'FORCE_GETPASS'),
            forwardx11=self.config.get('Remote Environment Settings', 'FORWARD_X11')
        )
        return parser
