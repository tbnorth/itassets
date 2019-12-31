import argparse
import os
import re
import time
from collections import defaultdict, namedtuple
from itertools import chain

import yaml

AT = namedtuple(
    "AssetType", "description style color tags fields depends prefix"
)

# shape / color for drawing graphs
# top => top level node like an application, needs no dependents to
#        justify its existence
# bottom => bottom level node like a server, doesn't need to depend on anything
ASSET_TYPE = {
    'application': AT(
        '"Terminal" asset type, that users use',
        "shape=oval, width=1.5, rank=max",
        'green',
        ['top'],
        ['location', 'owner'],
        [
            '(cloud/service|container/.*|'
            'physical/server/service$|website/static)'
        ],
        'app',
    ),
    'cloud/service': AT(
        "A service (web-server, RDMS) running in the cloud",
        'shape=polygon, width=1.25, sides=9',
        'pink',
        [],
        ['location'],
        ['resource/deployment'],
        'csvc',
    ),
    'container/docker': AT(
        "A docker container (image instance)",
        'shape="box3d", width=1.5',
        'green',
        [],
        [],
        [
            'resource/deployment',
            '(physical/server|cloud/service)',
            'storage/.*',
        ],
        'con',
    ),
    'drive': AT(
        "A physical drive",
        'shape=cylinder, width=1.25',
        'cyan',
        [],
        ['location', 'size'],
        ['physical/server'],
        'drv',
    ),
    'resource/deployment': AT(
        "The source / deplpoyment resource for an asset, "
        "e.g. the Dockerfile for a Docker image",
        'shape=note, width=1.5',
        'cyan',
        ['bottom'],
        ['location'],
        [],
        'dply',
    ),
    'physical/server': AT(
        "A real physical server",
        'shape=box, width=1',
        'gray',
        ['bottom'],
        [],
        [],
        'srv',
    ),
    'physical/server/service': AT(
        "A service (web-server, RDMS) running directly"
        " on a physical server",
        'shape=pentagon, width=1.25',
        'pink',
        [],
        [],
        ['physical/server', 'resource/deployment', 'storage/.*'],
        'psvc',
    ),
    'physical/server/service/infrastructure': AT(
        "A service (web-server, RDMS) running directly"
        " on a physical server",
        'shape=octagon, width=1.25',
        'pink',
        [],
        [],
        ['physical/server', 'resource/deployment', 'storage/.*'],
        'psvc',
    ),
    'vm/virtualbox': AT(
        "A VirtualBox VM",
        'shape=box, peripheries="2", width=1.4',
        'pink',
        [],
        [],
        ['physical/server', 'storage/.*'],
        'vbx',
    ),
    'storage/local': AT(
        "A local storage solutions, requires backup",
        'shape=folder,width=1.5',
        'white',
        [],
        ['location'],
        ['backup', 'drive'],
        'sto',
    ),
    'backup': AT(
        "A backup solution",
        'shape=Msquare,width=1.5',
        'white',
        [],
        ['location'],
        [],
        'bak',
    ),
    'website/static': AT(
        "A static website, may include javascript",
        'shape=trapezium,width=1.5',
        'white',
        [],
        ['location'],
        ['resource/deployment', 'storage/.*', 'physical/server/service'],
        'wss',
    ),
}

ID_PREFIX = {v.prefix: v.description for v in ASSET_TYPE.values()}
# fields treated as lists on report output
LIST_FIELDS = (
    'closed_issues',
    'depends_on',
    'links',
    'notes',
    'open_issues',
    'tags',
)

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
    for dep in asset_dep_ids(asset):
        if dep not in lookup and not dep.startswith('^'):
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
        and 'top' not in ASSET_TYPE[asset['type']].tags
    ):
        yield 'WARNING', "Non-top-level asset has no dependents"


@validator('.*')
def dependencies_if_not_bottom(asset, lookup, dependents):
    if (
        not asset.get('depends_on')
        and 'bottom' not in ASSET_TYPE[asset['type']].tags
    ):
        yield 'WARNING', "Non-bottom-level asset has no dependencies"


@validator('.*')
def has_open_issues(asset, lookup, dependents):
    if asset.get('open_issues'):
        yield 'WARNING', "Has open issues"


@validator('.*')
def tagged_needs_work(asset, lookup, dependents):
    if 'needs_work' in asset.get('tags', []):
        yield 'WARNING', "Has 'needs_work' tag"


@validator('.*')
def check_fields(asset, lookup, dependents):
    type_ = asset['type']
    for field in ASSET_TYPE[type_].fields:
        if not asset.get(field):
            yield 'WARNING', f"'{type_} definition missing '{field}' field"


@validator('.*')
def check_depends(asset, lookup, dependents):
    type_ = asset['type']
    for dep in ASSET_TYPE[type_].depends:
        if '^' + dep in asset_dep_ids(asset):
            yield 'NOTE', f"Specifically excludes '{dep}' dependency"
            continue
        if not any(
            re.search(dep, lookup.get(i, {'type': "NO-TYPE"})['type'])
            for i in asset_dep_ids(asset, insufficient=True)
        ):
            yield 'WARNING', f"'{type_}' should define '{dep}' dependency"


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
    file_data['assets'] = [
        i for i in file_data['assets'] if 'archived' not in i.get('tags', [])
    ]
    return file_data['assets']


def general_info(assets):
    """Search the assets for a general section"""
    for asset in assets:
        try:
            return asset['file_data']['general']
        except KeyError:
            pass
    return None


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
        for dep in asset_dep_ids(asset):
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


