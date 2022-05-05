import os

from cf_deploy.util import logger

log = logger.get_logger('innolab-deployer.deploy.settings')

# DIRECTORY CONFIGURATION
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(PROJECT_DIR, 'templates')
APPLICATION_DIR = os.path.join(TEMPLATE_DIR, 'applications')
PIPELINES_DIR = os.path.join(TEMPLATE_DIR, 'pipelines')
SERVICES_DIR = os.path.join(TEMPLATE_DIR, 'services')
