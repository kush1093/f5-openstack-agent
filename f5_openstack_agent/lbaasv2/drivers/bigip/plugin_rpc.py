"""RPC API for calls back to the plugin."""
# Copyright 2016 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from keystoneauth1 import identity
from keystoneauth1 import session

from neutron.extensions import portbindings
from neutron_lib import constants as neutron_const

from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
import oslo_messaging as messaging

from neutron.common import rpc
from neutron.plugins.common import constants as plugin_constants
from neutronclient.v2_0 import client

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as constants

LOG = logging.getLogger(__name__)

opt_group = cfg.OptGroup(name='keystone_authtoken')
OPTS = [cfg.StrOpt('username', default='neutron',
                        help=('username')),
             cfg.StrOpt('password',
                        default='changeme',
                        help=('password')),
             cfg.StrOpt('project_name',
                        default='services',
                        help=('project_name')),
             cfg.StrOpt('project_domain_name',
                        default='Default',
                        help=('project_domain_name')),
             cfg.StrOpt('user_domain_name',
                        default='Default',
                        help=('user_domain_name')),
             cfg.StrOpt('auth_url',
                        default='http://172.16.1.3:35357',
                        help=('auth_url'))]

class LBaaSv2PluginRPC(object):
    """Client interface for agent to plugin RPC."""

    RPC_API_NAMESPACE = None

    def __init__(self, topic, context, env, group, host, conf):
        """Initialize LBaaSv2PluginRPC."""
        super(LBaaSv2PluginRPC, self).__init__()

        if topic:
            self.topic = topic
        else:
            self.topic = constants.TOPIC_PROCESS_ON_HOST_V2

        self.target = messaging.Target(topic=self.topic,
                                       version=constants.RPC_API_VERSION)
        self._client = rpc.get_client(self.target, version_cap=None)

        self.context = context
        self.env = env
        self.group = group
        self.host = host
        self.rest = LbaaSv2pluginREST_CLASS(conf)

    def _make_msg(self, method, **kwargs):
        return {'method': method,
                'namespace': self.RPC_API_NAMESPACE,
                'args': kwargs}

    def _call(self, context, msg, **kwargs):
        return self.__call_rpc_method(context,
                                      msg,
                                      rpc_method='call',
                                      **kwargs)

    def _cast(self, context, msg, **kwargs):
        self.__call_rpc_method(context,
                               msg,
                               rpc_method='cast',
                               **kwargs)

    def _fanout_cast(self, context, msg, **kwargs):
        kwargs['fanout'] = True
        self.__call_rpc_method(context, msg, rpc_method='cast', **kwargs)

    def __call_rpc_method(self, context, msg, **kwargs):
        options = dict(
            ((opt, kwargs[opt])
             for opt in ('fanout', 'timeout', 'topic', 'version')
             if kwargs.get(opt))
        )
        if msg['namespace']:
            options['namespace'] = msg['namespace']

        if options:
            callee = self._client.prepare(**options)
        else:
            callee = self._client

        func = getattr(callee, kwargs['rpc_method'])
        return func(context, msg['method'], **msg['args'])

    @log_helpers.log_method_call
    def update_loadbalancer_status(self,
                                   lb_id,
                                   provisioning_status=None,
                                   operating_status=None):
        """Update the database with loadbalancer status."""
        return self._cast(
            self.context,
            self._make_msg('update_loadbalancer_status',
                           loadbalancer_id=lb_id,
                           status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_loadbalancer_stats(self,
                                  lb_id,
                                  stats):
        """Update the database with loadbalancer stats."""
        # return self.rest.update_loadbalancer_stats(lb_id, stats)
        return self._cast(
            self.context,
            self._make_msg('update_loadbalancer_stats',
                           loadbalancer_id=lb_id,
                           stats=stats),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def loadbalancer_destroyed(self, loadbalancer_id):
        """Delete the loadbalancer from the database."""
        return self._cast(
            self.context,
            self._make_msg('loadbalancer_destroyed',
                           loadbalancer_id=loadbalancer_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_listener_status(self,
                               listener_id,
                               provisioning_status=constants.F5_ERROR,
                               operating_status=constants.F5_OFFLINE):
        """Update the database with listener status."""
        return self._cast(
            self.context,
            self._make_msg('update_listener_status',
                           listener_id=listener_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def listener_destroyed(self, listener_id):
        """Delete listener from database."""
        return self._cast(
            self.context,
            self._make_msg('listener_destroyed',
                           listener_id=listener_id),
            topic=self.topic
        )
        # return self.rest.listener_destroyed(listener_id)

    @log_helpers.log_method_call
    def update_pool_status(self,
                           pool_id,
                           provisioning_status=constants.F5_ERROR,
                           operating_status=constants.F5_OFFLINE):
        """Update the database with pool status."""
        return self._cast(
            self.context,
            self._make_msg('update_pool_status',
                           pool_id=pool_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def pool_destroyed(self, pool_id):
        """Delete pool from database."""
        return self._cast(
            self.context,
            self._make_msg('pool_destroyed',
                           pool_id=pool_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_member_status(self,
                             member_id,
                             provisioning_status=None,
                             operating_status=None):
        """Update the database with member status."""
        return self._cast(
            self.context,
            self._make_msg('update_member_status',
                           member_id=member_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def member_destroyed(self, member_id):
        """Delete member from database."""
        return self._cast(
            self.context,
            self._make_msg('member_destroyed',
                           member_id=member_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_health_monitor_status(
            self,
            health_monitor_id,
            provisioning_status=constants.F5_ERROR,
            operating_status=constants.F5_OFFLINE):
        """Update the database with health_monitor status."""
        return self._cast(
            self.context,
            self._make_msg('update_health_monitor_status',
                           health_monitor_id=health_monitor_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def health_monitor_destroyed(self, healthmonitor_id):
        """Delete health_monitor from database."""
        return self._cast(
            self.context,
            self._make_msg('healthmonitor_destroyed',
                           healthmonitor_id=healthmonitor_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_l7rule_status(
            self,
            l7rule_id,
            l7policy_id,
            provisioning_status=constants.F5_ERROR,
            operating_status=constants.F5_OFFLINE):
        return self._cast(
            self.context,
            self._make_msg('update_l7rule_status',
                           l7rule_id=l7rule_id,
                           l7policy_id=l7policy_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def l7rule_destroyed(self, l7rule_id):
        """Delete health_monitor from database."""
        return self._cast(
            self.context,
            self._make_msg('l7rule_destroyed',
                           l7rule_id=l7rule_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_l7policy_status(
            self,
            l7policy_id,
            provisioning_status=constants.F5_ERROR,
            operating_status=constants.F5_OFFLINE):
        return self._cast(
            self.context,
            self._make_msg('update_l7policy_status',
                           l7policy_id=l7policy_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def l7policy_destroyed(self, l7policy_id):
        return self._cast(
            self.context,
            self._make_msg('l7policy_destroyed',
                           l7policy_id=l7policy_id),
            topic=self.topic
        )

    # for L3 binding
    @log_helpers.log_method_call
    def add_allowed_address(self, port_id=None, ip_address=None):
        """Add allowed address to the port."""
        return self._call(
            self.context,
            self._make_msg('add_allowed_address',
                           port_id=port_id,
                           ip_address=ip_address),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def remove_allowed_address(self, port_id=None, ip_address=None):
        """Remove allowed address on the port."""
        return self._call(
            self.context,
            self._make_msg('remove_allowed_address',
                           port_id=port_id,
                           ip_address=ip_address),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def get_ports_for_mac_addresses(self, mac_addresses=None):
        """Get a list of ports that correspond to the mac addrs."""
        # return self.rest.get_ports_for_mac_addresses(mac_addresses)
        try:
            ports = self._call(
                self.context,
                self._make_msg('get_ports_for_mac_addresses',
                               mac_addresses=mac_addresses),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_ports_for_mac_addresses")

        return ports

    @log_helpers.log_method_call
    def get_ports_on_network(self, network_id=None):
        """Get a list of ports on the network."""
        # return self.rest.get_ports_on_network(network_id)
        return self._call(
            self.context,
            self._make_msg('get_ports_on_network',
                           network_id=network_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def get_port_by_name(self, port_name=None):
        """Get a list of ports that have the name port_name."""
        # return self.rest.get_port_by_name(port_name)
        try:
            ports = self._call(
                self.context,
                self._make_msg('get_port_by_name',
                               port_name=port_name),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_port_by_name")

        return ports

    @log_helpers.log_method_call
    def create_port_on_subnet(self, subnet_id=None,
                              mac_address=None, name=None,
                              fixed_address_count=1,
                              device_id=None,
                              vnic_type="normal",
                              binding_profile={}):
        """Add a neutron port to the subnet."""
        return self.rest.create_port_on_subnet(subnet_id=subnet_id,
                               mac_address=mac_address,
                               name=name,
                               fixed_address_count=fixed_address_count,
                               host=self.host,
                               device_id=device_id,
                               vnic_type=vnic_type,
                               binding_profile=binding_profile)
        """try:
            port = self._call(
                self.context,
                self._make_msg('create_port_on_subnet',
                               subnet_id=subnet_id,
                               mac_address=mac_address,
                               name=name,
                               fixed_address_count=fixed_address_count,
                               host=self.host,
                               device_id=device_id,
                               vnic_type=vnic_type,
                               binding_profile=binding_profile),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: "
                      "create_port_on_subnet")

        return port"""

    @log_helpers.log_method_call
    def create_port_on_network(self, network_id=None, mac_address=None,
                               name=None, host=None,
                               device_id=None,
                               vnic_type="normal",
                               binding_profile={}):
        """Add a neutron port to the network."""
        """return self.rest.create_port_on_network(network_id=network_id,
                               mac_address=mac_address,
                               name=name,
                               host=self.host,
                               device_id=device_id,
                               vnic_type=vnic_type,
                               binding_profile=binding_profile)"""
        try:
            port = self._call(
                self.context,
                self._make_msg('create_port_on_network',
                               network_id=network_id,
                               mac_address=mac_address,
                               name=name,
                               host=self.host,
                               device_id=device_id,
                               vnic_type=vnic_type,
                               binding_profile=binding_profile),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: "
                      "create_port_on_subnet_with_specific_ip")

        return port

    @log_helpers.log_method_call
    def delete_port_by_name(self, port_name=None):
        """Delete ports with the given name."""
        return self.rest.delete_port_by_name(port_name)
        """try:
	    LOG.debug("REST_CLASS:blabla")
            return self._cast(
                self.context,
                self._make_msg('delete_port_by_name',
                               port_name=port_name),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: "
                      "delet_port_by_name")"""

    @log_helpers.log_method_call
    def delete_port(self, port_id=None, mac_address=None):
        """Delete port with the given port_id."""
        # return self.rest.delete_port(port_id, mac_address)
        return self._cast(
            self.context,
            self._make_msg('delete_port',
                           port_id=port_id,
                           mac_address=mac_address),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def get_service_by_loadbalancer_id(self,
                                       loadbalancer_id=None):
        """Retrieve the service definition for this loadbalancer."""
        service = {}
        try:
            service = self._call(
                self.context,
                self._make_msg('get_service_by_loadbalancer_id',
                               loadbalancer_id=loadbalancer_id,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_service_by_loadbalancer_id")

        return service

    @log_helpers.log_method_call
    def get_all_loadbalancers(self, env=None, group=None, host=None):
        """Retrieve a list of loadbalancers in Neutron."""
        loadbalancers = []

        if not env:
            env = self.env

        try:
            loadbalancers = self._call(
                self.context,
                self._make_msg('get_all_loadbalancers',
                               env=env,
                               group=group,
                               host=host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_all_loadbalancers")

        return loadbalancers

    @log_helpers.log_method_call
    def get_active_loadbalancers(self, env=None, group=None, host=None):
        """Retrieve a list of active loadbalancers for this agent."""
        loadbalancers = []

        if not env:
            env = self.env

        try:
            loadbalancers = self._call(
                self.context,
                self._make_msg('get_active_loadbalancers',
                               env=env,
                               group=group,
                               host=host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_active_loadbalancers")

        return loadbalancers

    @log_helpers.log_method_call
    def get_pending_loadbalancers(self, env=None, group=None, host=None):
        """Retrieve a list of pending loadbalancers for this agent."""
        loadbalancers = []

        if not env:
            env = self.env

        try:
            loadbalancers = self._call(
                self.context,
                self._make_msg('get_pending_loadbalancers',
                               env=env,
                               group=group,
                               host=host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_pending_loadbalancers")

        return loadbalancers

    @log_helpers.log_method_call
    def get_errored_loadbalancers(self, env=None, group=None, host=None):
        """Retrieve a list of errored loadbalancers for this agent."""
        loadbalancers = []

        if not env:
            env = self.env

        try:
            loadbalancers = self._call(
                self.context,
                self._make_msg('get_pending_loadbalancers',
                               env=env,
                               group=group,
                               host=host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_errored_loadbalancers")

        return loadbalancers

    @log_helpers.log_method_call
    def get_loadbalancers_by_network(self, network_id, env=None, group=None,
                                     host=None):
        """Retrieve tuple(list) of loadbalancers by network_id

        This object method will attempt to return the list of loadbalancers
        associated with the provided network_id that match to also provided
        env, group, and host.

        Args:
            <network_id> := Str(the network_id)
        Optional KWArgs:
            <env=env>:= API-defined env
            <group=group>:= API-defined group
            <host=host>:= API-defined host
        Returns:
            <loadbalancers>:= tuple([discovered loadbalancers])
        """
        env = env if env else self.env
        group = group if group else self.group
        host = host if host else self.host
        loadbalancers = []
        try:
            loadbalancers = self._call(
                self.context,
                self._make_msg('get_loadbalancers_by_network', env=env,
                               network_id=network_id, group=group, host=host),
                topic=self.topic)
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_loadbalancers_by_network")
        # not always assured an empty list...
        return tuple(loadbalancers) if loadbalancers else tuple()

    @log_helpers.log_method_call
    def set_agent_admin_state(self, admin_state_up):
        """Set the admin_state_up of for this agent"""
        succeeded = False
        try:
            succeeded = self._call(
                self.context,
                self._make_msg('set_agent_admin_state',
                               admin_state_up=admin_state_up,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "set_agent_admin_state")

        return succeeded

    @log_helpers.log_method_call
    def scrub_dead_agents(self, env, group):
        """Set the admin_state_up of for this agent"""
        service = {}
        try:
            service = self._call(
                self.context,
                self._make_msg('scrub_dead_agents',
                               env=env,
                               group=group,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "scrub_dead_agents")

        return service

    @log_helpers.log_method_call
    def get_clusterwide_agent(self, env, group):
        """Determin which agent performce global tasks for the cluster"""
        agent = {}
        try:
            agent = self._call(
                self.context,
                self._make_msg('get_clusterwide_agent',
                               env=env,
                               group=group,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "scrub_dead_agents")

        return agent

    @log_helpers.log_method_call
    def validate_loadbalancers_state(self, loadbalancers):
        """Get the status of a list of loadbalancers IDs in Neutron"""
        lb_status = {}
        try:
            lb_status = self._call(
                self.context,
                self._make_msg('validate_loadbalancers_state',
                               loadbalancers=loadbalancers,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "validate_loadbalancers_state")

        return lb_status

    @log_helpers.log_method_call
    def validate_listeners_state(self, listeners):
        """Get the status of a list of listener IDs in Neutron"""
        listener_status = {}
        try:
            listener_status = self._call(
                self.context,
                self._make_msg('validate_listeners_state',
                               listeners=listeners,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "validate_pool_state")

        return listener_status

    @log_helpers.log_method_call
    def validate_pools_state(self, pools):
        """Get the status of a list of pools IDs in Neutron"""
        pool_status = {}
        try:
            pool_status = self._call(
                self.context,
                self._make_msg('validate_pools_state',
                               pools=pools,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "validate_pool_state")

        return pool_status

    @log_helpers.log_method_call
    def get_pools_members(self, pools):
        """Get the members of a list of pools IDs in Neutron."""
        pools_members = {}
        try:
            pools_members = self._call(
                self.context,
                self._make_msg('get_pools_members',
                               pools=pools,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_pools_members")

        return pools_members

    @log_helpers.log_method_call
    def validate_l7policys_state_by_listener(self, listeners):
        """Get the status of a list of l7policys IDs in Neutron"""
        l7policy_status = {}
        try:
            l7policy_status = self._call(
                self.context,
                self._make_msg('validate_l7policys_state_by_listener',
                               listeners=listeners),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "validate_l7policys_state_by_listener")

        return l7policy_status


class LbaaSv2pluginREST_CLASS(object):
    def __init__(self, conf):
	CONF = conf
	CONF.register_group(opt_group)
	CONF.register_opts(OPTS, opt_group)
        self.aut = identity.Password(auth_url=
                                     CONF.keystone_authtoken.auth_url,
                                     username=
                                     CONF.keystone_authtoken.username,
                                     password=
                                     CONF.keystone_authtoken.password,
                                     project_name=
                                     CONF.keystone_authtoken.project_name,
                                     project_domain_name=
                                     CONF.keystone_authtoken.project_domain_name,
                                     user_domain_name=
                                     CONF.keystone_authtoken.user_domain_name)
        self.sess = session.Session(auth=self.aut)
        self.neutron = client.Client(session=self.sess)
        self.cluster_wide_agents = {}
        LOG.debug("REST_CLASS:self.user_domain_name %(user_domain_name)s",
                  {'user_domain_name':CONF.keystone_authtoken.user_domain_name})
        LOG.debug("REST_CLASS:self.project_domain_name %(project_domain_name)s",
                  {'project_domain_name':CONF.keystone_authtoken.project_domain_name})
        LOG.debug("REST_CLASS:self.project_name %(project_name)s",
                  {'project_name':CONF.keystone_authtoken.project_name})
        LOG.debug("REST_CLASS:self.password %(password)s",
                  {'password':CONF.keystone_authtoken.password})
        LOG.debug("REST_CLASS:self.username %(username)s",
                  {'username':CONF.keystone_authtoken.username})
	LOG.debug("REST_CLASS:self.neutron %(neutron)s",
                  {'neutron':self.neutron})
        LOG.debug("REST_CLASS:self.neutron %(auth_url)s",
                  {'auth_url':CONF.keystone_authtoken.auth_url})

    def get_ports_for_mac_addresses(self, mac_addresses=None):
        ports = []
        try:
            if not isinstance(mac_addresses, list):
                mac_addresses = [mac_addresses]
            filters = {'mac_address': mac_addresses}
            ports = self.neutron.list_ports(
                filters=filters
            )
        except Exception as e:
            LOG.error("Exception: get_ports_for_mac_addresses: %s",
                      e.message)

        return ports

    def get_ports_on_network(self, network_id=None):
        """Get ports for network."""
        ports = []
        try:
            if not isinstance(network_id, list):
                network_ids = [network_id]
            filters = {'network_id': network_ids}
            ports = self.neutron.list_ports(
                filters=filters
            )
	    LOG.debug("REST_CLASS:success")
        except Exception as e:
            LOG.error("Exception: get_ports_on_network: %s", e.message)
    
        return ports

    def get_port_by_name(self, port_name=None): # doesn't work
        """Get port by name."""
        if port_name:
            filters = {'name': [port_name]}
            LOG.debug("REST_CLASS:port %(filters)s",
                  {'filters':filters})
            return self.neutron.list_ports(
                filters=filters)

    def delete_port(self, port_id=None, mac_address=None): #not sure
        """Delete port."""
        if port_id:
            self.neutron.delete_port(port_id)
        elif mac_address:
            filters = {'mac_address': [mac_address]}
            ports = self.neutron.list_ports(
                filters=filters
            )
            for port in ports:
                self.neutron.delete_port(
                    port['id']
                )

    def delete_port_by_name(self, port_name=None): #used to delete lbaas-ports; doesn't work
        """Delete port by name."""
        if port_name:
            filters = {'name': [port_name]}
            try:
                ports = self.neutron.list_ports(
                    filters=filters
                )
                """for port in ports:
                    self.neutron.delete_port( #deleted lb but not the port associated with it. "failed to delete port: string indices must be integers, not str"
                        port['id']
                    )"""
	        for key,val in ports.iteritems():
                    for v in val:
                        if 'id' in v:
                            self.neutron.delete_port(v['id'])
	        """JSON RESPONSE: Error message: {"NeutronError": {"message": "Port 322b6ffa-19f6-4944-8f3d-9048129bc7fe cannot be deleted directly via the port API: has device owner network:router_gateway.", "type": "ServicePortInUse", "detail": ""}}
                LOG ERROR: failed to delete port: Port 322b6ffa-19f6-4944-8f3d-9048129bc7fe cannot be deleted directly via the port API: has device owner network:router_gateway"""
            except Exception as e:
                LOG.error("failed to delete port: %s", e.message)

    def create_port_on_subnet(self, subnet_id=None,
                              mac_address=None, name=None,
                              fixed_address_count=1, host=None,
                              device_id=None,
                              vnic_type=portbindings.VNIC_NORMAL,
                              binding_profile={}):
        """Create port on subnet."""
        port = None
        if subnet_id:
            try:
                subnet = self.neutron.show_subnet(
                    subnet_id
                )
                if not mac_address:
                    mac_address = neutron_const.ATTR_NOT_SPECIFIED
                fixed_ip = {'subnet_id': subnet['subnet']['id']} 
                if fixed_address_count > 1:
                    fixed_ips = []
                    for _ in range(0, fixed_address_count):
                        fixed_ips.append(fixed_ip)
                else:
                    fixed_ips = [fixed_ip]
                if not host:
                    host = ''
                if not name:
                    name = ''

                port_data = {
                    'tenant_id': subnet['subnet']['tenant_id'],
                    'name': name,
                    'network_id': subnet['subnet']['network_id'],
                    'admin_state_up': True,
                    'device_owner': 'network:f5lbaasv2',
                    # 'status': neutron_const.PORT_STATUS_ACTIVE,
                    'fixed_ips': fixed_ips
                }
                if device_id:
                    port_data['device_id'] = device_id
                port_data[portbindings.HOST_ID] = host
                port_data[portbindings.VNIC_TYPE] = vnic_type
                port_data[portbindings.PROFILE] = binding_profile
                port = self.neutron.create_port(
                    {'port': port_data})
                # Because ML2 marks ports DOWN by default on creation
                update_data = {
                    'status': neutron_const.PORT_STATUS_ACTIVE
                }
                # self.neutron.update_port(
                #     port['port']['id'], {'port': update_data}) # Exception: create_port_on_subnet: Cannot update read-only attribute status
		self.neutron.update_port(
                    port['port']['id'], {'port':{'status':''}}) # Exception: create_port_on_subnet: Cannot update read-only attribute status
            except Exception as e:
                LOG.error("Exception: create_port_on_subnet: %s",
                          e.message)

        return port

    def create_port_on_network(self, network_id=None,
                               mac_address=None, name=None, host=None,
                               device_id=None,
                               vnic_type=portbindings.VNIC_NORMAL,
                               binding_profile={}):
        """Create a port on a network."""
        LOG.debug("inside of create_port_on_network")
        ports = []
        if network_id and name:
            filters = {'name': [name]}
            ports = self.neutron.list_ports(
                filters=filters
            )

        if not ports:
            network = self.neutron.show_network(
                network_id
            )

            if not mac_address:
                mac_address = neutron_const.ATTR_NOT_SPECIFIED
            if not host:
                host = ''
            if not name:
                name = ''

            port_data = {
                'tenant_id': network['tenant_id'],
                'name': name,
                'network_id': network_id,
                'mac_address': mac_address,
                'admin_state_up': True,
                'device_owner': 'network:f5lbaasv2',
                'status': neutron_const.PORT_STATUS_ACTIVE,
                'fixed_ips': neutron_const.ATTR_NOT_SPECIFIED
            }
            if device_id:
                port_data['device_id'] = device_id
            port_data[portbindings.HOST_ID] = host
            port_data[portbindings.VNIC_TYPE] = vnic_type
            port_data[portbindings.PROFILE] = binding_profile

            port = self.neutron.create_port(
                {'port': port_data})
            # Because ML2 marks ports DOWN by default on creation
            update_data = {
                'status': neutron_const.PORT_STATUS_ACTIVE
            }
            self.neutron.update_port(
                port['id'], {'port': update_data})
            return port

        else:
            return ports[0]
