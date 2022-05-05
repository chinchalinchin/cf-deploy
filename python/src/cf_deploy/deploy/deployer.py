import boto3
import botocore
import os
import sys
import yaml
import time

from cf_deploy.deploy import settings
from cf_deploy.util import logger

log = logger.get_logger('innolab-cloudformation.deploy.deployer')

ACTIVE_STACKS = [
    'CREATE_IN_PROGRESS',
    'CREATE_COMPLETE',
    'ROLLBACK_IN_PROGRESS',
    'ROLLBACK_COMPLETE',
    'DELETE_IN_PROGRESS',
    'UPDATE_IN_PROGRESS',
    'UPDATE_COMPLETE',
    'UPDATE_ROLLBACK_FAILED',
    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
    'UPDATE_ROLLBACK_IN_PROGRESS',
    'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
    'UPDATE_ROLLBACK_COMPLETE'
]
IN_PROGRESS_STACKS = [
    'CREATE_IN_PROGRESS',
    'UPDATE_IN_PROGRESS',
    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
]


def handle_boto_error(err: botocore.exceptions.ClientError):
    """Handle **boto3** client response errors.

    :param err: Client error
    :type err: :class:`botocore.exceptions.ClientError`
    :return: Handled error
    """
    log.warning("Client Response %s - %s: %s",
                err.response['ResponseMetadata']['HTTPStatusCode'],
                err.response['Error']['Code'],
                err.response['Error']['Message'])
    if err.response['Error']['Code'] == "ValidationError" and \
            err.response['Error']['Message'] != "No updates are to be performed.":
        sys.exit(1)
    return err


def env_var_constructor(loader: yaml.SafeLoader, node: yaml.nodes.ScalarNode) -> str:
    """Pull YAML node reference from corresponding environment variable

    :param loader: YAML Serializer
    :type loader: :class:`yaml.SafeLoader`
    :param node: Node in the YAML tree
    :type node: :class:`yaml.nodes.ScalarNode`
    :return: Environment variable value with given `node` key.
    :rtype: str
    """
    env_key = loader.construct_scalar(node)
    env_var = os.getenv(env_key)

    if env_var is not None:
        return env_var

    raise OSError(
        f'${env_key} environment variable not found. Export from session and then re-execute.')


def get_loader() -> yaml.SafeLoader:
    """Add environment variable constructor to PyYAML loader.
    :return: YAML serializer
    :rtype: :class:`yaml.SafeLoader`
    """
    loader = yaml.SafeLoader
    loader.add_constructor("!env", env_var_constructor)
    return loader


def load_deployment(yaml_configuration_file: str) -> dict:
    """Loads in the YAML specified on the command line.

    :param yaml_configuration_file: Absolute path to the deployment YAML
    :type yaml_configuration_file: str
    :return: deployment configuration
    :rtype: dict
    """
    if os.path.exists(yaml_configuration_file):
        with open(yaml_configuration_file, 'r') as infile:
            deployment = yaml.load(infile, Loader=get_loader())
        return deployment
    raise FileNotFoundError(f'{yaml_configuration_file} does not exist')


def get_capabilities(admin: bool = False) -> list:
    """ Return the permissions given to the deployer script.
    :param admin: flag for admin permissions
    :type admin: bool
    :return: capabilities allocated to the deployer script
    :rtype: list 
    """
    if admin:
        return [
            'CAPABILITY_IAM',
            'CAPABILITY_NAMED_IAM',
            'CAPABILITY_AUTO_EXPAND',
        ]
    return [
        'CAPABILITY_AUTO_EXPAND'
    ]


def get_client() -> boto3.client:
    """ Factory function for **boto3 CloudFormation** client
    :return: **CloudFormation** client
    :rtype: :class:`boto3.client`
    """
    return boto3.client('cloudformation')


def get_stack_names(in_progress: bool = False) -> list:
    """Return list of currently active **CloudFormation** stacks.

    :param in_progress: Flag to filter stacks by `*_IN_PROGRESS` only.
    :type in_progress: bool
    :return: Stack names
    :rtype: list
    """
    if in_progress:
        filter = IN_PROGRESS_STACKS
    else:
        filter = ACTIVE_STACKS
    stacks = get_client().list_stacks(
        StackStatusFilter=filter
    )['StackSummaries']
    return [stack['StackName'] for stack in stacks]


def update_stack(stack: str, deployment: dict, capabilities: list) -> dict:
    """Update the given `stack` with the given `deployment` configuration

    :param stack: Name of the stack to be updated.
    :type stack: str
    :param deployment: `dict` containing the deployment configuration
    :type deployment: dict
    :return: **CloudFormation** response
    :rtype: dict
    """
    log.info('Updating stack %s', stack)
    parameters = deployment['parameters']

    try:
        with open(os.path.join(settings.TEMPLATE_DIR, deployment['template']), 'r') as infile:
            template = infile.read()
    except FileNotFoundError as e:
        log.warning(e)
        return e

    client = get_client()
    try:
        return client.update_stack(
            StackName=stack,
            TemplateBody=template,
            Parameters=parameters,
            Capabilities=capabilities
        )
    except botocore.exceptions.ClientError as e:
        return handle_boto_error(e)


def create_stack(stack: str, deployment: dict, capabilities: list) -> dict:
    """Create the given `stack` with the given `deployment` configuration

    :param stack: Name of the stack to be updated.
    :type stack: str
    :param deployment: `dict` containing the deployment configuration
    :type deployment: dict
    :return: **CloudFormation** response
    :rtype: dict
    """
    log.info('Creating stack %s', stack)
    parameters = deployment['parameters']

    try:
        with open(os.path.join(settings.TEMPLATE_DIR, deployment['template']), 'r') as infile:
            template = infile.read()
    except FileNotFoundError as e:
        log.warning(e)
        return e

    client = get_client()
    try:
        return client.create_stack(
            StackName=stack,
            TemplateBody=template,
            Parameters=parameters,
            Capabilities=capabilities,
        )
    except botocore.exceptions.ClientError as e:
        return handle_boto_error(e)


def deploy(deployment_file: str, as_admin: bool = False):
    """Application entrypoint. This function orchestrates the deployment.
    """

    stack_deployments, stack_names, capabilities = load_deployment(
        deployment_file), get_stack_names(), get_capabilities(as_admin)

    if stack_deployments is not None:
        for stack, deployment in stack_deployments.items():
            if stack in stack_names:
                update_stack(stack, deployment, capabilities)
            else:
                create_stack(stack, deployment, capabilities)

            while stack in get_stack_names(in_progress=True):
                log.info('Waiting on %s...', stack)
                time.sleep(10)
    else:
        log.info(stack_names)
