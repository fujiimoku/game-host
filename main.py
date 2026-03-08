"""
Game Host 主程序
连接 Saiblo Worker 和 THUAI8 Server
"""

import sys
import subprocess
import time
import threading
from typing import Dict, Any, Optional
from saiblo_protocol import SaibloProtocol, ErrorType, EndState
from thuai8_client import THUAI8Client, convert_game_state_to_json, convert_action_from_json


class GameHost:
    """Game Host 主类"""

    def __init__(self):
        self.replay_file = None
        self.clients = {}  # saiblo_id -> THUAI8Client
        self.player_mapping = {}  # saiblo_id -> thuai8_id
        self.current_round = 0
        self.game_over = False
        self.server_process = None
        self.player_states = {0: EndState.OK, 1: EndState.OK}  # 记录玩家状态

    def start_thuai8_server(self):
        """启动 THUAI8 Server（如果需要）"""
        # 注意：在 Docker 容器中，可能需要启动 Server
        # 如果 Server 已经在运行，可以跳过这一步
        try:
            print("[INFO] 尝试启动 THUAI8 Server...", file=sys.stderr)
            # self.server_process = subprocess.Popen(
            #     ["dotnet", "server/server.dll", "--urls", "http://0.0.0.0:50051"],
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.PIPE
            # )
            # time.sleep(2)  # 等待服务器启动
            print("[INFO] THUAI8 Server 已启动", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] 启动 Server 失败（可能已在运行）: {e}", file=sys.stderr)

    def stop_thuai8_server(self):
        """停止 THUAI8 Server"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
            print("[INFO] THUAI8 Server 已停止", file=sys.stderr)

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
        self.replay_file = open(init_info["replay"], 'w')
        print(f"[INFO] 回放文件: {init_info['replay']}", file=sys.stderr)

        # 3. 启动 THUAI8 Server（如果需要）
        self.start_thuai8_server()

        # 4. 创建两个 gRPC 客户端
        player_list = init_info["player_list"]
        for saiblo_id, player_type in enumerate(player_list):
            if player_type == 0:
                print(f"[INFO] 玩家 {saiblo_id} 未连接，跳过", file=sys.stderr)
                continue

            # 创建客户端
            client = THUAI8Client("localhost:50051")
            client.connect()

            # 初始化
            init_response = client.send_init()
            thuai8_id = init_response["player_id"]

            # 保存映射
            self.clients[saiblo_id] = client
            self.player_mapping[saiblo_id] = thuai8_id

            print(f"[INFO] 玩家 {saiblo_id} (Saiblo) -> 玩家 {thuai8_id} (THUAI8)", file=sys.stderr)

            # 发送棋子配置
            piece_config = THUAI8Client.get_default_piece_config(thuai8_id)
            client.send_init_policy(thuai8_id, piece_config)

        # 5. 发送回合配置给 Saiblo
        SaibloProtocol.send_round_config(time=60, length=4096)

        print("[INFO] 初始化完成", file=sys.stderr)

    def game_loop(self):
        """游戏主循环"""
        print("[INFO] ========== 游戏循环开始 ==========", file=sys.stderr)

        # 订阅游戏状态（使用第一个客户端）
        first_client = list(self.clients.values())[0]

        try:
            for grpc_state in first_client.broadcast_game_state(first_client.player_id):
                self.current_round = grpc_state.currentRound

                print(f"[INFO] ===== 回合 {self.current_round} =====", file=sys.stderr)
                print(f"[INFO] 当前玩家: {grpc_state.currentPlayerId}", file=sys.stderr)
                print(f"[INFO] 当前棋子: {grpc_state.currentPieceID}", file=sys.stderr)
                print(f"[INFO] 游戏结束: {grpc_state.isGameOver}", file=sys.stderr)

                # 转换为 JSON
                state_json = convert_game_state_to_json(grpc_state)

                # 写入回放
                self.replay_file.write(state_json + '\n')
                self.replay_file.flush()

                # 检查游戏是否结束
                if grpc_state.isGameOver:
                    self.game_over = True
                    self.handle_game_end(grpc_state)
                    break

                # 确定当前行动的玩家（THUAI8 ID -> Saiblo ID）
                thuai8_current_player = grpc_state.currentPlayerId
                saiblo_current_player = None
                for saiblo_id, thuai8_id in self.player_mapping.items():
                    if thuai8_id == thuai8_current_player:
                        saiblo_current_player = saiblo_id
                        break

                if saiblo_current_player is None:
                    print(f"[ERROR] 无法映射玩家 ID: {thuai8_current_player}", file=sys.stderr)
                    continue

                # 发送回合消息给 Saiblo
                SaibloProtocol.send_round_info(
                    state=self.current_round,
                    listen=[saiblo_current_player],  # 只有当前玩家需要响应
                    players=[0, 1],  # 发送给所有玩家
                    content=[state_json, state_json]  # 两个玩家收到相同的状态
                )

                # 接收 AI 操作
                ai_msg = SaibloProtocol.read_message()
                if not ai_msg:
                    print("[ERROR] 未收到 AI 消息", file=sys.stderr)
                    break

                ai_info = SaibloProtocol.parse_ai_message(ai_msg)

                # 处理异常
                if ai_info["is_error"]:
                    self.handle_ai_error(ai_info)
                    break

                # 发送操作给 THUAI8
                player_id = ai_info["player"]
                action_json = ai_info["content"]

                if player_id in self.clients:
                    action = convert_action_from_json(action_json)
                    thuai8_id = self.player_mapping[player_id]
                    success = self.clients[player_id].send_action(thuai8_id, action)

                    if not success:
                        print(f"[WARN] 玩家 {player_id} 操作失败", file=sys.stderr)

        except Exception as e:
            print(f"[ERROR] 游戏循环异常: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

        print("[INFO] 游戏循环结束", file=sys.stderr)

    def handle_ai_error(self, ai_info: Dict[str, Any]):
        """处理 AI 异常"""
        player_id = ai_info["player"]
        error_type = ai_info["error_type"]

        error_names = {
            ErrorType.RE: "RE (Runtime Error)",
            ErrorType.TLE: "TLE (Time Limit Exceeded)",
            ErrorType.OLE: "OLE (Output Limit Exceeded)"
        }

        error_name = error_names.get(error_type, "Unknown Error")
        print(f"[ERROR] 玩家 {player_id} 发生异常: {error_name}", file=sys.stderr)

        # 记录玩家状态
        if error_type == ErrorType.RE:
            self.player_states[player_id] = EndState.RE
        elif error_type == ErrorType.TLE:
            self.player_states[player_id] = EndState.TLE
        elif error_type == ErrorType.OLE:
            self.player_states[player_id] = EndState.OLE

        # 发送游戏结束消息
        # 异常的玩家输掉比赛
        end_info = {str(player_id): 0, str(1 - player_id): 1}
        end_state = [self.player_states[0], self.player_states[1]]

        SaibloProtocol.send_game_end(end_info, end_state)

    def handle_game_end(self, grpc_state):
        """处理游戏结束"""
        print("[INFO] ========== 游戏结束 ==========", file=sys.stderr)

        # TODO: 需要与后端确认如何判断胜者
        # 这里使用一个简单的逻辑：根据存活的棋子数量
        winner = self.determine_winner(grpc_state)

        print(f"[INFO] 胜者: 玩家 {winner}", file=sys.stderr)

        # 构造结束信息
        if winner == -1:
            # 平局
            end_info = {"0": 0, "1": 0}
        else:
            # 有胜者
            end_info = {str(winner): 1, str(1 - winner): 0}

        end_state = [self.player_states[0], self.player_states[1]]

        # 发送结束消息
        SaibloProtocol.send_game_end(end_info, end_state)

    def determine_winner(self, grpc_state) -> int:
        """
        判断胜者

        Args:
            grpc_state: 游戏状态

        Returns:
            int: 胜者的 Saiblo ID (0 或 1)，-1 表示平局
        """
        # TODO: 需要与后端确认胜利条件
        # 这里使用一个简单的逻辑：统计存活的棋子
        alive_pieces = {0: 0, 1: 0}

        for piece in grpc_state.actionQueue:
            if piece.is_alive:
                # 将 THUAI8 team 映射到 Saiblo ID
                for saiblo_id, thuai8_id in self.player_mapping.items():
                    if piece.team == thuai8_id:
                        alive_pieces[saiblo_id] += 1
                        break

        print(f"[INFO] 存活棋子: {alive_pieces}", file=sys.stderr)

        if alive_pieces[0] > alive_pieces[1]:
            return 0
        elif alive_pieces[1] > alive_pieces[0]:
            return 1
        else:
            return -1  # 平局

    def cleanup(self):
        """清理资源"""
        print("[INFO] 清理资源...", file=sys.stderr)

        # 关闭回放文件
        if self.replay_file:
            self.replay_file.close()

        # 断开客户端连接
        for client in self.clients.values():
            client.disconnect()

        # 停止服务器
        self.stop_thuai8_server()

        print("[INFO] 清理完成", file=sys.stderr)

    def run(self):
        """运行 Game Host"""
        try:
            print("[INFO] ========== Game Host 启动 ==========", file=sys.stderr)

            # 初始化
            self.initialize()

            # 游戏循环
            self.game_loop()

        except Exception as e:
            print(f"[ERROR] Game Host 异常: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

        finally:
            # 清理
            self.cleanup()

        print("[INFO] ========== Game Host 结束 ==========", file=sys.stderr)


def main():
    """主函数"""
    game_host = GameHost()
    game_host.run()


if __name__ == "__main__":
    main()
