"""
monitor.py - very simple github webhook receiver

Terry N. Brown terrynbrown@gmail.com Sat 04 Apr 2020 09:30:09 PM NZDT
"""

import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler


class MyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        print(data)
        data = json.loads(data)
        print(data)
        cmd = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
        cmd = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        branch, err = cmd.communicate()
        branch = branch.decode('utf-8').strip()
        print(f"Got post, monitoring {branch}")
        cmd = ['git', '-C', '/input', 'pull']
        cmd = subprocess.Popen(cmd)
        out, err = cmd.communicate()
        self.send_response(200)
        self.end_headers()


def main():
    httpd = HTTPServer(('', 8000), MyHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
