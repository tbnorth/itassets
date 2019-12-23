import argparse
import os
import re
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

AT = namedtuple("AssetType", "description style color top bottom")
# shape / color for drawing graphs
# top => top level node like an application, needs no dependents to
#        justify its existence
# bottom => bottom level node like a server, doesn't need to depend on anything
ASSET_TYPE = {
    'application': AT(
        '"Terminal" asset type, that users use',
        'shape="ellipse"',
        'green',
        True,
        False,
    ),
    'container/docker': AT(
        "A docker container (image instance)",
        'shape="box3d"',
        'green',
        False,
        False,
    ),
    'image/docker': AT(
        "The source (Dockerfile) for a Docker image",
        'shape="note"',
        'cyan',
        False,
        True,
    ),
    'physical/server': AT(
        "A real physical server", 'shape="box"', 'gray', False, True
    ),
    'physical/server/service': AT(
        "A service (web-server, RDMS) running directly"
        " on a physical server",
        'shape="octagon"',
        'pink',
        False,
        False,
    ),
    'vm/virtualbox': AT(
        "A VirtualBox VM", 'shape="box", peripheries="2"', 'pink', False, False
    ),
}

VALIDATORS = defaultdict(lambda: [])
VALIDATORS_COMPILED = {}


def validator(type_):
    def add_validator(function, type_=type_):
        VALIDATORS[type_].append(function)

    return add_validator


# do this first, as it may explain subsequent KeyErrors
@validator('.*')
def known_asset_type(asset, lookup, dependents):
    if asset.get('type') not in ASSET_TYPE:
        yield 'ERROR', f"Has unknown type {asset.get('type')}"


@validator('.*')
def no_undef_depends(asset, lookup, dependents):
    for dep in asset.get('depends_on', []):
        if dep not in lookup:
            yield 'WARNING', f"Depends on undefined asset ID={dep}"


@validator('.*')
def known_id_prefix(asset, lookup, dependents):
    if asset['id'].split('_')[0] not in ID_PREFIX:
        yield 'WARNING', "Has unknown prefix"


@validator('.*')
def dependents_if_not_top(asset, lookup, dependents):
    if (
        asset['id'] not in dependents
        and 'type' in asset
        and not ASSET_TYPE[asset['type']].top
    ):
        yield 'WARNING', "Non-top-level asset has no dependents"


@validator('.*')
def dependencies_if_not_bottom(asset, lookup, dependents):
    if not asset.get('depends_on') and not ASSET_TYPE[asset['type']].bottom:
        yield 'WARNING', "Non-bottom-level asset has no dependencies"


@validator('.*')
def tagged_needs_work(asset, lookup, dependents):
    if 'needs_work' in asset.get('tags', []):
        yield 'WARNING', "Has 'needs_work' tag"


@validator('image/docker')
def check_location(asset, lookup, dependents):
    if not asset.get('location'):
        yield 'WARNING', "Image definition missing 'location' field"


@validator('application')
def check_owner(asset, lookup, dependents):
    if not asset.get('owner'):
        yield 'WARNING', "Application definition missing 'owner' field"


@validator('container/docker')
def container_def(asset, lookup, dependents):
    if not any(
        lookup.get(i, {'type': None})['type'] == 'image/docker'
        for i in asset.get('depends_on', [])
    ):
        yield (
            'WARNING',
            "'container/docker' should define 'image/docker' dependency",
        )


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
    failures = {}
    # check for duplicate IDs, dependents
    duplicate_IDs = False
    for asset in assets:
        id_ = asset['id']
        if id_ in seen:
            duplicate_IDs = True
            print(f"ERROR: {id_} already seen")
            print(
                f"       First used in {seen[id_]['file_data']['file_path']}"
            )
            print(f"       Duplicated in {asset['file_data']['file_path']}")
        else:
            seen[id_] = asset
        for dep in asset.get('depends_on', []):
            dependents[dep].append(id_)
    if duplicate_IDs:
        raise Exception("Can't continue with duplicate IDs present")

    # check all depends_on IDs are defined, ID prefixes recognized
    if not VALIDATORS_COMPILED:
        VALIDATORS_COMPILED.update(
            {re.compile(k): v for k, v in VALIDATORS.items()}
        )
    for asset in assets:
        issues = []
        try:
            for pattern, validators in VALIDATORS_COMPILED.items():
                if pattern.search(asset.get('type', 'NOT-SPECIFIED')):
                    for validator in validators:
                        issues.extend(list(validator(asset, seen, dependents)))
        finally:
            if issues:
                failures[asset['id']] = issues
                print(
                    f"\nASSET: {asset['id']} '{asset.get('name')}'"
                    f"\n       in {asset['file_data']['file_path']}"
                )
            for type_, description in issues:
                print(f"    {type_}: {description}")

    return failures


def node_dot(id_, attr):
    return "  {id} [{attrs}]".format(
        id=id_,
        attrs=', '.join(
            (f'{k}="{v}"' if k else v[0]) for k, v in attr.items()
        ),
    )


def assets_to_dot(assets, issues):
    other = {i['id']: i for i in assets}
    ans = [
        'digraph "Assets" {',
        "  graph [rankdir=LR]",
        '  node [fontname="Ariel"]',
    ]
    os.makedirs("asset_reports", exist_ok=True)
    for asset in assets:
        for dep in asset.get('depends_on', []):
            if dep not in other:
                ans.append(
                    f'  n{len(other)} [label="???", shape="doubleoctagon", '
                    'fillcolor="pink", style="filled"]'
                )
                other[dep] = {'name': "???", '_node_id': f"n{len(other)}"}

    for _node_id, asset in enumerate(assets):
        asset['_node_id'] = f"n{_node_id}"
    for asset in assets:
        tooltip = []
        for k, v in asset.items():
            if isinstance(v, str) and not k.startswith('_'):
                tooltip.append(f"{k}: {v}")
        for tag in asset.get('tags', []):
            tooltip.append(f"TAG {tag}")
        tooltip.append(f"Defined in {asset['file_data']['file_path']}")
        attr = dict(
            label=asset.get('name'),
            URL=f"./asset_reports/n{asset['_node_id']}.html",
        )
        attr[None] = (ASSET_TYPE[asset["type"]].style,)
        if asset['id'] in issues:
            tooltip[:0] = ["%s %s" % (i, j) for i, j in issues[asset['id']]]
            attr['style'] = 'filled'
            attr['fillcolor'] = 'pink'
        with open(f"asset_reports/n{asset['_node_id']}.html", 'w') as rep:
            rep.write(f"<h2>{asset['id']}: {asset.get('name')}</h2><pre>")
            rep.write('\n'.join(tooltip))
            rep.write("</pre>")
        attr['tooltip'] = '\\n'.join(tooltip)
        ans.append(node_dot(asset['_node_id'], attr))

        for dep in asset.get('depends_on', []):
            ans.append(f"  {asset['_node_id']} -> {other[dep]['_node_id']}")

    ans.append('}')
    return '\n'.join(ans)


def main():
    opt = get_options()
    assets = []
    for asset_file in chain.from_iterable(opt.assets):
        assets.extend(load_assets(asset_file))
    issues = validate_assets(assets)
    with open("assets.dot", 'w') as out:
        out.write(assets_to_dot(assets, issues))


if __name__ == "__main__":
    main()
