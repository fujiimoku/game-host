"""
THUAI8 gRPC 客户端封装
负责与 THUAI8 Server 通信
"""

import grpc
import json
import sys
from typing import Dict, Any, Optional, Iterator
import message_pb2
import message_pb2_grpc


class THUAI8Client:
    """THUAI8 gRPC 客户端"""

    def __init__(self, server_address: str = "localhost:50051"):
        """
        初始化客户端

        Args:
            server_address: 服务器地址，格式为 "host:port"
        """
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.player_id = None

    def connect(self):
        """连接到服务器"""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = message_pb2_grpc.GameServiceStub(self.channel)
            print(f"[INFO] 已连接到 THUAI8 Server: {self.server_address}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] 连接失败: {e}", file=sys.stderr)
            raise

    def disconnect(self):
        """断开连接"""
        if self.channel:
            self.channel.close()
            print(f"[INFO] 已断开连接", file=sys.stderr)

    def send_init(self, message: str = "") -> Dict[str, Any]:
        """
        发送初始化请求

        Args:
            message: 初始化消息

        Returns:
            Dict: 包含 player_id, piece_count, board 的字典
        """
        try:
            request = message_pb2._InitRequest(message=message)
            response = self.stub.SendInit(request)

            self.player_id = response.id

            print(f"[INFO] 初始化成功: player_id={self.player_id}", file=sys.stderr)

            return {
                "player_id": response.id,
                "piece_count": response.pieceCnt,
                "board": {
                    "width": response.board.width,
                    "height": response.board.height,
                    "grid": [
                        {
                            "state": cell.state,
                            "player_id": cell.playerId,
                            "piece_id": cell.pieceId
                        }
                        for cell in response.board.grid
                    ]
                }
            }
        except Exception as e:
            print(f"[ERROR] 初始化失败: {e}", file=sys.stderr)
            raise

    def send_init_policy(self, player_id: int, piece_args: list) -> bool:
        """
        发送棋子配置

        Args:
            player_id: 玩家 ID
            piece_args: 棋子配置列表

        Returns:
            bool: 是否成功
        """
        try:
            # 转换为 protobuf 格式
            proto_piece_args = []
            for arg in piece_args:
                piece_arg = message_pb2._pieceArg(
                    strength=arg.get("strength", 10),
                    intelligence=arg.get("intelligence", 10),
                    dexterity=arg.get("dexterity", 10)
                )

                # 设置装备位置
                if "equip" in arg:
                    piece_arg.equip.x = arg["equip"]["x"]
                    piece_arg.equip.y = arg["equip"]["y"]

                # 设置初始位置
                if "pos" in arg:
                    piece_arg.pos.x = arg["pos"]["x"]
                    piece_arg.pos.y = arg["pos"]["y"]

                proto_piece_args.append(piece_arg)

            request = message_pb2._InitPolicyRequest(
                playerId=player_id,
                pieceArgs=proto_piece_args
            )

            response = self.stub.SendInitPolicy(request)

            if response.success:
                print(f"[INFO] 玩家 {player_id} 棋子配置成功", file=sys.stderr)
            else:
                print(f"[ERROR] 玩家 {player_id} 棋子配置失败: {response.mes}", file=sys.stderr)

            return response.success

        except Exception as e:
            print(f"[ERROR] 发送棋子配置失败: {e}", file=sys.stderr)
            return False

    def broadcast_game_state(self, player_id: int) -> Iterator[message_pb2._GameStateResponse]:
        """
        订阅游戏状态流

        Args:
            player_id: 玩家 ID

        Yields:
            游戏状态响应
        """
        try:
            request = message_pb2._GameStateRequest(playerID=player_id)
            for state in self.stub.BroadcastGameState(request):
                yield state
        except Exception as e:
            print(f"[ERROR] 订阅游戏状态失败: {e}", file=sys.stderr)
            raise

    def send_action(self, player_id: int, action: Dict[str, Any]) -> bool:
        """
        发送玩家操作

        Args:
            player_id: 玩家 ID
            action: 操作字典

        Returns:
            bool: 是否成功
        """
        try:
            # 构造 action_set
            action_set = message_pb2._actionSet(
                playerId=player_id,
                move=action.get("move", False),
                attack=action.get("attack", False),
                spell=action.get("spell", False)
            )

            # 移动
            if action.get("move") and "move_target" in action:
                action_set.move_target.x = action["move_target"]["x"]
                action_set.move_target.y = action["move_target"]["y"]

            # 攻击
            if action.get("attack") and "attack_context" in action:
                action_set.attack_context.attacker = action["attack_context"]["attacker"]
                action_set.attack_context.target = action["attack_context"]["target"]

            # 法术
            if action.get("spell") and "spell_context" in action:
                sc = action["spell_context"]
                action_set.spell_context.caster = sc.get("caster", 0)
                action_set.spell_context.spellID = sc.get("spell_id", 0)
                action_set.spell_context.target = sc.get("target", 0)

            response = self.stub.SendAction(action_set)

            if not response.success:
                print(f"[WARN] 玩家 {player_id} 操作被拒绝: {response.mes}", file=sys.stderr)

            return response.success

        except Exception as e:
            print(f"[ERROR] 发送操作失败: {e}", file=sys.stderr)
            return False

    @staticmethod
    def get_default_piece_config(player_id: int) -> list:
        """
        获取默认棋子配置

        Args:
            player_id: 玩家 ID (1 或 2)

        Returns:
            list: 棋子配置列表
        """
        # TODO: 需要与后端确认默认配置
        # 这里使用一个简单的默认配置
        if player_id == 1:
            return [
                {
                    "strength": 10,
                    "intelligence": 10,
                    "dexterity": 10,
                    "equip": {"x": 0, "y": 0},
                    "pos": {"x": 9, "y": 6}  # 从日志看，玩家1在(9,6)
                }
            ]
        else:  # player_id == 2
            return [
                {
                    "strength": 10,
                    "intelligence": 10,
                    "dexterity": 10,
                    "equip": {"x": 0, "y": 0},
                    "pos": {"x": 10, "y": 7}  # 从日志看，玩家2在(10,7)
                }
            ]


