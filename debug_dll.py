import clr
import sys
import os

dll_path = r'f:\Uni\s\2026_1春\Project：THUAI9通信\THUAI9-Backend\server\server\server\publish\server.dll'
clr.AddReference(dll_path)

import System
from System import Activator, AppDomain

def check_dll():
    try:
        # 显式加载所有可能的依赖 DLL 到当前域名
        publish_dir = r'f:\Uni\s\2026_1春\Project：THUAI9通信\THUAI9-Backend\server\server\server\publish'
        for f in os.listdir(publish_dir):
            if f.endswith('.dll') and f != 'server.dll':
                try:
                    clr.AddReference(os.path.join(publish_dir, f))
                except:
                    pass

        assm = [a for a in AppDomain.CurrentDomain.GetAssemblies() if 'server' in a.FullName.lower()][0]
        ge_type = assm.GetType('Server.GameEngine')
        if ge_type is None:
            print("Could not find type Server.GameEngine")
            return

        print(f"Found Type: {ge_type.FullName}")
        
        # 检查静态字段或构造函数是否需要参数
        ctors = ge_type.GetConstructors()
        print(f"Constructors count: {len(ctors)}")
        
        try:
            # 尝试最基础的实例化
            print("Attempting Activator.CreateInstance...")
            ge_instance = Activator.CreateInstance(ge_type)
            print("Successfully instantiated GameEngine!")
        except Exception as e:
            print(f"Activator failed: {e}")
            if hasattr(e, 'InnerException') and e.InnerException:
                print(f"Inner Exception: {e.InnerException}")
            # 如果是 WebHost 相关的，尝试在 GameEngine 系统环境变量中注入需要的路径
            os.environ["ASPNETCORE_ENVIRONMENT"] = "Development"
            print("Set ASPNETCORE_ENVIRONMENT=Development and retrying...")
            try:
                ge_instance = Activator.CreateInstance(ge_type)
                print("Success after env set!")
            except Exception as e2:
                 print(f"Still failed: {e2}")

    except Exception as e:
        print(f"Error during check: {e}")

if __name__ == "__main__":
    check_dll()
