#!/usr/bin/python
# -*- coding: UTF-8 -*-
import configparser
from common import utilities
from common.utilities import ServiceInfo
from service.key_center_service import KeyCenterService
import json
import os
import uuid


class ServiceConfigGenerator:
    def __init__(self, config, service_type, node_type):
        self.config = config
        self.ini_file = "config.ini"
        self.network_file = "nodes.json"
        self.service_type = service_type
        self.root_dir = "generated/" + self.service_type
        self.node_type = node_type

    def generate_all_config(self):
        if self.service_type == ServiceInfo.gateway_service_type:
            return self.generate_gateway_config_files()
        else:
            return self.generate_rpc_config_files()

    def generate_rpc_config_files(self):
        utilities.log_info("* generate config for the rpc service")
        section = "rpc"
        for rpc_service in self.config.rpc_service_list.keys():
            rpc_service_config = self.config.rpc_service_list[rpc_service]
            if self.__generate_config_files(section, rpc_service_config) is False:
                return False
        utilities.log_info("* generate config for the rpc service success")
        return True

    def generate_gateway_config_files(self):
        utilities.log_info("* generate config for the gateway service")
        section = "p2p"
        for gateway_service in self.config.gateway_service_list.keys():
            gateway_service_config = self.config.gateway_service_list[gateway_service]
            if self.__generate_config_files(section, gateway_service_config) is False:
                return False
            if self.__generate_gateway_connection_info_for_all_deploy_ip(gateway_service_config) is False:
                return False
        utilities.log_info("* generate config for the gateway service success")
        return True

    def __get_cert_config_file_list(self, service_config, ip):
        cert_config_file_list = []
        if service_config.sm_ssl is False:
            cert_config_file_list = ["ca.crt", "ssl.crt", "ssl.key"]
        else:
            cert_config_file_list = [
                "sm_ca.crt", "sm_ssl.crt", "sm_ssl.key", "sm_enssl.crt", "sm_enssl.key"]
        cert_config_path_list = []
        path = self.__get_service_config_base_path(service_config, ip)
        for cert in cert_config_file_list:
            cert_config_path_list.append(os.path.join(path, "ssl", cert))
        return (cert_config_file_list, cert_config_path_list)

    def __get_config_file_info(self, config_file_list, service_config, ip):
        path = self.__get_service_config_base_path(service_config, ip)
        (cert_file_list, cert_file_path_list) = self.__get_cert_config_file_list(
            service_config, ip)
        config_path_list = []
        for config_file in config_file_list:
            config_path_list.append(os.path.join(path, config_file))
        return (config_file_list + cert_file_list, config_path_list + cert_file_path_list)

    def get_config_file_list(self, service_config, ip):
        if service_config.service_type == utilities.ServiceInfo.rpc_service_type:
            return self.__get_config_file_info(["config.ini"], service_config, ip)
        else:
            return self.__get_config_file_info(["config.ini", "nodes.json"], service_config, ip)

    def __generate_config_files(self, section, service_config):
        utilities.print_badage(
            "* generate config for the %s service %s" % (section, service_config.name))
        utilities.log_info("* generate %s for the %s service %s" %
                           (self.ini_file, section, service_config.name))
        if self.__generate_and_store_ini_config(service_config, section) is False:
            return False
        utilities.log_info("* generate %s for the %s service %s success" %
                           (self.ini_file, section, service_config.name))
        utilities.log_info("* generate cert for the %s service %s" %
                           (section, service_config.name))
        if self.__generate_cert_for_all_deploy_ip(service_config) is False:
            return False
        utilities.log_info(
            "* generate cert for the %s service %s success" % (section, service_config.name))
        utilities.print_badage(
            "* generate config for the %s service success%s" % (section, service_config.name))
        return True

    def __generate_and_store_ini_config(self, service_config, section):
        """
        generate and store ini config
        """
        ini_config_content = self.__generate_ini_config(
            service_config, section)
        if self.__store_config_file(service_config, ini_config_content) is False:
            return False
        return True

    def __generate_ini_config(self, service_config, section):
        """
        generate config.ini.tmp
        """
        ini_config = configparser.ConfigParser(
            comment_prefixes='/', allow_no_value=True)
        ini_config.read(service_config.tpl_config_file)
        ini_config[section]['listen_ip'] = service_config.listen_ip
        ini_config[section]['listen_port'] = str(service_config.listen_port)
        ini_config[section]['sm_ssl'] = utilities.convert_bool_to_str(
            service_config.sm_ssl)
        ini_config[section]['thread_count'] = str(
            service_config.thread_count)
        ini_config["service"]['gateway'] = service_config.agency_config.chain_id + \
            "." + service_config.agency_config.gateway_service_name
        ini_config["service"]['rpc'] = service_config.agency_config.chain_id + \
            "." + service_config.agency_config.rpc_service_name
        ini_config["chain"]['chain_id'] = service_config.agency_config.chain_id
        # generate failover config
        failover_section = "failover"
        if self.node_type == "max":
            ini_config[failover_section]["enable"] = utilities.convert_bool_to_str(
                True)
        else:
            ini_config[failover_section]["enable"] = utilities.convert_bool_to_str(
                False)
        ini_config[failover_section]["cluster_url"] = service_config.agency_config.failover_cluster_url

        # generate uuid according to chain_id and gateway_service_name
        uuid_name = ini_config["service"]['gateway']
        ini_config[section]['uuid'] = str(
            uuid.uuid3(uuid.NAMESPACE_URL, uuid_name))
        self.__update_storage_security_info(ini_config, service_config)
        return ini_config

    def __update_storage_security_info(self, ini_config, service_config):
        """
        update the storage_security for config.ini
        """
        # TODO: access key_center to encrypt the certificates and the private keys
        section = "storage_security"
        ini_config[section]["enable"] = utilities.convert_bool_to_str(
            service_config.agency_config.enable_storage_security)
        ini_config["chain"]["sm_crypto"] = utilities.convert_bool_to_str(
            service_config.sm_ssl)
        ini_config[section]["key_center_url"] = service_config.agency_config.key_center_url
        ini_config[section]["cipher_data_key"] = service_config.agency_config.cipher_data_key

    def __store_config_file(self, service_config, ini_config_content):
        for ip in service_config.deploy_ip_list:
            path = self.__get_service_config_base_path(service_config, ip)
            ini_path = os.path.join(path, self.ini_file)
            if os.path.exists(ini_path) is True:
                utilities.log_error(
                    "config file %s already exists, please delete after confirming carefully" % ini_path)
                return False
            utilities.mkfiledir(ini_path)
            with open(ini_path, 'w') as configfile:
                ini_config_content.write(configfile)
            utilities.log_info("* generate %s" % ini_path)
        return True

    def __get_service_config_base_path(self, service_config, deploy_ip):
        config_path = os.path.join(
            self.root_dir, service_config.agency_config.chain_id, service_config.name, deploy_ip)
        return config_path

    def __generate_cert_for_all_deploy_ip(self, service_config):
        for ip in service_config.deploy_ip_list:
            self.__generate_cert(service_config, ip)

    def __generate_cert(self, service_config, deploy_ip):
        output_dir = self.__get_service_config_base_path(
            service_config, deploy_ip)
        if self.__ca_generated(service_config) is False:
            # generate the ca cert
            utilities.generate_ca_cert(
                service_config.sm_ssl, service_config.ca_cert_path)
        utilities.log_info(
            "* generate cert, ip: %s, output path: %s" % (deploy_ip, output_dir))
        utilities.generate_node_cert(
            service_config.sm_ssl, service_config.ca_cert_path, output_dir)
        if service_config.agency_config.enable_storage_security is True:
            key_center = KeyCenterService(
                service_config.agency_config.key_center_url, service_config.agency_config.cipher_data_key)
            if service_config.sm_ssl is True:
                ret = key_center.encrypt_file(
                    os.path.join(output_dir, "ssl", "sm_ssl.key"))
                if ret is False:
                    return False
                ret = key_center.encrypt_file(
                    os.path.join(output_dir, "ssl", "sm_enssl.key"))
                if ret is False:
                    return False
            else:
                ret = key_center.encrypt_file(
                    os.path.join(output_dir, "ssl", "ssl.key"))
                if ret is False:
                    return False
        if service_config.service_type == ServiceInfo.rpc_service_type:
            utilities.log_info(
                "* generate sdk cert, output path: %s" % (output_dir))
            utilities.generate_sdk_cert(
                service_config.sm_ssl, service_config.ca_cert_path, output_dir)
        return True

    def __generate_gateway_connection_info_for_all_deploy_ip(self, service_config):
        for ip in service_config.deploy_ip_list:
            if self.__generate_gateway_connection_info(service_config, ip) is False:
                return False
        return True

    def __generate_gateway_connection_info(self, service_config, ip):
        path = self.__get_service_config_base_path(service_config, ip)
        network_file_path = os.path.join(path, self.network_file)
        if os.path.exists(network_file_path):
            utilities.log_error(
                "config file %s already exists, please delete after confirming carefully" % network_file_path)
            return False
        peers = {}
        peers["nodes"] = service_config.peers
        utilities.mkfiledir(network_file_path)
        with open(network_file_path, 'w') as configfile:
            json.dump(peers, configfile)
        utilities.log_info(
            "* generate gateway connection file: %s" % network_file_path)
        return True

    def __ca_generated(self, service_config):
        if service_config.sm_ssl is False:
            if os.path.exists(os.path.join(service_config.ca_cert_path, "ca.crt")) and os.path.exists(os.path.join(service_config.ca_cert_path, "ca.key")):
                return True
        else:
            if os.path.exists(os.path.join(service_config.ca_cert_path, "sm_ca.crt")) and os.path.exists(os.path.join(service_config.ca_cert_path, "sm_ca.key")):
                return True
        return False
