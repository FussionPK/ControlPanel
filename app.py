from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import subprocess
import os
import psutil
import shlex
import platform
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure random key for production
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
Session(app)

# Adjust ALLOWED_COMMANDS based on OS
if platform.system() == 'Windows':
    ALLOWED_COMMANDS = ['dir', 'cd', 'type', 'echo', 'whoami']
else:  # Assume Unix-like (Linux, macOS)
    ALLOWED_COMMANDS = ['ls', 'pwd', 'cd', 'cat', 'echo', 'whoami', 'date', 'uptime']

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        logger.debug("Authentication check passed (placeholder)")
        return f(*args, **kwargs)
    return decorated

def execute_command(cmd, cwd):
    try:
        if cmd.split()[0] in ['pwd', 'cd']:  # Handle shell builtins in Python
            if cmd == 'pwd':
                return os.getcwd(), ""
            elif cmd.startswith('cd '):
                new_dir = cmd.split(maxsplit=1)[1]
                new_dir = os.path.expandvars(new_dir)
                if not os.path.isabs(new_dir):
                    new_dir = os.path.abspath(os.path.join(cwd, new_dir))
                if os.path.isdir(new_dir):
                    return f"Changed directory to {new_dir}", ""
                return "", f"No such directory: {new_dir}"
        else:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=5
            )
            return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", "Command timed out"
    except Exception as e:
        logger.error(f"Command execution failed: {str(e)}")
        return "", f"Execution failed: {str(e)}"

@app.route('/')
def home():
    if 'cwd' not in session:
        session['cwd'] = os.path.expanduser('~')
    return render_template('index.html')

@app.route('/run-command', methods=['POST'])
@require_auth
def run_command():
    data = request.get_json()
    cmd = data.get('command', '').strip()

    if not cmd:
        return jsonify({'output': '', 'error': 'No command provided'}), 400

    try:
        cmd_name = cmd.split()[0]
    except IndexError:
        return jsonify({'output': '', 'error': 'Invalid command syntax'}), 400

    if cmd_name not in ALLOWED_COMMANDS:
        return jsonify({'output': '', 'error': f'Command "{cmd_name}" not allowed'}), 403

    cwd = session.get('cwd', os.path.expanduser('~'))

    if cmd_name == 'cd':
        parts = cmd.split(maxsplit=1)
        if len(parts) == 1 or parts[1] == '~':
            new_dir = os.path.expanduser('~')
        else:
            new_dir = os.path.expandvars(parts[1])
            if not os.path.isabs(new_dir):
                new_dir = os.path.abspath(os.path.join(cwd, new_dir))

        if os.path.isdir(new_dir):
            session['cwd'] = new_dir
            return jsonify({'output': f'Changed directory to {new_dir}', 'error': ''})
        return jsonify({'output': '', 'error': f'No such directory: {new_dir}'}), 404

    output, error = execute_command(cmd, cwd)
    return jsonify({'output': output, 'error': error})

@app.route('/stats')
def stats():
    try:
        cpu = psutil.cpu_percent(interval=1.0)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/' if platform.system() != 'Windows' else 'C:\\').percent
        net_io = psutil.net_io_counters()
        net_sent = round(net_io.bytes_sent / (1024 * 1024), 2)
        net_recv = round(net_io.bytes_recv / (1024 * 1024), 2)

        if not all(isinstance(x, (int, float)) for x in [cpu, memory, disk, net_sent, net_recv]):
            raise ValueError("Invalid data from system metrics")

        logger.debug(f"Stats: CPU={cpu}, Memory={memory}, Disk={disk}, NetSent={net_sent}, NetRecv={net_recv}")
        return jsonify({
            'cpu': cpu,
            'memory': memory,
            'disk': disk,
            'net_sent': net_sent,
            'net_recv': net_recv,
        })
    except Exception as e:
        logger.error(f"Stats fetch failed: {str(e)}")
        return jsonify({'error': f'Failed to fetch stats: {str(e)}'}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    logger.debug("Shutdown endpoint called")
    try:
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            logger.warning("Shutdown not supported: Running with non-Werkzeug server or misconfigured environment")
            server_info = os.environ.get('SERVER_SOFTWARE', 'Unknown server')
            return jsonify({'error': f'Shutdown not supported: Running on {server_info}. Use Ctrl+C or stop manually'}), 501
        func()
        logger.info("Server shutting down...")
        return jsonify({'message': 'Server shutting down...'})
    except Exception as e:
        logger.error(f"Shutdown failed: {str(e)}")
        return jsonify({'error': f'Shutdown failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)  # Explicit host and port for clarity