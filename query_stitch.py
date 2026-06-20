import subprocess
import json
import os

env = os.environ.copy()
env['STITCH_API_KEY'] = os.environ.get('STITCH_API_KEY', '')

p = subprocess.Popen(['npx.cmd', 'stitch-mcp-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)

# Send init
init_msg = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
}
p.stdin.write(json.dumps(init_msg) + '\n')
p.stdin.flush()

# Read init response
print(p.stdout.readline())

# Send initialized
p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + '\n')
p.stdin.flush()

# Send tools/list
tools_msg = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
}
p.stdin.write(json.dumps(tools_msg) + '\n')
p.stdin.flush()

# Read tools/list response
print(p.stdout.readline())
print(p.stdout.readline())
print(p.stdout.readline())

p.terminate()
