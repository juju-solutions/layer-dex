from charms import layer
from charms.layer import snap
from charms.reactive import hook
from charms.reactive import when
from charms.reactive import when_any
from charms.reactive import when_not
# from charms.reactive import set_state
from charms.templating.jinja2 import render

from charmhelpers.core.hookenv import config
from charmhelpers.core.hookenv import close_port
from charmhelpers.core.hookenv import open_port
from charmhelpers.core.hookenv import status_set
from charmhelpers.core.hookenv import unit_get
from charmhelpers.core.host import service_restart

from lib.utilities import convert_dict_keys

from subprocess import check_call
from subprocess import CalledProcessError

import os


@hook('stop')
def remove_dex():
    ''' Remove the snap and purge configuration files on the way out '''
    opts = layer.options('dex')
    # This is ugly, but snap.remove resets the state. This will ensure we
    # clean up after ourseles on the way out.
    check_call(['snap', 'remove', opts['dex_snap']])


@hook('update-status')
def update_status():
    ''' Invoke the health checks and do any additional status messaging '''
    invoke_health_message()


@when_not('snap.installed.lazy-dex')
def install_dex():
    ''' Install dex on first run '''
    opts = layer.options('dex')
    snap.install(opts['dex_snap'], channel=config('channel'))
    open_port(config('auth-port'))
    invoke_health_message()


@when('config.changed.channel')
def update_dex_channel():
    ''' React to channel changes and refresh the dex snap '''
    opts = layer.options('dex')
    snap.install(opts['dex_snap'], channel=config('channel'))
    invoke_health_message()


# TODO: Make this actually reconfigure dex
@when('config.changed.auth-port')
def cycle_ports():
    ''' Close the previous port and open the currently configured port '''
    cfg = config()
    if cfg.previous('auth-port'):
        close_port(cfg.previous('auth-port'))
        open_port(config('auth-port'))


@when_any('config.changed.auth-port', 'config.changed.github-client',
          'config.changed.github-secret', 'config.changed.google-client',
          'config.changed.google-secret', 'config.changed.expire-signing-keys',
          'config.changed.expire-id-tokens', 'config.changed.demo-mode',
          'config.changed.github-org')
def render_dex_template():
    ''' Re-render the dex service template and recycle the daemon to ingest the
    new config.'''

    config_path = os.path.join(os.path.sep, 'var', 'snap', 'lazy-dex',
                               'common', 'config.yaml')

    # clone the config  and layer options dict and prep the keys
    # for jinja templating
    context = convert_dict_keys(config())
    opts = convert_dict_keys(layer.options('dex'))

    context.update({'issuer': unit_get('public-address')})
    context.update(opts)

    # instantiate a config object and pass it in as context
    render('config.yaml.jinja2', config_path, context)
    service_restart('snap.lazy-dex.daemon')


def invoke_health_message():
    ''' Basic probe of the daemon to report status in juju-status output '''
    cmd = ['systemctl', 'is-active', 'snap.lazy-dex.daemon']
    try:
        return_code = check_call(cmd)
    except CalledProcessError:
        return_code = 1

    if return_code < 1:
        status_set('active', 'Dex is active.')
    else:
        status_set('error', 'Error checking dex.')
