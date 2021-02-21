from dependency_types import AssetType as AT

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
        'db',
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
    # e.g. a non-containerized Django app., c.f. /infrastructure variant below
    'physical/server/service': AT(
        "A service (Django, web app. etc.) running directly"
        " on a physical server",
        'shape=pentagon, width=1.25',
        'pink',
        [],
        [],
        ['physical/server', 'resource/deployment', 'storage/.*'],
        'psvc',
    ),
    # /infrastructure denotes the "core" HTTP etc. service on a server
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
        "The source / deployment resource for an asset, "
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

# fields treated as lists on report output
LIST_FIELDS = (
    'closed_issues',
    'depends_on',
    'links',
    'notes',
    'open_issues',
    'tags',
)
