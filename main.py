"""
Game Host 主程序 (Saiblo 协议版)
连接 Saiblo Worker 和 THUAI9 GameEngine (C# DLL)
"""

import sys
import json
import time
from typing import Dict, Any, List
from saiblo_protocol import SaibloProtocol, ErrorType
from game_engine_wrapper import GameEngineWrapper

class GameHost:
    """Game Host 主类"""

    def __init__(self):
        self.wrapper = GameEngineWrapper()
        self.replay_file = None
        self.player_types = [0, 0]  # Saiblo ID 0, 1
        self.round_number = 0
        self.game_over = False

    def initialize(self):
        """初始化阶段"""
        print("[INFO] ========== 初始化阶段 ==========", file=sys.stderr)

        # 1. 读取初始化消息
        init_msg = SaibloProtocol.read_message()
        if not init_msg:
            print("[ERROR] 未收到初始化消息", file=sys.stderr)
            sys.exit(1)

        init_info = SaibloProtocol.parse_init_message(init_msg)
        print(f"[INFO] 收到初始化消息: {init_info}", file=sys.stderr)

        # 2. 打开回放文件
        try:
            self.replay_file = open(init_info["replay"], 'w', encoding='utf-8')
        except Exception as e:
            print(f"[ERROR] 无法打开回放文件: {e}", file=sys.stderr)
            sys.exit(1)

        # 3. 初始化游戏引擎
        # 注意：Saiblo 0/1 对应 C# 内部的 1/2
        self.wrapper.initialize(init_info["config"])
        self.player_types = init_info["player_list"]

        # 4. 配置双方初始棋子 (此处可根据后端约定传递默认配置)
        for saiblo_id in [0, 1]:
            # 获取默认棋子配置 (JSON 列表)
            # todo: 与后端确认默认棋子数据结构
            default_pieces = self._get_default_pieces(saiblo_id)
            # C# 接口使用 1-based ID
            self.wrapper.set_player_pieces(saiblo_id + 1, default_pieces)

        # 5. 发送回合配置给 Saiblo (超时 60s, 最大消息 4096 字节)
        SaibloProtocol.send_round_config(time=60, length=4096)

        print("[INFO] 初始化完成", file=sys.stderr)

    def _get_default_pieces(self, player_id: int) -> List[Dict]:
        """获取玩家的初始棋子配置"""
        # 示例配置，需根据 THUAI9 实际规则调整
        return [
            {"strength": 10, "intelligence": 10, "dexterity": 10, "pos": {"x": 0, "y": 0 if player_id == 0 else 14}}
        ]

    def game_loop(self):
        """游戏主循环"""
        print("[INFO] ========== 游戏开始 ==========", file=sys.stderr)

        while not self.wrapper.is_game_over():
            self.round_number += 1
            
            # 1. 引擎进入下一阶段 (更新冷却、位置等)
            self.wrapper.next_turn()

            # 2. 获取当前状态 JSON
            state_json = self.wrapper.get_state_json()
            state_data = json.loads(state_json)
            
            # 3. 写入回放文件 (每回合一行 JSON)
            self.replay_file.write(state_json + '\n')
            self.replay_file.flush()

            # 4. 发送观战消息 (给本地调试或网页播放器)
            SaibloProtocol.send_watch_info(state_json)

            # 5. 确定当前活跃玩家 (Saiblo 0/1)
            # 假设 state_data 中包含 currentPlayerId (1/2)
            csharp_pid = state_data.get("currentPlayerId", 1)
            active_saiblo_id = csharp_pid - 1

            # 6. 发送回合消息给 AI
            # content 列表长度应与 player 列表一致
            content_list = [state_json, state_json]
            SaibloProtocol.send_round_info(
                state=self.round_number,
                listen=[active_saiblo_id],
                players=[0, 1],
                content=content_list
            )

            # 7. 接收 AI 响应
            ai_msg = SaibloProtocol.read_message()
            if not ai_msg:
                print(f"[WARN] 回合 {self.round_number}: AI 未响应", file=sys.stderr)
                continue

            parsed_ai = SaibloProtocol.parse_ai_message(ai_msg)
            
            # 8. 处理 AI 异常 (TLE/RE/OLE)
            if parsed_ai["is_error"]:
                error_type = parsed_ai["error_type"]
                print(f"[ERROR] 玩家 {active_saiblo_id} 发生错误: {error_type}", file=sys.stderr)
                # 记录异常状态，可视情况提前结束或跳过
                continue

            # 9. 执行 AI 操作
            # 只有当响应的玩家是当前活跃玩家时才执行
            if parsed_ai["player"] == active_saiblo_id:
                action_json = parsed_ai["content"]
                self.wrapper.execute_action(csharp_pid, action_json)

        print("[INFO] ========== 游戏结束 ==========", file=sys.stderr)
        self.finalize()

    def finalize(self):
        """游戏结束处理"""
        winner = self.wrapper.get_winner() # 0, 1, 2
        
        # Saiblo 要求的排名信息: 0=平局或输, 1=赢 (取决于评分逻辑)
        # 这里简单映射: 1 赢则 {"0": 1, "1": 0}, 2 赢则 {"0": 0, "1": 1}
        scores = {"0": 1 if winner == 1 else 0, "1": 1 if winner == 2 else 0}
        states = ["OK", "OK"] # 默认全正常

        SaibloProtocol.send_game_end(scores, states)

        if self.replay_file:
            self.replay_file.close()

if __name__ == "__main__":
    host = GameHost()
    try:
        host.initialize()
        host.game_loop()
    except Exception as e:
        print(f"[FATAL] 运行时崩溃: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
