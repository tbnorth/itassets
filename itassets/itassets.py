import argparse
import os
from collections import defaultdict, namedtuple
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

AT = namedtuple("AssetType", "description shape color top bottom")
# shape / color for drawing graphs
# top => top level node like an application, needs no dependents to
#        justify its existence
# bottom => bottom level node like a server, doesn't need to depend on anything
ASSET_TYPE = {
    'application': AT(
        '"Terminal" asset type, that users use',
        'ellipse',
        'green',
        True,
        False,
    ),
    'container/docker': AT(
        "A docker container (image instance)", 'box3d', 'green', False, False
    ),
    'image/docker': AT(
        "The source (Dockerfile) for a Docker image",
        'house',
        'darkgreen',
        True,
        False,
    ),
    'physical/server': AT(
        "A real physical server", 'box', 'gray', False, True
    ),
    'physical/server/service': AT(
        "A service (web-server, RDMS) running directly"
        " on a physical server",
        'tripleoctagon',
        'pink',
        False,
        False,
    ),
    'vm/virtualbox': AT(
        "A VirtualBox VM", 'doubleoctagon', 'pink', False, False
    ),
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
    dependents = defaultdict(lambda: [])
    # check for duplicate IDs, dependents
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
        for dep in asset.get('depends_on', []):
            dependents[dep].append(id_)
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
        if (
            id_ not in dependents
            and 'type' in asset
            and not ASSET_TYPE[asset['type']].top
        ):
            issues.append(("WARNING", "non-top-level asset has no dependents"))
        if (
            not asset.get('depends_on')
            and not ASSET_TYPE[asset['type']].bottom
        ):
            issues.append(
                ("WARNING", "non-bottom-level asset has no dependencies")
            )
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
                ans.append(
                    f'  n{len(other)} [label="???", shape="tripleoctagon", '
                    'fillcolor="red", style="filled"]'
                )
                other[dep] = {'name': "???", '_node_id': f"n{len(other)}"}

    for _node_id, asset in enumerate(assets):
        asset['_node_id'] = f"n{_node_id}"
    for asset in assets:
        ans.append(
            '  {id} [label="{name}", shape="{shape}", '
            'fillcolor="{color}", style="filled"]'.format(
                id=asset['_node_id'],
                name=asset['name'],
                shape=ASSET_TYPE[asset["type"]].shape,
                color=ASSET_TYPE[asset["type"]].color,
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
