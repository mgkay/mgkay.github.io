"""tc_daemon — persistent Python helper for the PreToolUse hook (Fix #11).

When the hook spawns the daemon, it loads `tc_analyzer` once and serves
analyzer jobs over a TCP localhost socket. Subsequent hook invocations
connect to the existing daemon, avoiding per-call Python interpreter +
import + regex-compile costs.

Lifecycle:
  - Lazy spawn on first hook call (via spawn_if_needed).
  - Port written to ~/.claude/skills/track-changes/state/daemon.port.
  - PID written to ~/.claude/skills/track-changes/state/daemon.pid.
  - TTL self-shutdown after IDLE_TIMEOUT seconds (5 minutes).
  - Stop hook (or kill_daemon) sends a graceful shutdown command.

Wire protocol (newline-delimited JSON):
  client -> daemon: {"op": "analyze", "protocol_version": 2, "source_text": "...",
                     "payload": {...}, "tool_name": "Edit", "ftype": "md",
                     "sources": {"src.txt#L1-L4": "...sliced source..."}}
  daemon -> client: {"ok": true, "protocol_version": 2, "violations": [[ln, reason], ...],
                     "suggest_draft": false, "proposed_text": "...", "imported": [...]}
  client -> daemon: {"op": "ping"}                 -> {"ok": true, "pong": true}
  client -> daemon: {"op": "shutdown"}             -> {"ok": true}; daemon exits

Schema evolution (C5): `protocol_version` is advisory; the daemon parses
tolerantly — unknown fields are ignored, and a missing `sources` field maps
to None (the analyzer's byte-identical v1 behavior).

Each request/response is a single JSON object terminated by a newline.
"""
import os
import sys
import json
import time
import socket
import subprocess

IDLE_TIMEOUT = 300  # 5 minutes
CONNECT_TIMEOUT = 0.5
READ_TIMEOUT = 10.0


def _state_dir():
    home = os.environ.get('HOME') or os.path.expanduser('~')
    d = os.path.join(home, '.claude', 'skills', 'track-changes', 'state')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def _port_file():
    sd = _state_dir()
    return os.path.join(sd, 'daemon.port') if sd else None


def _pid_file():
    sd = _state_dir()
    return os.path.join(sd, 'daemon.pid') if sd else None


def read_port():
    pf = _port_file()
    if not pf or not os.path.isfile(pf):
        return None
    try:
        with open(pf, 'r', encoding='utf-8') as f:
            s = f.read().strip()
        return int(s) if s.isdigit() else None
    except (IOError, OSError, ValueError):
        return None


def connect(timeout=CONNECT_TIMEOUT):
    """Connect to running daemon. Return socket or None."""
    port = read_port()
    if port is None:
        return None
    try:
        s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
        s.settimeout(READ_TIMEOUT)
        return s
    except (socket.error, OSError):
        return None


def send_request(sock, request):
    """Send a JSON request, read JSON response, return parsed dict or None."""
    try:
        data = (json.dumps(request) + '\n').encode('utf-8')
        sock.sendall(data)
        # Read until newline.
        buf = b''
        while b'\n' not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
            if len(buf) > 50 * 1024 * 1024:  # 50MB safety cap
                return None
        line, _, _ = buf.partition(b'\n')
        return json.loads(line.decode('utf-8'))
    except (socket.error, OSError, ValueError):
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass


