#!/usr/bin/python
# -*- coding: UTF-8 -*-
from common import utilities
from common.utilities import CommandInfo
from argparse import RawTextHelpFormatter
import argparse
import sys
from common.utilities import ServiceInfo
import toml
import os
from config.chain_config import ChainConfig
from controller.binary_controller import BinaryController
from command.service_command_impl import ServiceCommandImpl
from command.node_command_impl import NodeCommandImpl
from command.monitor_command_impl import MonitorCommandImpl
from networkmgr.network_manager import NetworkManager


class _HelpAction(argparse._HelpAction):
    def __call__(self, parser, namespace, values, option_string=None):
        # retrieve subparsers from parser
        subparsers_actions = [
            action for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)]
        # there will probably only be one subparser_action,
        # but better save than sorry
        for subparsers_action in subparsers_actions:
            # get all subparsers and print help
            for choice, subparser in subparsers_action.choices.items():
                help_info = "help for subcommand '{}'".format(choice)
                print("----------- %s -----------" % help_info)
                print(subparser.format_help())
        parser.exit()


def get_description_prefix(subparser_name, command, service_type):
    return "* %s %s: python3 %s %s -o deploy -t %s" % (command, service_type, sys.argv[0], subparser_name, service_type)


def parse_command():
    parser = argparse.ArgumentParser(
        prog=sys.argv[0], description="", formatter_class=RawTextHelpFormatter, add_help=False)
    parser.add_argument("-h", '--help', action=_HelpAction)

    sub_parsers = parser.add_subparsers(dest="command")
    subparser_name = CommandInfo.download_binary
    help_info = "Download binary, eg: python3 build_chain.py download_binary -t cdn"
    binary_parser = sub_parsers.add_parser(description=utilities.format_info(help_info),
                                           name=subparser_name, help="download binary", formatter_class=RawTextHelpFormatter)
    help_info = "[Optional] Specify the source of the download, support %s now, default type is cdn" % (
        ','.join(CommandInfo.download_type))
    binary_parser.add_argument(
        "-t", '--type', help=help_info, default="cdn", required=False)
    help_info = "[Optional] Specify the version of the binary, default is %s" % CommandInfo.default_binary_version
    binary_parser.add_argument(
        "-v", "--version", default=CommandInfo.default_binary_version, help=help_info, required=False)
    help_info = "[Optional] Specify the path of the binary, default is binary"
    binary_parser.add_argument(
        "-p", "--path", default="binary", help=help_info, required=False)

    subparser_name = CommandInfo.chain_sub_parser_name
    deploy_nodes_command = get_description_prefix(
        subparser_name, "deploy", ServiceInfo.node_service_type)
    deploy_rpc_service_command = get_description_prefix(subparser_name,
                                                        "deploy", ServiceInfo.rpc_service_type)
    deploy_gateway_service_command = get_description_prefix(subparser_name,
                                                            "deploy", ServiceInfo.gateway_service_type)
    description = "e.g:\n%s\n%s\n%s" % (
        deploy_nodes_command, deploy_rpc_service_command, deploy_gateway_service_command)
    chain_parser = sub_parsers.add_parser(description=utilities.format_info(description),
                                          name=subparser_name, help="chain operation", formatter_class=RawTextHelpFormatter)
    # command option
    help_info = "[required] specify the command: \n* command list: %s\n" % (
        CommandInfo.service_command_list_str)
    chain_parser.add_argument(
        "-o", '--op', help=help_info, required=True)
    # config option
    help_info = "[optional] the config file, default is config.toml:\n * config to deploy chain example: conf/config-deploy-example.toml\n * config to expand node example: conf/config-node-expand-example.toml\n * config to expand rpc/gateway example: conf/config-service-expand-example.toml"
    chain_parser.add_argument(
        "-c", "--config", help=help_info, default="config.toml")
    # service type option
    supported_service_type_str = ', '.join(ServiceInfo.supported_service_type)
    help_info = "[required] the service type:\n* now support: %s \n" % (
        supported_service_type_str)
    chain_parser.add_argument("-t", "--type", help=help_info, default="")

    # create_subnet_parser parser
    description = "e.g: python3 %s create-subnet -n tars-network -s 172.25.0.0/16" % (
        sys.argv[0])
    create_subnet_parser = sub_parsers.add_parser(description=utilities.format_info(description),
                                                  name=CommandInfo.network_create_subnet, help="create docker subnet", formatter_class=RawTextHelpFormatter)
    help_info = "[optional] specified the network name, default is tars-network\n"
    create_subnet_parser.add_argument(
        "-n", "--name", help=help_info, default="tars-network")

    help_info = "[required] specified the subnet, e.g. 172.25.0.0/16\n"
    create_subnet_parser.add_argument(
        "-s", "--subnet", help=help_info, default=None, required=True)

    # network_add_vxlan
    # description = (
    #    "Note: only support linux now\ne.g: python3 %s add-vxlan -n tars-network -d ${remote_ip} -v docker_vxlan") % (sys.argv[0])
    # add_vxlan_parser = sub_parsers.add_parser(description=utilities.format_info(description),
    #                                          name=CommandInfo.network_add_vxlan, help="add vxlan for docker subnet", formatter_class=RawTextHelpFormatter)
    # subnet option
    #help_info = "[optional] specified the subnet, default is tars-network\n"
    # add_vxlan_parser.add_argument(
    #    "-n", "--network", help=help_info, default="tars-network")
    # remote ip
    #help_info = "[required] specified the dstip to create vxlan network"
    # add_vxlan_parser.add_argument(
    #    "-d", "--dstip", help=help_info, default=None, required=True)

    # vxlan network name
    #help_info = "[required] specified the vxlan name to create vxlan network, e.g.: vxlan_docker"
    # add_vxlan_parser.add_argument(
    #    "-v", "--vxlan", help=help_info, default=None, required=True)

    args = parser.parse_args()
    return args


