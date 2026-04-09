import json
import traceback
import os
from game_engine_wrapper import GameEngineWrapper

def test_engine():
    print("🚀 [测试开始] 初始化 GameEngine (USE_MOCK_DLL={})".format(os.environ.get('USE_MOCK_DLL', '0')))
    try:
        engine = GameEngineWrapper()
        
        # 1. 初始化
        engine.initialize({"random_seed": 42})
        print("✅ 初始化成功")

        # 2. 配置玩家棋子
        pieces = [{'strength': 10, 'intelligence': 10, 'dexterity': 10, 'equip': {'x': 1, 'y': 2}, 'pos': {'x': 5, 'y': 2}}]
        
        print("⏳ 正在调用 SetPlayerPieces...")
        result = engine.set_player_pieces(0, pieces)
        print(f"👉 SetPlayerPieces(0) 返回值: {result}")
        if result is False or result is None:
            print("⚠️ 警告: SetPlayerPieces 返回了异常值，请对照测试文档排查 C# 内部序列化问题！")

        # 3. 推进回合
        print("⏳ 正在调用 NextTurn...")
        engine.next_turn()
        state_json = engine.get_state_json()
        
        if state_json:
            state = json.loads(state_json)
            print(f"✅ 成功获取状态 JSON: 回合 {state.get('currentRound', 'N/A')}")
        else:
            print("❌ 获取状态为空！")

    except Exception as e:
        print(f"❌ [测试失败] 出现异常:")
        traceback.print_exc()

if __name__ == "__main__":
    test_engine()