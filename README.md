# THUAI9 Game Host

## 1. 简介
Game Host 是 THUAI9 的核心调度程序，负责连接 Saiblo 评测平台与游戏逻辑引擎（C# DLL）。

## 2. 核心架构
- **语言**：Python 3.11+
- **关键技术**：
  - `pythonnet`：用于在 Python 中直接调用 C# 编写的 `GameEngine.dll`。
  - `Saiblo Protocol`：基于 stdin/stdout 的二进制协议与评测机通信。

## 3. 文件说明
- `main.py`：主程序，负责游戏循环、状态同步及 AI 指令转发。
- `game_engine_wrapper.py`：针对 C# DLL 的 Python 封装层，支持 Mock 调试模式。
- `saiblo_protocol.py`：Saiblo 平台底层通信协议实现。
- `Dockerfile`：用于构建标准的部署环境（包含 .NET 8.0 运行时）。

## 4. 本地调试
由于 `GameEngine.dll` 依赖 .NET WebHost 环境，本地直接运行可能由于缺少宿主环境而报错。
可以通过环境变量开启 Mock 模式进行协议逻辑联调：

```powershell
$env:USE_MOCK_DLL="1"; python main.py
```

## 5. 依赖安装
```bash
pip install -r requirements.txt
```