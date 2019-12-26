# IT Assets

Simply YAML parsing code to report of DB of IT assets.

DB is simply a collection of YAML files describing assets.

## Special conventions

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
