"""
Saiblo 平台通信协议实现
负责通过 stdin/stdout 与 Saiblo Worker 通信
"""

import sys
import struct
import json
from typing import Dict, Any, Optional


class SaibloProtocol:
    """Saiblo 通信协议"""

    @staticmethod
    def read_message() -> Optional[Dict[str, Any]]:
        """
        从 stdin 读取消息

        消息格式: [4字节长度(大端序)] + [JSON内容]

        Returns:
            Dict: 解析后的 JSON 对象，如果读取失败返回 None
        """
        try:
            # 读取 4 字节长度头
            length_bytes = sys.stdin.buffer.read(4)
            if not length_bytes or len(length_bytes) < 4:
                return None

            # 解析长度（大端序）
            length = struct.unpack('>I', length_bytes)[0]

            # 读取消息体
            data_bytes = sys.stdin.buffer.read(length)
            if len(data_bytes) < length:
                print(f"[ERROR] 期望读取 {length} 字节，实际读取 {len(data_bytes)} 字节", file=sys.stderr)
                return None

            # 解析 JSON
            data_str = data_bytes.decode('utf-8')
            return json.loads(data_str)

        except Exception as e:
            print(f"[ERROR] 读取消息失败: {e}", file=sys.stderr)
            return None

    @staticmethod
    def write_message(data: Dict[str, Any], target: int = 0):
        """
        向 stdout 写入消息

        消息格式: [4字节长度] + [4字节目标] + [JSON内容]

        Args:
            data: 要发送的数据（字典）
            target: 目标 ID（0=judger, -1=观战, >=0=特定玩家）
        """
        try:
            # 序列化为 JSON
            content = json.dumps(data, ensure_ascii=False).encode('utf-8')
            length = len(content)

            # 构造头部: 4字节长度 + 4字节目标
            # 注意: target 为 -1 时表示观战，使用 'i' (signed) 或先处理为 unsigned
            header = struct.pack('>Ii', length, target)

            # 写入
            sys.stdout.buffer.write(header)
            sys.stdout.buffer.write(content)
            sys.stdout.buffer.flush()

        except Exception as e:
            print(f"[ERROR] 写入消息失败: {e}", file=sys.stderr)

    @staticmethod
    def send_round_config(time: int, length: int):
        """
        发送回合配置

        Args:
            time: 超时时间（秒）
            length: 最大消息长度（字节）
        """
        config = {
            "state": 0,
            "time": time,
            "length": length
        }
        SaibloProtocol.write_message(config)
        print(f"[INFO] 发送回合配置: time={time}s, length={length}bytes", file=sys.stderr)

    @staticmethod
    def send_round_info(state: int, listen: list, players: list, content: list):
        """
        发送回合消息

        Args:
            state: 回合编号（从1开始）
            listen: 需要响应的玩家列表
            players: 接收消息的玩家列表
            content: 发送给每个玩家的内容（JSON字符串列表）
        """
        round_info = {
            "state": state,
            "listen": listen,
            "player": players,
            "content": content
        }
        SaibloProtocol.write_message(round_info)
        print(f"[INFO] 发送回合 {state}: listen={listen}", file=sys.stderr)

    @staticmethod
    def send_watch_info(watch_content: str):
        """
        发送观战消息

        Args:
            watch_content: 观战内容
        """
        watch_info = {"watch": watch_content}
        SaibloProtocol.write_message(watch_info, target=-1)

    @staticmethod
    def send_game_end(end_info: Dict[str, int], end_state: list):
        """
        发送游戏结束消息

        Args:
            end_info: 排名信息，例如 {"0": 1, "1": 0} 表示玩家0第1名，玩家1第0名
            end_state: 结束状态列表，例如 ["OK", "OK"] 或 ["OK", "TLE"]
        """
        game_end = {
            "state": -1,
            "end_info": json.dumps(end_info),
            "end_state": json.dumps(end_state)
        }
        SaibloProtocol.write_message(game_end)
        print(f"[INFO] 发送游戏结束: {end_info}, {end_state}", file=sys.stderr)

    @staticmethod
    def parse_init_message(msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析初始化消息

        Args:
            msg: 原始消息

        Returns:
            Dict: 包含 player_list, replay, config 的字典
        """
        return {
            "player_list": msg.get("player_list", [1, 1]),
            "replay": msg.get("replay", "/tmp/replay.json"),
            "config": msg.get("config", {})
        }

    @staticmethod
    def parse_ai_message(msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 AI 消息

        Args:
            msg: 原始消息

        Returns:
            Dict: 包含 player, content, is_error 的字典
        """
        player = msg.get("player", -1)
        content = msg.get("content", "")

        # 检查是否是异常消息
        if player == -1:
            # 异常消息格式: {"player": -1, "content": "{\"player\": 0, \"error\": 1}"}
            try:
                error_info = json.loads(content)
                return {
                    "player": error_info.get("player", -1),
                    "content": "",
                    "is_error": True,
                    "error_type": error_info.get("error", 0)  # 0=RE, 1=TLE, 2=OLE
                }
            except:
                return {
                    "player": -1,
                    "content": content,
                    "is_error": True,
                    "error_type": 0
                }
        else:
            # 正常消息
            return {
                "player": player,
                "content": content,
                "is_error": False,
                "error_type": None
            }


# 错误类型常量
class ErrorType:
    RE = 0   # Runtime Error
    TLE = 1  # Time Limit Exceeded
    OLE = 2  # Output Limit Exceeded


# 结束状态常量
class EndState:
    OK = "OK"
    RE = "RE"
    TLE = "TLE"
    OLE = "OLE"
    IA = "IA"  # Illegal Action
