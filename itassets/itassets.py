import argparse
import os
from itertools import chain

import yaml

ID_PREFIX = {
    'dok': "Docker image definition / source",
    'con': "Docker container",
    'srv': "Physical server",
    'vbx': "VirtualBox VM",
    'svc': "A Service like Postgres, Apache",
    'app': "An application users use",
}

ASSET_TYPE = {
    'application': '"Terminal" asset type, that users use',
    'container/docker': "A docker container (image instance)",
    'image/docker': "The source (Dockerfile) for a Docker image",
    'physical/server': "A real physical server",
    'physical/server/service': "A service (web-server, RDMS) running directly"
    " on a physical server",
    'vm/virtualbox': "A VirtualBox VM",
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
    if not file_data:
        return []
    for asset in file_data.get('assets', []):
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
        issues = []
        if id_.split('_')[0] not in ID_PREFIX:
            issues.append(("WARNING", "has unknown prefix"))
        if asset.get('type') not in ASSET_TYPE:
            issues.append(("ERROR", f"has unknown type {asset.get('type')}"))
        for dep in asset.get('depends_on', []):
            if dep not in seen:
                issues.append(("WARNING", f"depends on undefined id={dep}"))
        if issues:
            print(f"\nASSET: {id_} in {filepath}")
        for type_, description in issues:
            print(f"    {type_}: {description}")


def assets_to_dot(assets):
    other = {i['id']: i for i in assets}
    ans = ['digraph "Assets" {', "  graph [rankdir=LR]"]
    for asset in assets:
        for dep in asset.get('depends_on', []):
            if dep not in other:
                ans.append(f'  n{len(other)} [label="???"]')
                other[dep] = {'name': "???", '_node_id': f"n{len(other)}"}

    for _node_id, asset in enumerate(assets):
        asset['_node_id'] = f"n{_node_id}"
    for asset in assets:
        ans.append(
            '  {id} [label="{name}"]'.format(
                id=asset['_node_id'], name=asset['name']
            )
        )
        for dep in asset.get('depends_on', []):
            ans.append(f"  {asset['_node_id']} -> {other[dep]['_node_id']}")

    ans.append('}')
    return '\n'.join(ans)


def main():
    opt = get_options()
    assets = []
    for asset_file in chain.from_iterable(opt.assets):
        assets.extend(load_assets(asset_file))
    validate_assets(assets)
    with open("assets.dot", 'w') as out:
        out.write(assets_to_dot(assets))


if __name__ == "__main__":
    main()
