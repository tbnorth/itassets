import argparse
import json
import os
import re
import time
from collections import defaultdict, namedtuple
from itertools import chain

from lxml import etree
import jinja2
import yaml

OUTPUT_DIR = 'asset_inventory'

AT = namedtuple(
    "AssetType", "description style color tags fields depends prefix"
)

# shape / color for drawing graphs
# top => top level node like an application, needs no dependents to
#        justify its existence
# bottom => bottom level node like a server, doesn't need to depend on anything
ASSET_TYPE = {
    'application/external': AT(
        '"Terminal" asset type, that users use',
        "shape=oval, width=1.5, rank=max",
        'green',
        ['top'],
        ['location', 'owner'],
        [
            '(cloud/service|container/.*|vm/virtualbox|'
            'physical/server/service$|website/static)'
        ],
        'app',
    ),
    # application/internal same as external except peripheries=2
    'application/internal': AT(
        '"Terminal" asset type, that users use',
        "shape=oval, width=1.5, rank=max, peripheries=2",
        'green',
        ['top'],
        ['location', 'owner'],
        [
            '(cloud/service|container/.*|vm/virtualbox|'
            'physical/server/service$|website/static)'
        ],
        'app',
    ),
    'backup': AT(
        "A backup solution",
        'shape=component, width=1.5',
        'white',
        [],
        ['location'],
        [],
        'bak',
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
    'database': AT(
        "A database on a server",
        "shape=house",
        "white",
        [],
        [],
        [
            '(cloud/service|container/.*|vm/virtualbox|'
            'physical/server/service$)',
            'backup',
        ],
        'db_',
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
    'storage/local': AT(
        "A local storage solutions, requires backup",
        'shape=folder,width=1.5',
        'white',
        [],
        ['location'],
        ['backup', 'drive'],
        'sto',
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
    'website/static': AT(
        "A static website, may include javascript",
        'shape=tab,width=1',
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

LIGHT_THEME = dict(
    dot_header=[
        "digraph Assets {{",
        '  graph [rankdir=LR, concentrate=true, URL="{top}index.html"',
        '       label="{title}", fontname=FreeSans, tooltip=" "]',
        "  node [fontname=FreeSans, fontsize=10]",
        "  edge [fontname=FreeSans, fontsize=10]",
    ],
    dot_err_col='pink',
)

DARK_THEME = dict(stroke="#808080", text="#808080")
DARK_THEME.update(
    dict(
        dot_header=[
            "digraph Assets {{",
            '  graph [rankdir=LR, concentrate=true, URL="{top}index.html"',
            '         label="{title}", fontname=FreeSans, tooltip=" ",',
            '         bgcolor=black]',
            f'  node [fontname=FreeSans, fontsize=10, '
            f'color="{DARK_THEME["stroke"]}", '
            f'        fontcolor="{DARK_THEME["text"]}"]',
            f'  edge [fontname=FreeSans, fontsize=10, ',
            f'color="{DARK_THEME["stroke"]}"]',
        ],
        dot_err_col='#200000',
    )
)

THEME = DARK_THEME

VALIDATORS = defaultdict(lambda: [])
VALIDATORS_COMPILED = {}  # updated in main()


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
            yield 'WARNING', f"'{type_}' definition missing '{field}' field"


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
    parser.add_argument(
        "--leaf-type",
        help="Trim map to stop at assets of this TYPE (regex match)",
        metavar="TYPE",
    )
    parser.add_argument(
        "--leaf-negate",
        help="Trim map to show assets not leading to --leaf-type",
        action='store_true',
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


def get_jinja():
    path = os.path.join(os.path.dirname(__file__), 'templates')
    return jinja2.Environment(loader=jinja2.FileSystemLoader([path]))


def load_assets(asset_file):
    file_data = yaml.safe_load(open(asset_file))
    if not file_data:
        return []
    for asset in file_data.get('assets', []):
        asset['file_data'] = file_data
    file_data['file_path'] = os.path.abspath(asset_file)
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
        try:
            id_ = asset['id']
            if id_ in seen:
                duplicate_IDs = True
                print(f"ERROR: {id_} already seen")
                print(f"  First used in {seen[id_]['file_data']['file_path']}")
                print(f"  Duplicated in {asset['file_data']['file_path']}")
            else:
                seen[id_] = asset
            for dep in asset_dep_ids(asset):
                dependents[dep].append(id_)
        except Exception:
            print(f"Failed validating {asset}")
    if duplicate_IDs:
        raise Exception("Can't continue with duplicate IDs present")

    for asset in assets:
        issues = [('UNKNOWN', 'FAILURE')]
        # Having something on this list makes sure the finally clause prints
        # something to incriminate the failing asset if there's an exception
        # before anything's added to issues.
        try:
            for pattern, validators in VALIDATORS_COMPILED.items():
                if pattern.search(asset.get('type', 'NOT-SPECIFIED')):
                    for validator in validators:
                        issues.extend(list(validator(asset, seen, dependents)))
            assert issues[0] == ('UNKNOWN', 'FAILURE')
            del issues[0]  # remove this, see comment above
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


def propagate_dependent(assets, output='_dependent_types', field='type'):
    """Add a `_dependent_types` set to all assets which lists the types of
    assets dependent on this asset, to generate trimmed maps with --leaf-type.
    """
    # FIXME: catch circular dependencies
    lookup = {i['id']: i for i in assets}

    def add_types(asset, type_, lookup):
        asset.setdefault(output, set()).add(type_)
        for depend in asset_dep_ids(asset):
            if depend in lookup:
                add_types(lookup[depend], type_, lookup)

    for asset in assets:
        add_types(asset, asset[field], lookup)


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
        lines[line_i] = line.replace('<', '&lt;')
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
    try:
        fn = asset.get('name', asset['id']).replace('/', '-').replace('?', '-')
    except Exception:
        print(asset)
        raise
    return '_'.join(fn.split()) + '.html'


def edit_url(asset):
    if not asset.get('file_data'):
        return None  # a node for an undefined dependency
    return f"itas://{asset['file_data']['file_path']}#{asset['id']}"


def report_to_html(asset, lookup, issues, title, write=True, dep_map=True):
    keys = {
        k: link_links(asset[k])
        for k in asset
        if not k.startswith('_') and isinstance(asset[k], str)
    }
    keys['defined_in'] = asset['file_data']['file_path']
    lists = {
        k: [link_links(i) for i in v]
        for k, v in asset.items()
        if not k.startswith('_')
        and isinstance(asset[k], list)
        and k != 'depends_on'
    }
    Link = namedtuple("Link", 'link text')
    dependencies = []
    for txt in asset.get('depends_on', []):
        id_ = txt.split()[0]
        if id_ in lookup:
            dependencies.append(
                Link(
                    html_filename(lookup[id_]),
                    lookup[id_]['type']
                    + ':'
                    + lookup[id_]['name']
                    + ' '
                    + ' '.join(txt.split()[1:]),
                )
            )
        else:
            Link('', txt)

    dependents = [
        Link(
            html_filename(lookup[id_]),
            lookup[id_]['type'] + ':' + lookup[id_]['name'],
        )
        for id_ in asset['_dependents']
        if id_ in lookup  # absent in trimmed graph maybe
    ]

    context = dict(
        asset=asset,
        lookup=lookup,
        issues=[i for i in issues.get(asset['id'], [])],
        edit_url=edit_url(asset),
        keys=keys,
        lists=lists,
        dependencies=dependencies,
        dependents=dependents,
        top="",
        dep_map=dep_map,
        generated=title.split(' updated ')[-1],
    )

    if write:
        template = get_jinja().get_template("asset_def.html")
    else:
        template = get_jinja().get_template("asset_block.html")

    html = template.render(context)

    if write:
        with open(OUTPUT_DIR + '/' + html_filename(asset), 'w') as rep:
            rep.write(html)

    return html


def add_missing_deps(assets, other, ans):
    for asset in assets:
        real_deps = [i for i in asset_dep_ids(asset) if not i.startswith('^')]
        for dep in real_deps:
            if dep not in other:
                ans.append(
                    f'  n{len(other)} [label="???", shape=doubleoctagon, '
                    f'fillcolor="{THEME["dot_err_col"]}", style=filled]'
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


def get_tooltip(asset, issues):
    tooltip = []
    # add validation issues to top of tooltip
    tooltip += ["%s %s" % (i, j) for i, j in issues.get(asset['id'], [])]
    # put asset attributes in tooltip
    tooltip.extend(
        [
            f"{k}: {v}"
            for k, v in asset.items()
            if isinstance(v, str) and not k.startswith('_')
        ]
    )
    # put tags etc. in tooltip
    for list_field in LIST_FIELDS:
        if asset.get(list_field):
            tooltip.append(list_field.upper())
            for item in asset.get(list_field, []):
                tooltip.append(f"  {item}")
    # include path to asset def. file in tooltip
    tooltip.append(f"Defined in {asset['file_data']['file_path']}")
    return tooltip


def assets_to_dot(assets, issues, title, top):
    other = {i['id']: i for i in assets}
    edit_linked = set()
    ans = [i.format(top=top, title=title) for i in THEME["dot_header"]]

    add_missing_deps(assets, other, ans)

    for _node_id, asset in enumerate(assets):
        asset['_node_id'] = f"n{_node_id}"
    for asset in assets:

        tooltip = get_tooltip(asset, issues)

        # dict of dot / graphviz node attributes
        attr = dict(
            label=dot_node_name(asset.get('name')),
            URL=top + html_filename(asset),
            target=f"_{asset['id']}",
        )
        if False:  # used to generate demo output
            attr['label'] = asset['type'].split('/')[-1]
        # `style` is compound 'shape=box, color=cyan', so key is None
        attr[None] = (ASSET_TYPE[asset["type"]].style,)
        if asset['id'] in issues:
            if any(i[0] != 'NOTE' for i in issues[asset['id']]):
                attr['style'] = 'filled'
                attr['fillcolor'] = THEME["dot_err_col"]
        # tooltip dict -> text
        attr['tooltip'] = '\\n'.join(tooltip)

        # write node to graphviz file
        ans.append(node_dot(asset['_node_id'], attr))

        # write links to graphviz file, FROM dep TO asset
        for dep in [i for i in asset_dep_ids(asset) if not i.startswith('^')]:
            attr = dict(fontcolor='#303030')
            if asset['id'] not in edit_linked:
                edit_linked.add(asset['id'])
                attr.update(
                    dict(
                        headURL=edit_url(asset),
                        headlabel='edit',
                        headtooltip='Edit',
                    )
                )
            if edit_url(other[dep]) and dep not in edit_linked:
                # i.e. not an undefined dependency
                edit_linked.add(dep)
                attr.update(
                    dict(
                        tailURL=edit_url(other[dep]),
                        taillabel='edit',
                        tailtooltip='Edit',
                    )
                )
            edge_attr = node_dot('x', attr).split(None, 1)[-1]
            ans.append(
                f"  {other[dep]['_node_id']} -> {asset['_node_id']}"
                f"{edge_attr}"
            )

    ans.append('}')
    return '\n'.join(ans)


def write_reports(assets, issues, title, archived):

    env = get_jinja()
    generated = title.split(' updated ')[-1]
    applications = [i for i in assets if i['type'].startswith('application/')]
    storage = [i for i in assets if i['type'].startswith('storage/')]
    applications.sort(key=lambda x: x['name'])
    storage.sort(key=lambda x: x['location'])
    archived.sort(key=lambda x: x['name'])
    lookup = {i['id']: i for i in assets}
    archived = [
        report_to_html(i, lookup, issues, title, write=False, dep_map=False)
        for i in archived
    ]
    for asset in assets:
        asset['_reppath'] = html_filename(asset)
        asset['_edit_url'] = edit_url(asset)
        if asset['id'] in issues:
            asset['_class'] = 'issues'
    asset_types = []
    for key, asset in ASSET_TYPE.items():
        asset_types.append(asset._asdict())
        asset_types[-1]['id'] = key
    # types of issues
    issue_counts = set(j[0] for i in issues.values() for j in i)
    # count of each type
    issue_counts = {
        i: len([j for k in issues.values() for j in k if j[0] == i])
        for i in issue_counts
    }
    context = dict(
        applications=applications,
        archived=archived,
        asset_types=asset_types,
        generated=generated,
        issue_counts=sorted((k, v) for k, v in issue_counts.items()),
        issues=issues,
        lookup={i['id']: i for i in assets},
        storage=storage,
        title=title,
        top='',
    )
    with open(f"{OUTPUT_DIR}/index.html", 'w') as out:
        out.write(env.get_template("map.html").render(context))

    for rep in (
        'asset_types',
        'storage',
        'applications',
        'archived',
        'validation',
    ):
        with open(f"{OUTPUT_DIR}/_{rep}.html", 'w') as out:
            out.write(env.get_template(f"{rep}.html").render(context))


def write_maps(assets, issues, title):

    write_map(
        base="index",
        assets=assets,
        issues=issues,
        title=title,
        leads_to=".*",
        in_field="_dependent_types",
    )
    write_map(
        base=f"_unapplied",
        assets=assets,
        issues=issues,
        title=title,
        leads_to="application/.*",
        in_field="_dependent_types",
        negate=True,
    )
    for type_ in ASSET_TYPE:
        write_map(
            base=f"_" + type_.replace('/', '_'),
            assets=assets,
            issues=issues,
            title=title,
            leads_to=type_,
            in_field="_dependent_types",
        )
    for app in [i for i in assets if i['type'].startswith('application/')]:
        write_map(
            base=f"_" + app['id'],
            assets=assets,
            issues=issues,
            title=title,
            leads_to=app['id'],
            in_field="_dependent_ids",
        )


def asset_to_svg(svg):
    """get a mapping from asset IDs to svg node IDs"""
    dom = etree.fromstring(svg.encode('utf-8'))
    nodes = dom.xpath(
        "//svg:g[@id='graph0']/svg:g",
        namespaces={
            'svg': "http://www.w3.org/2000/svg",
            'xlink': "http://www.w3.org/1999/xlink",
        },
    )
    a2s = {}
    for node in nodes:
        target = node.xpath(".//@target")
        if target:
            a2s[target[0][1:]] = node.get('id')
    return a2s


def write_map(base, assets, issues, title, leads_to, in_field, negate=False):

    use = [
        i
        for i in assets
        if any(re.search(f'^{leads_to}$', j) for j in (i.get(in_field) or []))
    ]
    if negate:
        lookup = {i['id']: i for i in assets}
        use = [i for i in assets if i not in use]
        old_len = None
        while old_len != len(use):
            for asset in list(use):
                for dep in asset_dep_ids(asset):
                    if dep in lookup and lookup[dep] not in use:
                        use.append(lookup[dep])
            print(f"Added {len(use)-(old_len or 0)}")
            old_len = len(use)

    print(f"Showing {len(use)} of {len(assets)} assets for {base}")

    top = ''
    with open(f"{OUTPUT_DIR}/{base}.dot", 'w') as out:
        out.write(assets_to_dot(use, issues, title, top))

    os.system(f"dot -Tsvg -o{OUTPUT_DIR}/{base}.svg {OUTPUT_DIR}/{base}.dot")

    generated = title.split(' updated ')[-1]
    subset = 'All assets' if base == 'index' else f'{leads_to} assets only'
    if negate:
        subset = f"Assets not leading to an asset of type {leads_to}"

    svg = open(f"{OUTPUT_DIR}/{base}.svg").read()
    asset_map = asset_to_svg(svg)
    context = dict(
        title=title,
        imap=svg,
        asset_map=json.dumps(asset_map),
        generated=generated,
        top=top,
        base=base,
        subset=subset,
    )
    with open(f"{OUTPUT_DIR}/{base}.html", 'w') as out:
        out.write(get_jinja().get_template("map.html").render(context))


def main():
    opt = get_options()
    assets = []
    for asset_file in chain.from_iterable(opt.assets):
        try:
            assets.extend(load_assets(asset_file))
        except Exception:
            print(f"Failed reading {asset_file}")
            raise

    # separate archived assets
    archived = [i for i in assets if 'archived' in i.get('tags', [])]
    assets = [i for i in assets if 'archived' not in i.get('tags', [])]

    VALIDATORS_COMPILED.update(
        {re.compile(k): v for k, v in VALIDATORS.items()}
    )
    issues = validate_assets(assets)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # add _dependent_types to each asset listing types of all dependents
    propagate_dependent(assets, output='_dependent_types', field='type')
    propagate_dependent(assets, output='_dependent_ids', field='id')
    lookup = {i['id']: i for i in assets}
    title = get_title(assets)
    for asset in assets:
        asset.setdefault('_dependents', [])  # so they all have it
        for dep in asset_dep_ids(asset):
            if dep in lookup:
                lookup[dep].setdefault('_dependents', []).append(asset['id'])
    for asset in assets:  # after all dependents recorded
        report_to_html(asset, lookup, issues, title)
    for asset in archived:
        asset.setdefault('_dependents', [])  # even these

    write_reports(assets, issues, title, archived)

    if opt.leaf_type:
        n = len(assets)
        use = [
            i
            for i in assets
            if any(
                re.search(opt.leaf_type, j)
                for j in (i.get('_dependent_types') or [])
            )
        ]
        if opt.leaf_negate:
            assets = [i for i in assets if i not in use]
        else:
            assets = use
        print(f"Showing {len(assets)} of {n} assets")

    write_maps(assets, issues, title)


if __name__ == "__main__":
    main()
