from collections import namedtuple

AT = namedtuple(
    "AssetType",
    [
        "description",  # description of node
        "style",  # styling for node
        "color",  # color, not used
        "tags",  # node's tags
        # fields node is required to have, id, depends, type etc.
        # are assumed by default
        "fields",
        "depends",  # regex for node types on which this node type depends
        "prefix",  # short prefix for ids of nodes of this type
    ],
)
