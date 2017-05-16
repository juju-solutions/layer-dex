from charms import layer
from charms.layer import snap
from charms.reactive import hook
from charms.reactive import when
from charms.reactive import when_any
from charms.reactive import when_not
from charms.reactive import remove_state
from charms.reactive import set_state
from charms.templating.jinja2 import render

from charmhelpers.core import unitdata
from charmhelpers.core.hookenv import application_version_set
from charmhelpers.core.hookenv import config
from charmhelpers.core.hookenv import close_port
from charmhelpers.core.hookenv import local_unit
from charmhelpers.core.hookenv import log
from charmhelpers.core.hookenv import open_port
from charmhelpers.core.hookenv import status_set
from charmhelpers.core.hookenv import unit_get
from charmhelpers.core.hookenv import unit_public_ip
from charmhelpers.core.hookenv import unit_private_ip

from charmhelpers.core.host import service_restart

from lib.utilities import convert_dict_keys

from shlex import split
from subprocess import check_call
from subprocess import check_output
from subprocess import CalledProcessError

import os
import random
import socket
import string


@hook('stop')
def remove_dex():
    ''' Remove the snap and purge configuration files on the way out. '''
    opts = layer.options('dex')
    # This is ugly, but snap.remove resets the state. This will ensure we
    # clean up after ourseles on the way out.
    try:
        check_call(['snap', 'remove', opts['dex_snap']])
    except CalledProcessError:
        msg = "Unable to remove dex snap. Machine may be dirty on exit"
        log('WARNING', msg)


@when('certificates.server.cert.available')
def stop_object_proliferation(certs):
    set_state('dex.ssl.ready')


@hook('upgrade-charm')
def upgrade_charm():
    ''' Remove the snap installation state to trigger a refresh '''
    remove_state('snap.installed.lazy-dex')


@hook('update-status')
def update_status():
    ''' Invoke the health checks and do any additional status messaging. '''
    invoke_health_message()
    report_dex_version()


@when('dex.ssl.ready')
@when_not('snap.installed.lazy-dex')
def install_dex():
    ''' Install dex on first run '''
    opts = layer.options('dex')
    snap.install(opts['dex_snap'], channel=config('channel'))
    open_port(config('auth-port'))
    invoke_health_message()


@when('dex.ssl.ready')
@when('config.changed.channel')
def update_dex_channel():
    ''' React to channel changes and refresh the dex snap '''
    opts = layer.options('dex')
    snap.install(opts['dex_snap'], channel=config('channel'))
    invoke_health_message()


@when('config.changed.auth-port')
def cycle_ports():
    ''' Close the previous port and open the currently configured port. '''
    cfg = config()
    if cfg.previous('auth-port'):
        close_port(cfg.previous('auth-port'))
        open_port(config('auth-port'))


@when('config.changed.portal-port')
def cycle_portal():
    cfg = config()
    if cfg.previous('portal-port'):
        close_port(cfg.previous('portal-port'))
        open_port(config('portal-port'))
    # TODO: service_restart('dex-auth-portal')


@when('dex.ssl.ready')
@when_any('config.changed.auth-port', 'config.changed.github-client',
          'config.changed.github-secret', 'config.changed.google-client',
          'config.changed.google-secret', 'config.changed.expire-signing-keys',
          'config.changed.expire-id-tokens', 'config.changed.demo-mode',
          'config.changed.github-org', 'config.changed.portal-port')
def render_dex_template():
    ''' Re-render the dex service template and recycle the daemon to ingest the
    new config.'''

    config_path = os.path.join(os.path.sep, 'var', 'snap', 'lazy-dex',
                               'common', 'config.yaml')

    # clone the config  and layer options dict and prep the keys
    # for jinja templating
    context = convert_dict_keys(config())
    dex_opts = convert_dict_keys(layer.options('dex'))
    tls_opts = convert_dict_keys(layer.options('tls-client'))
    context.update({'issuer': unit_get('public-address'),
                    'portal_token': portal_token()})
    context.update(dex_opts)
    context.update(tls_opts)

    # instantiate a config object and pass it in as context
    render('config.yaml.jinja2', config_path, context)
    service_restart('snap.lazy-dex.daemon')
    remove_state('auth-portal.available')


@when_not('certificates.available')
def missing_relation_notice():
    status_set('blocked', 'Missing relation to certificate authority.')


@when('certificates.available')
@when_not('dex.ssl.requested')
def prepare_tls_certificates(tls):
    status_set('maintenance', 'Requesting tls certificates.')
    common_name = unit_public_ip()
    sans = []
    sans.append(unit_public_ip())
    sans.append(unit_private_ip())
    sans.append(socket.gethostname())
    certificate_name = local_unit().replace('/', '_')
    tls.request_server_cert(common_name, sans, certificate_name)
    set_state('dex.ssl.requested')


@when('snap.installed.lazy-dex')
@when_not('auth-portal.available')
def start_auth_portal():
    ''' Activate the authorization portal which enables the oauth workflow '''
    opts = layer.options('dex')
    arg_path = os.path.join(os.path.sep, 'var', 'snap', opts['dex_snap'],
                            'common', 'portal-args')

    issuer_uri = "https://{0}:{1}/dex".format(unit_get('public-address'),
                                              config('auth-port'))
    redirect_uri = "http://{0}:{1}/callback".format(unit_get('public-address'),
                                                    config('portal-port'))
    portal_args = {'issuer': issuer_uri,
                   'redirect-uri': redirect_uri,
                   'client-id': 'auth-portal',
                   'client-secret': portal_token(),
                   'listen': 'http://0.0.0.0:{}'.format(config('portal-port'))}
    log('Configuring auth portal args as {}'.format(arg_path), 'INFO')
    with open(arg_path, 'w+') as fp:
        for k in portal_args.keys():
            fp.write('--{0}={1} '.format(k, portal_args[k]))


@when('authorization.available', 'snap.installed.lazy-dex')
def provide_authorization_detail(auth):
    ''' Set configuration values for communicating with the authorization
    service. '''

    # client_id = portal_token()
    # groups_claim = config('github-org')
    issuer_uri = "https://{0}:{1}/dex".format(unit_get('private-address'),
                                              config('auth-port'))

    auth.configure('example-app', issuer_uri, 'groups', 'email')


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
        status_set('waiting', 'Error checking dex.')


def portal_token(size=32):
    ''' Generate a client token for client/server communication between dex
    and the authentication portal.

    param size - the length of the ascii token.'''
    db = unitdata.kv()
    if not db.get('portal-token'):
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
        token = ''.join(random.choice(chars) for _ in range(size))
        db.set('portal-token', token)
    return db.get('portal-token')


def report_dex_version():
    ''' Declare the version of dex installed via juju status '''
    # set the application version while we're here
    cmd = "/snap/bin/lazy-dex.dex version"
    try:
        raw_out = check_output(split(cmd))
    except FileNotFoundError:  # noqa
        # We haven't installed dex yet, dont break progression.
        return
    version = ''
    for line in raw_out.split(b'\n'):
        if b'dex' in line:
            version = line.split(b' ')[-1].replace(b'v', b'')
    application_version_set(version)
