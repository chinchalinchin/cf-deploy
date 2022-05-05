import argparse
import enum
import os
import pprint
import sys

from cf_deploy.deploy.deployer import deploy


class Commands(enum.Enum):
    deploy = 'deploy'

    def __str__(self):
        return self.value


def is_directory(path: str):
    if os.path.isfile(path):
        return path
    raise FileNotFoundError(path)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('command',
                        type=Commands,
                        choices=list(Commands),
                        help="deploy")
    parser.add_argument('-yml', '--yaml-file',
                        type=lambda x: is_directory(x),
                        required='deploy' in sys.argv,
                        help="Absolute path to the YAML deployment configuration file")
    parser.add_argument('-iam', '--iam',
                        action='store_true',
                        help="Deploy stack with IAM named capabilities")
    return parser.parse_args()


def entrypoint():
    args = parse_args()

    if args.command == Commands.deploy:
        results = deploy(args.yaml_file, args.iam)

    pprint.pprint(results)


if __name__ == "__main__":
    entrypoint()