def is_chain_command(args):
    return (args.command == CommandInfo.chain_sub_parser_name)


def is_create_subnet_command(args):
    return (args.command == CommandInfo.network_create_subnet)


def is_add_vxlan_command(args):
    return (args.command == CommandInfo.network_add_vxlan)


def is_download_binary_command(args):
    return (args.command == CommandInfo.download_binary)


def chain_operations(args, node_type):
    if is_chain_command(args) is False:
        return
    if os.path.exists(args.config) is False:
        utilities.log_error("The config file '%s' not found!" % args.config)
        sys.exit(-1)
    toml_config = toml.load(args.config)
    op_type = args.type
    if op_type not in ServiceInfo.supported_service_type:
        utilities.log_error("the service type must be " +
                            ', '.join(ServiceInfo.supported_service_type))
        return
    command = args.op
    if op_type == ServiceInfo.rpc_service_type or op_type == ServiceInfo.gateway_service_type:
        if command in CommandInfo.service_command_impl.keys():
            chain_config = ChainConfig(toml_config, node_type, False)
            command_impl = ServiceCommandImpl(
                chain_config, args.type, node_type)
            impl_str = CommandInfo.service_command_impl[command]
            cmd_func_attr = getattr(command_impl, impl_str)
            cmd_func_attr()
            return
    if op_type == ServiceInfo.monitor_service_type:
        if command in CommandInfo.node_command_to_impl.keys():
            chain_config = ChainConfig(toml_config, node_type, True)
            command_impl = MonitorCommandImpl(chain_config, node_type)
            impl_str = CommandInfo.monitor_command_to_impl[command]
            cmd_func_attr = getattr(command_impl, impl_str)
            cmd_func_attr()
            return
    if op_type == ServiceInfo.node_service_type:
        if command in CommandInfo.node_command_to_impl.keys():
            chain_config = ChainConfig(toml_config, node_type, True)
            command_impl = NodeCommandImpl(chain_config, node_type)
            impl_str = CommandInfo.node_command_to_impl[command]
            cmd_func_attr = getattr(command_impl, impl_str)
            cmd_func_attr()
            return
    if op_type == ServiceInfo.executor_service_type:
        if command in CommandInfo.executor_command_to_impl.keys():
            chain_config = ChainConfig(toml_config, node_type, True)
            command_impl = NodeCommandImpl(chain_config, node_type)
            impl_str = CommandInfo.executor_command_to_impl[command]
            cmd_func_attr = getattr(command_impl, impl_str)
            cmd_func_attr()
            return
    utilities.log_info("unimplemented command")


def create_subnet_operation(args):
    if is_create_subnet_command(args) is False:
        return
    docker_network_name = args.name
    if docker_network_name is None or len(docker_network_name) == 0:
        utilities.log_error(
            "Must set the docker network name! e.g. tars-network")
        sys.exit(-1)
    subnet_ip_segment = args.subnet
    if subnet_ip_segment is None or len(subnet_ip_segment) == 0:
        utilities.log_error("Must set the subnet! e.g. 172.25.0.0.1")
        sys.exist(-1)
    NetworkManager.create_sub_net(subnet_ip_segment, docker_network_name)
    utilities.print_split_info()


def add_vxlan_operation(args):
    if is_add_vxlan_command(args) is False:
        return
    utilities.print_split_info()
    network = args.network
    if network is None or len(network) == 0:
        utilities.log_error(
            "Must set a valid non-empty network name, e.g. tars-network")
        return
    dstip = args.dstip
    if dstip is None or len(dstip) == 0:
        utilities.log_error("Must set a valid non-empty dst ip")
        return
    vxlan_name = args.vxlan
    if vxlan_name is None or len(vxlan_name) == 0:
        utilities.log_error("Must set a valid non-empty vxlan name")
        return
    NetworkManager.create_bridge(network, vxlan_name, dstip)
    utilities.print_split_info()


def download_binary_operation(args, node_type):
    if is_download_binary_command(args) is False:
        return
    utilities.print_split_info()
    binary_path = args.path
    version = args.version
    if version.startswith("v") is False:
        version = "v" + version
    if args.type not in CommandInfo.download_type:
        utilities.log_error("Unsupported download type %s, only support %s now" % (
            args.type, ', '.join(CommandInfo.download_type)))
        return
    use_cdn = True
    if args.type == "git":
        use_cdn = False
    binary_controller = BinaryController(
        version, binary_path, use_cdn, node_type)
    binary_controller.download_all_binary()
    utilities.print_split_info()
