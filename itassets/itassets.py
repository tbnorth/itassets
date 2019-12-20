import argparse
import os
from itertools import chain

import yaml

ID_PREFIX = {
    'dok': "Docker image definition / source",
    'con': "Docker container",
    'srv': "Physical server",
    'vbx': "VirtualBox VM",
}


def make_parser():

    parser = argparse.ArgumentParser(
        description="""Make reports from asset DB""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--assets",
        action='append',
        nargs='+',
        help="One or more asset .yaml files to read",
        metavar="FILE",
    )

    return parser


def get_options(args=None):
    """
    get_options - use argparse to parse args, and return a
    argparse.Namespace, possibly with some changes / expansions /
    validations.

    Client code should call this method with args as per sys.argv[1:],
    rather than calling make_parser() directly.

    Args:
        args ([str]): arguments to parse

    Returns:
        argparse.Namespace: options with modifications / validations
    """
    opt = make_parser().parse_args(args)

    # modifications / validations go here

    return opt


def load_assets(asset_file):
    file_data = yaml.safe_load(open(asset_file))
    for asset in file_data['assets']:
        asset['file_data'] = file_data
    file_data['file_path'] = os.path.abspath(asset_file)
    return file_data['assets']


def validate_assets(assets):
    seen = {}
    # check for duplicate IDs
    for asset in assets:
        id_ = asset['id']
        if id_ in seen:
            print(f"ERROR: {id_} already seen")
            print(
                f"       First used in {seen[id_]['file_data']['file_path']}"
            )
            print(f"       Duplicated in {asset['file_data']['file_path']}")
        else:
            seen[id_] = asset
    # check all depends_on IDs are defined, ID prefixes recognized
    for asset in assets:
        id_ = asset['id']
        filepath = asset['file_data']['file_path']
        if id_.split('_')[0] not in ID_PREFIX:
            print("WARNING: {id} in {file}".format(id=id_, file=filepath))
            print("         has unknown prefix")
        for dep in asset.get('depends_on', []):
            if dep not in seen:
                print("WARNING: {id} in {file}".format(id=id_, file=filepath))
                print(f"         depends on undefined id={dep}")


def main():
    opt = get_options()
    assets = []
    for asset_file in chain.from_iterable(opt.assets):
        assets.extend(load_assets(asset_file))
    validate_assets(assets)


if __name__ == "__main__":
    main()
