import clr
import sys
import json
import os

# 获取 DLL 所在的绝对路径
DLL_DIR = r"f:\Uni\s\2026_1春\Project：THUAI9通信\THUAI9-Backend\server\server\server\publish"
if DLL_DIR not in sys.path:
    sys.path.append(DLL_DIR)

# 加载 DLL
try:
    if os.environ.get("USE_MOCK_DLL", "0") == "0":
        clr.AddReference("server")
        import Server
        GameEngineType = Server.GameEngine
    else:
        GameEngineType = None
except Exception:
    GameEngineType = None

class MockGameEngine:
    def __init__(self):
        self.round = 0
    def Initialize(self, j): print(f"[MOCK] Init", file=sys.stderr)
    def SetPlayerPieces(self, p, j): return True
    def NextTurn(self): self.round += 1
    def GetStateJson(self):
        return json.dumps({"currentRound": self.round, "currentPlayerId": (self.round % 2) + 1, "isGameOver": self.round >= 5})
    def ExecuteAction(self, p, j): return True
    def IsGameOver(self): return self.round >= 5
    def GetWinner(self): return 1
    def GetReplayJson(self): return "[]"

class GameEngineWrapper:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock or (GameEngineType is None) or (os.environ.get("USE_MOCK_DLL", "0") == "1")
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