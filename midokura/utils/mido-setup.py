# Ensure cirros 0.3.3 is the image in tempest
# Ensure that allow overlapping tenants is set to false?
# tempest.conf is configured properly, and tenants are clean

import os
import sys

sys.path.append(os.getcwd())

from simpleconfigparser import simpleconfigparser
from tempest import clients
from tempest import config
from tempest.common import cred_provider

CONF = config.CONF
image_ref = None
tenant = None

# Mandatory sections and keys for a minimal deployment tempest.conf
sections = {
    'identity': [
        'admin_username',
        'admin_password',
        'admin_tenant_name',
        'username',
        'password',
        'tenant_name',
        'uri',
        'uri_v3'],
    'compute-feature-enabled': [
        'live_migration'
    ]}


def main():
    config = read_tempest_conf()
    credentials = cred_provider.get_configured_credentials('identity_admin')
    manager = clients.Manager(credentials=credentials)
    check_image_ref(manager)
    fix_tempest_conf(manager, config)


def check_image_ref(manager):
    global image_ref
    # FIXME: workaround until we have tempest-add to always work on tempest master
    try:
        images = manager.image_client.image_list()
    except:
        images = manager.image_client.list_images()['images']

    image_checksum = '133eae9fb1c98f45894a4e60d8736619'
    matched_image = next((img for img in images
                          if img['checksum'] == image_checksum),
                         None)
    if matched_image:
        image_ref = matched_image['id']
    else:
        upload_image_ref(manager)


def upload_image_ref(manager):
    # create and image with cirros 0.3.3
    global image_ref
    kwargs = {
        'copy_from': 'http://download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img',
        'visibility': 'public',
        'is_public': True,
    }
    try:
        resp = manager.image_client.create_image(name='cirros 0.3.3',
                                                 container_format='bare',
                                                 disk_format='raw',
                                                 **kwargs)
    except Exception:
        raise SystemError("Cirros image not created")

    image_ref = resp['id']


def read_tempest_conf():
    default_path = "etc/tempest.conf"
    mido_path = "midokura/utils/tempest.conf.midokura"

    if not os.path.isfile(mido_path):
        raise IOError("No tempest.conf file in %s", mido_path)

    config = simpleconfigparser()
    config.read(default_path)

    for section, keys in sections.items():
        for key in keys:
            if not config.has_option(section, key):
                raise ValueError(
                    "Section " + section + " key " + key + " is missing.\n" +
                    "A minimal tempest.conf MUST specify:\n" +
                    str(sections))

    return config


def fix_tempest_conf(manager, config):
    default_path = "etc/tempest.conf"
    mido_path = "midokura/utils/tempest.conf.midokura"

    if not os.path.isfile(mido_path):
        raise IOError("No mido tempest.conf file in %s", mido_path)

    midoconfig = simpleconfigparser()
    midoconfig.read(mido_path)

    # get config params from deployment and set into midoconfig
    # TODO: no need for public_net_id, query it ourselves
    for section, keys in sections.items():
        for key in keys:
            value = config.get(section, key)
            midoconfig.set(section, key, value)

    # get neutron suported extensions
    extensions_dict = manager.network_client.list_extensions()
    extensions_unfiltered = [x['alias'] for x in extensions_dict['extensions']]
    # setup network extensions
    extensions = [x for x in extensions_unfiltered
                  if x not in ['lbaas', 'fwaas', 'lbaas_agent_scheduler']]
    to_string = ""
    for ex in extensions[:-1]:
        if ex != "lbaas" or ex != "fwaas" or ex != "lbaas_agent_scheduler":
            to_string = str.format("{0},{1}", ex, to_string)
    to_string = str.format("{0}{1}", to_string, extensions[-1])

    if CONF.network_feature_enabled.api_extensions != to_string:
        # modify tempest.conf file
        midoconfig.set('network-feature-enabled',
                       'api_extensions', to_string)

    # set up public_network_id
    try:
        networks = manager.network_client.list_networks(
            **{'router:external': True})
    except:
        networks = manager.networks_client.list_networks(
            **{'router:external': True})

    if len(networks['networks']) == 0:
        raise ValueError('No public networks available.')

    public_network_id = networks['networks'][0]['id']
    midoconfig.set('network', 'public_network_id', public_network_id)

    # set up image_ref
    if image_ref:
        midoconfig.set('compute', 'image_ref', image_ref)
        midoconfig.set('compute', 'image_ref_alt', image_ref)
    # set up flavor_ref
    # FIXME: workaround to make it work with tempest upstream
    try:
        flavors = manager.flavors_client.list_flavors_with_detail()
        flavors.sort(key=lambda x: x['ram'])
        min_flavor = flavors[0]
        min_ram = min_flavor['ram']
    except:
        flavors = manager.flavors_client.list_flavors()['flavors']
        min_ram = 1024000000
        min_flavor = None
        for flavor in flavors:
            current_ram = manager.flavors_client.show_flavor(
                flavor['id'])['flavor']['ram']
            if current_ram < min_ram:
                min_ram = current_ram
                min_flavor = flavor

    if min_ram > 64:
        print "WARNING: smallest flavor available is greater than 64 mb"
    midoconfig.set('compute', 'flavor_ref', min_flavor['id'])

    # Disable resize feature to disable those tests
    midoconfig.set('compute-feature-enabled', 'resize', 'false')

    with open(default_path, 'w') as tempest_conf:
        midoconfig.write(tempest_conf)

if __name__ == "__main__":
    main()