def dot_node_name(text):
    """Handle wide node names"""
    hlen = len(text) // 2
    if hlen <= 8:
        return text
    i = 0
    at = None
    while i < hlen - 1:
        if text[hlen + i] in ' _-':
            at = hlen + i
            break
        if text[hlen - i] in ' _-':
            at = hlen - i
            break
        i += 1
    if at is not None:
        return text[:at] + '\\n' + text[at:]
    return text


def link_links(text):
    lines = text.split('\n')
    for line_i, line in enumerate(lines):
        if re.search(r'\w+://', line):
            words = [
                f"<a href={i} target='_blank'>{i}</a>"
                if re.match(r'\w+://', i)
                else i
                for i in line.split(' ')
            ]
            lines[line_i] = ' '.join(words)
    return '\n'.join(lines)


def html_filename(asset):
    fn = asset.get('name', asset['id']).replace('/', '-')
    return 'asset_reports/' + '_'.join(fn.split()) + '.html'


def edit_url(asset):
    if not asset.get('file_data'):
        return None  # a node for an undefined dependency
    return f"itas://{asset['file_data']['file_path']}#{asset['id']}"


def report_to_html(asset, tooltip):
    fn = html_filename(asset)
    with open(f"{fn}", 'w') as rep:
        rep.write(
            f"<html><head><title>{asset.get('name')}</title></head><body>"
        )
        rep.write(f"<h2>{asset['id']}: {asset.get('name')}</h2><pre>")
        rep.write(link_links('\n'.join(tooltip)))
        rep.write(f"\n<a href='{edit_url(asset)}'>edit</a>\n")
        rep.write("</pre></body></html>")


def add_missing_deps(assets, other, ans):
    for asset in assets:
        real_deps = [i for i in asset_dep_ids(asset) if not i.startswith('^')]
        for dep in real_deps:
            if dep not in other:
                ans.append(
                    f'  n{len(other)} [label="???", shape=doubleoctagon, '
                    'fillcolor=pink, style=filled]'
                )
                # used just to display missing asset on graph plot
                other[dep] = {'name': "???", '_node_id': f"n{len(other)}"}


def asset_dep_ids(asset, insufficient=False):
    return [
        i.split()[0]
        for i in asset.get('depends_on', [])
        if (not insufficient or 'INSUF' not in i)
    ]


def get_title(assets):
    ttl = general_info(assets)
    if ttl:
        ttl = ttl['title']
    else:
        ttl = ''
    return f"{ttl} updated {time.asctime()}"


def assets_to_dot(assets, issues):
    other = {i['id']: i for i in assets}
    ans = [
        "digraph Assets {",
        '  graph [rankdir=LR, concentrate=true, URL="index.html"'
        f'       label="{get_title(assets)}", fontname=FreeSans, tooltip=" "]',
        "  node [fontname=FreeSans, fontsize=10]",
    ]
    add_missing_deps(assets, other, ans)
    os.makedirs("asset_reports", exist_ok=True)

    for _node_id, asset in enumerate(assets):
        asset['_node_id'] = f"n{_node_id}"
    for asset in assets:
        real_deps = [i for i in asset_dep_ids(asset) if not i.startswith('^')]
        tooltip = []
        # put asset attributes in tooltip
        for k, v in asset.items():
            if isinstance(v, str) and not k.startswith('_'):
                tooltip.append(f"{k}: {v}")
        # put tags etc. in tooltip
        for list_field in LIST_FIELDS:
            if asset.get(list_field):
                tooltip.append(list_field.upper())
                for item in asset.get(list_field, []):
                    tooltip.append(f"  {item}")
        # include path to asset def. file in tooltip
        tooltip.append(f"Defined in {asset['file_data']['file_path']}")
        # dict of dot / graphviz node attributes
        attr = dict(
            label=dot_node_name(asset.get('name')),
            URL=html_filename(asset),
            target=f"_{asset['id']}",
        )
        if False:  # used to generate demo output
            attr['label'] = asset['type'].split('/')[-1]
        # `style` is compound 'shape=box, color=cyan', so key is None
        attr[None] = (ASSET_TYPE[asset["type"]].style,)
        # add validation issues to top of tooltip
        if asset['id'] in issues:
            tooltip[:0] = ["%s %s" % (i, j) for i, j in issues[asset['id']]]
            if any(i[0] != 'NOTE' for i in issues[asset['id']]):
                attr['style'] = 'filled'
                attr['fillcolor'] = 'pink'
        # write tooltip to validation HTML page for copy / paste etc.
        report_to_html(asset, tooltip)
        # tooltip dict -> text
        attr['tooltip'] = '\\n'.join(tooltip)

        # write node to graphviz file
        ans.append(node_dot(asset['_node_id'], attr))

        # write links to graphviz file
        for dep in real_deps:
            attr = dict(
                fontcolor='#ffffff00',
                headURL=edit_url(asset),
                headlabel='edit',
                headtooltop='Edit',
            )
            if edit_url(other[dep]):  # i.e. not an undefined dependency
                attr.update(
                    dict(
                        tailURL=edit_url(other[dep]),
                        taillabel='edit',
                        tailtooltop='Edit',
                    )
                )
            edge_attr = node_dot('x', attr).split(None, 1)[-1]
            ans.append(
                f"  {other[dep]['_node_id']} -> {asset['_node_id']}"
                f"{edge_attr}"
            )

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
