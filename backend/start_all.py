import subprocess
import sys
import time
import os
import socket
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")


def project_path(path: str | Path) -> Path:
    """Resolve a project-relative path independently of the caller's cwd."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def build_service_environment(port):
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in (str(PROJECT_ROOT), existing_pythonpath) if item
    )
    env["API_PORT"] = str(port)
    return env


def is_port_listening(port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def start_neo4j() -> subprocess.Popen | None:
    """Start the local Neo4j dependency before the graph API on Windows."""
    if is_port_listening(7687):
        print("Neo4j already running on port 7687.")
        return None
    if os.name != "nt":
        raise RuntimeError("Neo4j is not listening on port 7687; start it before the backend.")

    neo4j_home = Path(os.getenv("NEO4J_HOME", r"D:\Neo4j\server\neo4j-community-5.26.6"))
    launcher = neo4j_home / "bin" / "neo4j.bat"
    if not launcher.exists():
        raise RuntimeError(f"Neo4j launcher not found: {launcher}")

    env = os.environ.copy()
    java_home = Path(env.get("JAVA_HOME", ""))
    if not (java_home / "bin" / "java.exe").exists():
        candidates = [
            Path(r"C:\Program Files\Java\jdk-24"),
            *Path(r"C:\Program Files\Eclipse Adoptium").glob("jdk-*"),
            *Path(r"D:\Java").glob("jdk-*"),
        ]
        java_home = next((path for path in candidates if (path / "bin" / "java.exe").exists()), Path())
    if not java_home or not (java_home / "bin" / "java.exe").exists():
        raise RuntimeError("A Java runtime for Neo4j was not found.")
    env["JAVA_HOME"] = str(java_home)
    env["PATH"] = os.pathsep.join((str(java_home / "bin"), env.get("PATH", "")))

    log_path = project_path("backend/logs/Neo4j.log")
    log_file = open(log_path, "w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            ["cmd.exe", "/c", str(launcher), "console"],
            cwd=str(neo4j_home),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    finally:
        log_file.close()

    deadline = time.time() + 45
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Neo4j exited during startup; see {log_path}")
        if is_port_listening(7687):
            print(f"Neo4j ready. Log: {log_path}")
            return process
        time.sleep(1)
    process.terminate()
    raise RuntimeError(f"Neo4j did not become ready within 45 seconds; see {log_path}")


def start_service(name, script_path, port, log_dir="backend/logs"):
    print(f"Starting {name} on port {port}...")
    log_directory = project_path(log_dir)
    log_directory.mkdir(parents=True, exist_ok=True)
    log_file_path = log_directory / f"{name.replace(' ', '_')}.log"
    log_file = open(log_file_path, "w", encoding="utf-8")
    try:
        env = build_service_environment(port)
        process = subprocess.Popen(
            [sys.executable, str(project_path(script_path))],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    finally:
        log_file.close()
    time.sleep(3)
    print(f"  日志文件: {log_file_path}")
    return process

def main():
    services = [
        ("Knowledge Graph Service", "backend/services/knowledge_graph_service/main.py", 8007),
        ("OCR Service", "backend/services/handwriting_ocr_service/app/main.py", 8089),
        ("Analysis Service", "backend/services/analysis_service/main.py", 8081),
        ("Error Analysis Service", "backend/services/error_analysis_service/main.py", 8082),
        ("Knowledge Service", "backend/services/knowledge_service/main.py", 8083),
        ("Teaching Service", "backend/services/teaching_service/main.py", 8084),
        ("Teacher Service", "backend/services/teacher_service/main.py", 8090),
        ("State Service", "backend/services/state_service/main.py", 8085),
        ("Review Scheduler", "backend/services/review_service/scheduler.py", 8086),
        ("Review Service", "backend/services/review_service/main.py", 8087),
        ("API Gateway", "backend/api_gateway/app.py", 8000)
    ]
    
    processes = []
    
    try:
        neo4j_process = start_neo4j()
        if neo4j_process is not None:
            processes.append(("Neo4j", neo4j_process))
        print("Initializing database...")
        subprocess.run(
            [sys.executable, str(project_path("backend/tools/init_sqlite_database.py"))],
            cwd=str(PROJECT_ROOT),
            check=True,
        )
        
        for name, script, port in services:
            process = start_service(name, script, port)
            processes.append((name, process))
        
        print("\nAll services started!")
        print("=" * 60)
        print("API Gateway:              http://localhost:8000")
        print("Analysis Service:         http://localhost:8081")
        print("Error Analysis Agent:     http://localhost:8082")
        print("Knowledge Service:        http://localhost:8083")
        print("Teaching Service:         http://localhost:8084")
        print("Teacher Service:          http://localhost:8090")
        print("State Service:            http://localhost:8085")
        print("Review Scheduler:         http://localhost:8086")
        print("Review Service:           http://localhost:8087")
        print("OCR Service:              http://localhost:8089")
        print("Knowledge Graph Service:  http://localhost:8007")
        print("=" * 60)
        print(f"\n各服务日志保存在: backend/logs/ 目录下，如需调试请查看对应文件")
        print("\nPress Ctrl+C to stop all services...")
        
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nStopping all services...")
        for name, process in processes:
            process.terminate()
            process.wait()
            print(f"{name} stopped")
        print("All services stopped")

if __name__ == "__main__":
    main()
