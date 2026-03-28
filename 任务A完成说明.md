# 任务 A (Game Host) 开发完成说明及 DLL 调用指南

## 1. 任务完成概况
已完成 [game-host/main.py](game-host/main.py) 与 [game-host/game_engine_wrapper.py](game-host/game_engine_wrapper.py) 的重构。
- **通信协议**：已从 gRPC 全面切换为 Saiblo stdin/stdout 二进制协议。
- **架构切换**：游戏逻辑由 Python 脚本驱动，通过 `pythonnet` 直接调用 C# 编写的 `GameEngine` DLL。
- **异常捕获**：主循环内已集成对 AI 端的 `TLE` (超时)、`RE` (运行错误)、`OLE` (输出超限) 的识别与汇报。

## 2. 关于 `GameEngine` DLL 的调用说明

### 2.1 强制运行环境
**由于 `server.dll` 基于 `.NET 8.0` 并引用了 WebHost 堆栈，目前无法在标准的 Windows Python 环境中直接通过 `python .\main.py` 启动。**
- **现象**：实例化 `GameEngine` 时会报 `Exception.ToString() failed` 或 `ModuleNotFoundError: No module named 'Server'`。
- **原因**：DLL 中包含 Web 启动逻辑，需要完整的 ASP.NET Core Runtime 环境。
- **解决方案**：**必须在 Docker 容器（基于 `mcr.microsoft.com/dotnet/runtime:8.0`）中运行**。在那里，`pythonnet` 才能正确初始化 .NET Runtime 并加载 Web 组件。

### 2.2 核心接口约定 (反射已验证)
DLL 导出的命名空间为 `Server`，类名为 `GameEngine`。包装器已实现以下映射：

| Python 方法 | 对应 C# 方法 | 参数/返回值说明 |
| :--- | :--- | :--- |
| `initialize(config)` | `Initialize(string)` | 输入 JSON 配置字符串 |
| `next_turn()` | `NextTurn()` | 驱动回合推进 |
| `get_state_json()` | `GetStateJson()` | 返回当前全量状态 JSON |
| `execute_action(pid, act)` | `ExecuteAction(int, string)` | 执行玩家操作，PID 为 1-based |
| `is_game_over()` | `IsGameOver()` | 返回布尔值 |

## 3. 重要逻辑说明 (人员 B/C/D 必看)

### 3.1 Player ID 映射
- **Saiblo 平台**：使用 `0` 和 `1`。
- **C# DLL 内部**：使用 `1` 和 `2`。
- **处理方式**：`main.py` 中已自动进行 `+1/-1` 转换。对于 Client 开发者，只需关注 Saiblo 发送给你的 JSON 状态即可。

### 3.2 回放文件与观战
- 每一回合的 JSON 状态会自动写入回放文件，并实时通过 `send_watch_info` 发送给 Saiblo 的观战端口（ target = -1）。

## 4. 后续测试说明
完成 A 后的本地验证已受阻于 DLL 本地的宿主环境限制，后续通过人员 D 的 Docker 集成测试进行最终验收。
