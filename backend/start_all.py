import subprocess
import sys
import time
import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent


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
