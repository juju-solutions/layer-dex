from charms import layer
from charms.layer import snap
from charms.reactive import when
from charms.reactive import when_not
# from charms.reactive import set_state

from charmhelpers.core.hookenv import config


@when_not('snap.installed.lazy-dex')
def install_dex():
    opts = layer.options('dex')
    snap.install(opts['dex_snap'], channel=config('channel'))


@when('config.changed.channel')
def update_dex_channel():
    opts = layer.options('dex')
    snap.install(opts['dex_snap'], channel=config('channel'))
