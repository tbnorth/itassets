# IT Assets

Code to validate and graphically map a database of IT assets or other entities.

The database is simply a collection of YAML files describing assets.  Asset
types include `application/external`, `cloud/service`, `container/docker`,
`resource/deployment`, `physical/server`, `backup` etc.  Relationships are
validated, for example `container/docker` should define a dependency on an
asset of type `resource/deployment`, typically linking to the Dockerfile and
other resources needed to create the image.  Similarly a `storage/local` asset
should define dependencies on `drive` and `backup` assets.

Nodes below have their regular names replaced with the name of their type for
illustration, node names are more usually "Geoserver for bicycle app." etc.

![Example image](./img/assets.png)

Colors indicate validation failures or the presence of a `needs_work` tag.
Hovering over a node display attributes and validation issues.  Clicking on a
node opens a page reporting asset details, where links to external resources
are active.  Nodes and report pages include
`itas:///path/to/file.yaml#con_asset_id` links which can be used to [link your
favorite editor to the web view](#open-asset-definition-in-editor-from-browser).

An asset definition looks like:
```yaml
id: con_geoserver_bike
name: Bicycle app. GeoServer
description: GeoServer docker container for cycling app.
owner: Terry Brown <terrynbrown@gmail.com>
location: https://github.com/tbnorth/itassets
type: container/docker
depends_on:
 - srv_bigbox2 the server the container's running on
 - psvc_bb_apache /etc/apache/sites-enabled/010-bike_app
 - dply_geoserv_bike a link to the Dockerfile / compose / deploy repo. to make container
 - sto_store1_usr1 a link to a local storage definition
tags:
 - needs_work
 - archived
 - migrate_to_cloud
notes:
 - check with Alexis if this is still needed
open_issues:
 - separate defs from main code https://github.com/tbnorth/itassets/issues/1
closed_issues:
 - some other issue https://github.com/tbnorth/itassets/issues/11
 - etc. etc. https://github.com/tbnorth/itassets/issues/111
```
The first word (`srv_bigbox2` etc.) in the `depends_on` list is the linking ID
field, the remainder of the line is additional information.

## Running in a Docker container

```shell
docker run -it --rm \
  -v /some/path/to/assets:/inputs \
  -v /some/path/to/outputs:/outputs \
  tbnorth/itassets:latest
```
will read all the `.yaml` files in `/some/path/to/assets` and write outputs to
`/some/path/to/outputs`.

## Running from the command line

`itassets` requires [pyyaml](https://pyyaml.org/wiki/PyYAMLDocumentation) and
[graphviz - dot](https://www.graphviz.org/).  An example command line
invocation:
```shell
python3 itassets.py --assets ./some/path/*.yaml
# creates assets.dot and asset_reports folder
dot -Tpng -oassets.png -Tcmapx -oassets.map assets.dot
# creates assets.png and assets.map
cat docker/head.html assets.map docker/tail.html >index.html
```
then view index.html in your browser.  [docker/head.html](./docker/head.html)
and [docker/tail.html](./docker/tail.html) are just minimal HTML snippets to
apply the image link map to the image.

## Running in response to GitHub webhooks

This is more complicated to set up but allows regeneration of the web view of
the asset database in response to a push to a GitHub repo., or even editing of
the database on a GitHub / GitHub-Enterprise site.  The docker container can be
started like this:
```
sudo docker run -d -p 8181:8000 \
    -v /some/path0/asset_repo:/repo \
    -v /some/path1/asset_repo/assets_yml:/inputs \
    -v /some/path2:/outputs \
    -v /some/path3/ssh:/root/.ssh \
    tbnorth/itassets:latest python3 /itassets/monitor.py
```
The `python3 /itassets/monitor.py` at the end is needed to run in continuous
monitoring mode rather than the immediate command-line mode shown above.  The
`/inputs` and `/outputs` volumes function as before.  The
`/repo` volume should be the root directory of a checkout of the repo.
containing the asset data.  The container will attempt `git pull` in that
directory when it hears there's been an update.  Internally the container listens
for a POST command on port 8000, here host port 8181 is mapped to that.

The other two steps in setting up this mode are:

### Setting up the webhook on the repository

This is done in the GitHub(Enterprise) web UI.  Set the `push` event to send a
`JSON` notification to an URL that will reach the docker container.  For
example `http://example.com/hooks/asset_update` might be proxied to local port
8181 with something like (Apache):
```
<VirtualHost *:80>
    # commits to https://github.com/username/project trigger a POST
    # to http://example.com/hooks/asset_update
    ProxyPreserveHost On
    ProxyRequests Off
    ProxyPass /hooks/asset_update http://127.0.0.1:8181/
    ProxyPassReverse /hooks/asset_update http://127.0.0.1:8181/
</VirtualHost>
```

### Making the repo. pullable by the container

Depending on the access restrictions on your repo., you may have to take
special steps to allow the container to pull from it when the hook fires and
tells the container there's been a push.

One approach is to generate an ssh key pair:
```
mkdir ssh
cd ssh
ssh-keygen -f ./id_rsa
# don't use a pass phrase, it needs to be used non-interactively
```
then add this key (the `id_rsa.pub` file content) as a Deploy Key for the repo.
using the GitHub web UI (read only is fine), and make this key available to
the container as seen with the `-v /some/path3/ssh:/root/.ssh` in the above
example.

## Special conventions

### Archived tag

Assets with `archived` in their list of `tags` will be ignored during loading,
and play no role in the rest of the system.  The only way to see / change such
assets is directly editing the file containing them.

### Notes on dependencies

Only the first word (whitespace delimited character sequence) is used as the ID
for a dependency in the `depends_on` list.  So you can write more information
on the rest of the line, e.g.:
```
   depends_on:
    - con_some_webserver in /etc/apache2/sites-available/mysite
```

### Insufficient depends

Some asset A may depend on another asset B that appears to satisfy A's need for
a particular dependency to be defined, but in fact does not.  E.g. A may depend
on a web application *and* a database, either of which would satisfy A's need to
have a server/service defined.  If the complete list of dependencies is entered
at once, there's really no problem.  If, however, you want to define the
database dependency but not allow A to pass validation because you know the web
application dependency is missing, you can enter the database dependency as
follows:
```
   depends_on:
    - con_some_db INSUF
```
The `INSUF` marker indicates that the defined dependency is insufficient to
satisfy the assets required dependencies.

### Over-riding a dependency

Containers and VMs should *usually* define a `storage/.*` dependency.
Sometimes they don't need to, they can use
```
depends_on:
 - ^storage/.*
```
for those cases, the `^<pattern>` syntax can be used to skip any dependency.

### `location` field.

For applications this is typically the URL of the app.  For storage, this is
usually `machine.some.tld:/some/path/to/local/storage` or `GoogleDrive:...`
etc.

### List fields

The fields listed in the LIST_FIELDS list, currently
```python
LIST_FIELDS = 'notes', 'tags', 'links', 'open_issues', 'closed_issues'
```
get special handling, so
```yaml
tags:
 - a_tag
 - other_tag
```
is shown as
```
TAGS
  a_tag
  other_tag
```
in the asset's report page.  Unknown fields with list or dict types aren't
shown in the report.

## Open asset definition in editor from browser

[`open-itas.sh`](./itassets/open-itas.sh) can be used to open an asset definition
from the `edit` link at the bottom of the asset's info. page.  The link has a
structure like `itas:///some/path/to/assets_file.yaml#some_asset_id`.  To
install `open-itas.sh` using
[xdg-open](https://www.freedesktop.org/wiki/Software/xdg-utils/) write a
`.desktop` file like this:
```
[Desktop Entry]
Type=Application
Name=ITAS Scheme Handler
Exec=/home/tbrown/bin/open-itas.sh %u
StartupNotify=false
MimeType=x-scheme-handler/itas;
```
and put it somewhere like `~/.local/share/applications/itas.desktop`.  Then
tell the xdg system about it wit a command like:
```shell
xdg-mime default itas.desktop x-scheme-handler/itas
```
`open-itas.sh` opens the definition in a running instance of vim, but could be
modified for other editors.

If you're using a docker container to generate the inventory, the path may
be incorrect, e.g.
```
itas:///inputs/storage.yaml#drv_alt_gisbu_n0
```
instead of
```
itas:///home/me/repos/myInfrastructure/assets/storage.yaml#drv_alt_gisbu_n0
```
You can add a line to `open-itas.sh` like:
```shell
FILE=$(echo "$FILE"|sed 's%/inputs/%/home/me/repos/myInfrastructure/assets/%')
```
to fix that.   
