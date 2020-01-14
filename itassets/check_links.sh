# Quick check that there are no broken links in the generated output
# Only checks links internal to the inventory, not external links
#
# usage:
#    bash check_links.sh <output_dir>

cd $1
python3 -m http.server &
SERVER_PID=$!
sleep 2  # give server a chance to start or wget won't connect
wget --spider -r -nd -nv -o check_links.log http://127.0.0.1:8000/index.html
cat check_links.log
echo
echo NOTE: only internal inventory links checked
kill $SERVER_PID
echo server pid $SERVER_PID killed