def convert_game_state_to_json(grpc_state: message_pb2._GameStateResponse) -> str:
    """
    将 gRPC 游戏状态转换为 JSON 字符串

    Args:
        grpc_state: gRPC 游戏状态

    Returns:
        str: JSON 字符串
    """
    state_dict = {
        "round": grpc_state.currentRound,
        "current_player": grpc_state.currentPlayerId,
        "current_piece": grpc_state.currentPieceID,
        "is_over": grpc_state.isGameOver,
        "action_queue": [
            {
                "id": piece.id,
                "team": piece.team,
                "position": {"x": piece.position.x, "y": piece.position.y},
                "health": piece.health,
                "max_health": piece.max_health,
                "action_points": piece.action_points,
                "max_action_points": piece.max_action_points,
                "movement": piece.movement,
                "max_movement": piece.max_movement,
                "is_alive": piece.is_alive,
                "is_in_turn": piece.is_in_turn
            }
            for piece in grpc_state.actionQueue
        ],
        "board": {
            "width": grpc_state.board.width,
            "height": grpc_state.board.height,
            "grid": [
                {
                    "state": cell.state,
                    "player_id": cell.playerId,
                    "piece_id": cell.pieceId
                }
                for cell in grpc_state.board.grid
            ]
        }
    }

    return json.dumps(state_dict, ensure_ascii=False)


def convert_action_from_json(action_json: str) -> Dict[str, Any]:
    """
    将 JSON 字符串转换为操作字典

    Args:
        action_json: JSON 字符串

    Returns:
        Dict: 操作字典
    """
    try:
        return json.loads(action_json)
    except:
        # 如果解析失败，返回一个空操作
        return {
            "move": False,
            "attack": False,
            "spell": False
        }
