"""ctdz_agent 一键启动编排：前端(3000) + 完整后端服务。

在同一个控制台窗口内运行。按 Ctrl+C 后，所有子进程会被统一终止，
不留残留进程，控制台窗口可正常关闭。
"""

import os
import subprocess
import sys
import time
import webbrowser

REPO = r"D:\ctdz_agent"
VENV_PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")


def kill_tree(proc):
    """强制终止进程及其整棵子进程树（Windows taskkill /T /F）。"""
    if proc and proc.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
        )


def main():
    auto_stop = 0.0
    if "--auto-stop-seconds" in sys.argv:
        idx = sys.argv.index("--auto-stop-seconds")
        auto_stop = float(sys.argv[idx + 1])

    frontend = None
    backend = None
    try:
        print("[1/2] 启动前端终端 (3000)...")
        frontend = subprocess.Popen(
            ["cmd.exe", "/k", "title ctdz Frontend &&", VENV_PY, "-m", "http.server", "3000", "--bind", "127.0.0.1"],
            cwd=os.path.join(REPO, "frontend"),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

        time.sleep(2)
        try:
            webbrowser.open("http://localhost:3000")
        except Exception:
            pass

        print("[2/2] 启动 Backend 终端（含 OCR、网关和业务服务）...")
        env = os.environ.copy()
        env["PYTHONPATH"] = REPO
        backend = subprocess.Popen(
            ["cmd.exe", "/k", "title ctdz Backend &&", VENV_PY, os.path.join(REPO, "backend", "start_all.py")],
            cwd=REPO,
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

        deadline = time.time() + auto_stop if auto_stop > 0 else None
        while backend.poll() is None:
            if deadline and time.time() > deadline:
                raise KeyboardInterrupt
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n收到停止信号，正在停止所有服务...")
    finally:
        for name, proc in (("后端", backend), ("前端", frontend)):
            if proc and proc.poll() is None:
                print(f"正在停止 {name}...")
            kill_tree(proc)
        print("全部已停止，可以关闭本窗口。")


if __name__ == "__main__":
    main()