def spawn_if_needed(python_cmd=None):
    """Spawn the daemon as a detached background process if not running.
    Returns True if a daemon is reachable after this call."""
    s = connect()
    if s is not None:
        s.close()
        return True
    # Spawn.
    if python_cmd is None:
        python_cmd = sys.executable or 'python'
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tc_daemon.py')
    try:
        # Detach so the daemon outlives this client.
        if os.name == 'nt':
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            subprocess.Popen(
                [python_cmd, script, '--serve'],
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, close_fds=True,
            )
        else:
            subprocess.Popen(
                [python_cmd, script, '--serve'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
                close_fds=True,
            )
    except (OSError, Exception):
        return False
    # Poll for port file (daemon startup takes a moment).
    for _ in range(40):  # up to ~2 seconds
        time.sleep(0.05)
        s = connect()
        if s is not None:
            s.close()
            return True
    return False


def kill_daemon():
    """Send graceful shutdown to a running daemon, if any."""
    s = connect()
    if s is None:
        return
    send_request(s, {'op': 'shutdown'})
    # Remove stale state files.
    pf = _port_file(); pid_f = _pid_file()
    for f in (pf, pid_f):
        try:
            if f and os.path.isfile(f):
                os.remove(f)
        except OSError:
            pass


def _serve():
    """Run the daemon loop. Listens on 127.0.0.1:ephemeral, writes port to
    state file, processes one request at a time, self-shutdown on idle."""
    # Late import: tc_analyzer + tc_audit pull in `re` + `difflib` + module
    # state. Pay the import cost ONCE per daemon.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tc_analyzer  # noqa: E402
    import tc_audit     # noqa: E402  Fix #13

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', 0))
    srv.listen(8)
    port = srv.getsockname()[1]
    sd = _state_dir()
    if sd:
        try:
            with open(os.path.join(sd, 'daemon.port'), 'w', encoding='utf-8') as f:
                f.write(str(port))
            with open(os.path.join(sd, 'daemon.pid'), 'w', encoding='utf-8') as f:
                f.write(str(os.getpid()))
        except (IOError, OSError):
            pass

    srv.settimeout(IDLE_TIMEOUT)
    running = True
    while running:
        try:
            conn, _addr = srv.accept()
        except socket.timeout:
            break  # idle TTL expired
        except (socket.error, OSError):
            break
        conn.settimeout(READ_TIMEOUT)
        try:
            buf = b''
            while b'\n' not in buf:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 50 * 1024 * 1024:
                    break
            line, _, _ = buf.partition(b'\n')
            if not line:
                conn.close(); continue
            try:
                req = json.loads(line.decode('utf-8'))
            except ValueError:
                conn.sendall(b'{"ok":false,"error":"bad_json"}\n')
                conn.close(); continue
            op = req.get('op', '')
            if op == 'ping':
                conn.sendall(b'{"ok":true,"pong":true}\n')
            elif op == 'shutdown':
                conn.sendall(b'{"ok":true}\n')
                running = False
            elif op == 'analyze':
                try:
                    # Tolerant parse: unknown fields ignored; missing `sources`
                    # -> None (the analyzer's byte-identical v1 path). C5.
                    sources = req.get('sources', None)
                    result = tc_analyzer.analyze(
                        req.get('source_text', ''),
                        req.get('payload', {}),
                        req.get('tool_name', ''),
                        req.get('ftype', ''),
                        sources=sources,
                    )
                    resp = {
                        'ok': True,
                        'protocol_version': 2,
                        'violations': [list(v) for v in result['violations']],
                        'suggest_draft': bool(result['suggest_draft']),
                        'proposed_text': result.get('proposed_text', ''),
                        'imported': result.get('imported', []),
                    }
                    conn.sendall((json.dumps(resp) + '\n').encode('utf-8'))
                except Exception as e:
                    conn.sendall((json.dumps({'ok': False, 'error': str(e)}) + '\n').encode('utf-8'))
            elif op == 'audit':
                # Fix #13: PostToolUse audit log + cache update.
                try:
                    result = tc_audit.record(
                        req.get('source_text', ''),
                        req.get('tool_name', ''),
                        req.get('ftype', ''),
                        req.get('abs_file_path', ''),
                        req.get('log_path', ''),
                        req.get('cache_path', ''),
                        req.get('rel_path_for_log', ''),
                    )
                    resp = {
                        'ok': True,
                        'introduced': len(result.get('introduced', [])),
                        'resolved': len(result.get('resolved', [])),
                        'imported': len(result.get('imported', [])),
                        'lineage': len(result.get('lineage', [])),
                        'wrote_log': bool(result.get('wrote_log', False)),
                    }
                    conn.sendall((json.dumps(resp) + '\n').encode('utf-8'))
                except Exception as e:
                    conn.sendall((json.dumps({'ok': False, 'error': str(e)}) + '\n').encode('utf-8'))
            else:
                conn.sendall(b'{"ok":false,"error":"unknown_op"}\n')
        except (socket.error, OSError):
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # Cleanup state files.
    if sd:
        for fn in ('daemon.port', 'daemon.pid'):
            try:
                os.remove(os.path.join(sd, fn))
            except OSError:
                pass


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--serve':
        _serve()
    elif len(sys.argv) > 1 and sys.argv[1] == '--stop':
        kill_daemon()
