# IT Assets

Simply YAML parsing code to report of DB of IT assets.

DB is simply a collection of YAML files describing assets.

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

