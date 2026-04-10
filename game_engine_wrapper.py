import sys
import json
import os

GameEngineType = None

USE_MOCK = os.environ.get("USE_MOCK_DLL", "0") == "1"

if not USE_MOCK:
    try:
        import pythonnet
        pythonnet.load("coreclr")
        import clr

        # 获取 DLL 所在的绝对路径
        DLL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server")
        if DLL_DIR not in sys.path:
            sys.path.append(DLL_DIR)

        clr.AddReference("server")
        import Server
        GameEngineType = Server.GameEngine

        # 关键：把 C# Console.Out 重定向到 stderr，
        # 防止 C# 的调试日志污染 stdout（Saiblo 二进制协议流）
        import System
        System.Console.SetOut(System.Console.Error)

        print("[DEBUG] C# DLL loaded successfully", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] 加载 C# DLL 失败，回退 Mock 模式: {e}", file=sys.stderr)
        USE_MOCK = True

class MockGameEngine:
    def __init__(self):
        self.round = 0
    def Initialize(self, j): print(f"[MOCK] Init", file=sys.stderr)
    def SetPlayerPieces(self, p, j): return True
    def NextTurn(self): self.round += 1
    def GetStateJson(self):
        pid = (self.round % 2) + 1  # 1 or 2
        pieces = [
            {"id": 0, "team": 1, "health": 50, "max_health": 50,
             "physical_resist": 8, "magic_resist": 10, "physical_damage": 18, "magic_damage": 0,
             "action_points": 2, "max_action_points": 2, "spell_slots": 1, "max_spell_slots": 1,
             "movement": 15.0, "max_movement": 15.0, "strength": 10, "dexterity": 10, "intelligence": 10,
             "position": {"x": 5, "y": 2}, "height": 0, "attack_range": 5, "spell_range": 0.0,
             "is_alive": True, "is_in_turn": pid == 1, "is_dying": False,
             "deathRound": -1, "queue_index": 0, "spell_list": []},
            {"id": 1, "team": 2, "health": 50, "max_health": 50,
             "physical_resist": 8, "magic_resist": 10, "physical_damage": 18, "magic_damage": 0,
             "action_points": 2, "max_action_points": 2, "spell_slots": 1, "max_spell_slots": 1,
             "movement": 15.0, "max_movement": 15.0, "strength": 10, "dexterity": 10, "intelligence": 10,
             "position": {"x": 5, "y": 12}, "height": 0, "attack_range": 5, "spell_range": 0.0,
             "is_alive": True, "is_in_turn": pid == 2, "is_dying": False,
             "deathRound": -1, "queue_index": 1, "spell_list": []},
        ]
        board = {
            "width": 10, "height": 15, "boarder": 7,
            "grid": [{"state": 1, "playerId": -1, "pieceId": -1} for _ in range(150)],
            "height_map": [0] * 150,
        }
        return json.dumps({
            "currentRound": self.round,
            "currentPlayerId": pid,
            "currentPieceID": pid - 1,  # piece id 0 for team1, 1 for team2
            "isGameOver": self.round >= 5,
            "actionQueue": pieces,
            "board": board,
            "delayedSpells": [],
        })
    def ExecuteAction(self, p, j): return True
    def IsGameOver(self): return self.round >= 5
    def GetWinner(self): return 1
    def GetReplayJson(self): return "[]"

class GameEngineWrapper:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock or USE_MOCK or (GameEngineType is None)
        if self.use_mock:
            print("[DEBUG] Using Mock GameEngine", file=sys.stderr)
            self.engine = MockGameEngine()
        else:
            import System
            self.engine = System.Activator.CreateInstance(GameEngineType)

    def initialize(self, config): self.engine.Initialize(json.dumps(config))
    def set_player_pieces(self, pid, p): self.engine.SetPlayerPieces(pid, json.dumps(p))
    def next_turn(self): self.engine.NextTurn()
    def get_state_json(self): return self.engine.GetStateJson()
    def execute_action(self, pid, act): return self.engine.ExecuteAction(pid, act)
    def is_game_over(self): return self.engine.IsGameOver()
    def get_winner(self): return self.engine.GetWinner()
    def get_replay_json(self): return self.engine.GetReplayJson()

if __name__ == "__main__":
    w = GameEngineWrapper(use_mock=True)
    w.initialize({})
    print(w.get_state_json())