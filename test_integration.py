"""
本地集成测试：同时启动 game-host 和两个 client，模拟完整对局流程。
运行方式：python test_integration.py
"""
import subprocess
import struct
import json
import sys
import os
import threading

GAME_HOST_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.join(GAME_HOST_DIR, "..", "THUAI9-Backend", "client", "client")


# ========== 协议工具 ==========

def pack_to_logic(data: dict) -> bytes:
    """judger -> logic: [4字节长度] + [JSON]"""
    content = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(content)) + content


def read_from_logic(pipe) -> dict | None:
    """logic -> judger: [4字节长度] + [4字节target(signed)] + [JSON]"""
    header = pipe.read(8)
    if not header or len(header) < 8:
        return None
    length, target = struct.unpack(">Ii", header)
    data = pipe.read(length)
    if len(data) < length:
        return None
    msg = json.loads(data.decode("utf-8"))
    msg["_target"] = target
    return msg


def pack_to_client(data: dict) -> bytes:
    """judger -> client: [4字节长度] + [JSON]"""
    content = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(content)) + content


def read_from_client(pipe) -> dict | None:
    """client -> judger: [4字节长度] + [JSON]"""
    header = pipe.read(4)
    if not header or len(header) < 4:
        return None
    length = struct.unpack(">I", header)[0]
    data = pipe.read(length)
    if len(data) < length:
        return None
    return json.loads(data.decode("utf-8"))


# ========== stderr 转发 ==========

def pipe_stderr(pipe, prefix):
    for line in pipe:
        sys.stdout.write(f"{prefix} {line.decode('utf-8', errors='replace')}")
        sys.stdout.flush()


# ========== 主测试逻辑 ==========

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", action="store_true", help="使用 Docker 容器运行")
    args = parser.parse_args()

    if args.docker:
        host_cmd = ["docker", "run", "-i", "--rm", "-e", "USE_MOCK_DLL=0", "thuai9-game-host"]
        client0_cmd = ["docker", "run", "-i", "--rm", "thuai9-client", "python3", "-u", "main.py", "--strategy", "aggressive", "--player-id", "0"]
        client1_cmd = ["docker", "run", "-i", "--rm", "thuai9-client", "python3", "-u", "main.py", "--strategy", "defensive", "--player-id", "1"]
        host_cwd = None
        client_cwd = None
    else:
        host_cmd = [sys.executable, "-u", "main.py"]
        client0_cmd = [sys.executable, "-u", "main.py", "--strategy", "aggressive", "--player-id", "0"]
        client1_cmd = [sys.executable, "-u", "main.py", "--strategy", "defensive", "--player-id", "1"]
        host_cwd = GAME_HOST_DIR
        client_cwd = CLIENT_DIR

    print("[TEST] 启动 game-host...")
    host = subprocess.Popen(
        host_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=host_cwd,
    )
    threading.Thread(target=pipe_stderr, args=(host.stderr, "[HOST]"), daemon=True).start()

    print("[TEST] 启动 client 0 (aggressive)...")
    client0 = subprocess.Popen(
        client0_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=client_cwd,
    )
    threading.Thread(target=pipe_stderr, args=(client0.stderr, "[C0]"), daemon=True).start()

    print("[TEST] 启动 client 1 (defensive)...")
    client1 = subprocess.Popen(
        client1_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=client_cwd,
    )
    threading.Thread(target=pipe_stderr, args=(client1.stderr, "[C1]"), daemon=True).start()

    clients = [client0, client1]

    # 1. 发送初始化消息给 game-host
    replay_path = "/tmp/replay.json" if args.docker else os.path.join(GAME_HOST_DIR, "replay.json")
    init_msg = {
        "player_list": [1, 1],
        "replay": replay_path,
        "config": {}
    }
    host.stdin.write(pack_to_logic(init_msg))
    host.stdin.flush()
    print("[TEST] 已发送初始化消息")

    # 2. 读取回合配置 (state=0)
    msg = read_from_logic(host.stdout)
    assert msg and msg.get("state") == 0, f"期望回合配置，收到: {msg}"
    print(f"[TEST] 收到回合配置: time={msg.get('time')}s, length={msg.get('length')}")

    # 3. 游戏循环
    max_rounds = 200
    for round_num in range(1, max_rounds + 1):
        # 读取 host 发出的消息（可能是观战消息或回合消息）
        msg = read_from_logic(host.stdout)
        if msg is None:
            print("[TEST] host 管道关闭")
            break

        print(f"[TEST] 收到 host 消息: target={msg.get('_target')}, state={msg.get('state')}, keys={list(msg.keys())}")

        # 跳过观战消息 (target=-1)
        while msg and msg.get("_target") == -1:
            print(f"[TEST] 跳过观战消息")
            msg = read_from_logic(host.stdout)
            if msg:
                print(f"[TEST] 收到 host 消息: target={msg.get('_target')}, state={msg.get('state')}, keys={list(msg.keys())}")

        if msg is None:
            break

        state = msg.get("state")

        # 游戏结束
        if state == -1:
            print(f"[TEST] 游戏结束: end_info={msg.get('end_info')}, end_state={msg.get('end_state')}")
            break

        listen = msg.get("listen", [])
        players = msg.get("player", [0, 1])
        content_list = msg.get("content", ["", ""])

        print(f"[TEST] 回合 {state}: listen={listen}")

        # 转发状态给两个 client（每个 client 只收到自己视角的消息）
        for pid in [0, 1]:
            client_msg = {
                "state": state,
                "listen": listen,
                "player": players,
                "content": content_list,
            }
            clients[pid].stdin.write(pack_to_client(client_msg))
            clients[pid].stdin.flush()

        # 只从 listen 中的 client 读取响应
        for pid in listen:
            if pid > 1:
                continue
            ai_resp = read_from_client(clients[pid].stdout)
            if ai_resp is None:
                print(f"[TEST] client {pid} 无响应，发送空动作")
                ai_resp = {"player": pid, "content": json.dumps({"move": False, "attack": False, "spell": False})}

            # 转发给 host
            host.stdin.write(pack_to_logic(ai_resp))
            host.stdin.flush()
            print(f"[TEST] 转发 client {pid} 的行动")

    # 清理
    for proc in [host, client0, client1]:
        try:
            proc.stdin.close()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

    print("[TEST] 完成")


if __name__ == "__main__":
    import io
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output.txt")
    with open(log_path, "w", encoding="utf-8") as log_file:
        # 同时输出到终端和文件
        class Tee:
            def __init__(self, *streams):
                self.streams = streams
            def write(self, data):
                for s in self.streams:
                    s.write(data)
            def flush(self):
                for s in self.streams:
                    s.flush()
        orig_stdout = sys.stdout
        sys.stdout = Tee(orig_stdout, log_file)
        try:
            main()
        finally:
            sys.stdout = orig_stdout
    print(f"[TEST] 日志已保存到 {log_path}")
