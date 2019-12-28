#!/bin/bash
# a script to load an asset definition in vim from an url like
# itas://some/path#some_id, invoked from a browser link via xdg-open

URL="$1"
# URL is itas://PATH#ID
URL="${URL//\/\//#}"
# URL is itas:#PATH#ID
PARTS=(${URL//#/ })
# replace # with ' ', expand (array) https://stackoverflow.com/questions/918886
FILE=${PARTS[1]}
ID=${PARTS[2]}
vim --servername VIM --remote "$FILE"
# escape, go to top of file, search "id: ID", center line
vim --servername VIM --remote-send '<Esc>gg/id: '"$ID"'<CR>zz'
