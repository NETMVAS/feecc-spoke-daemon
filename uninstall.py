import os
import subprocess
import sys
import typing as tp

if __name__ == "__main__":
    # check if running with sudo
    if os.getuid() != 0:
        print("This script must be executed with Root permissions.")
        sys.exit()

    # get own repository name
    cwd: str = os.path.dirname(os.path.realpath(__file__))
    project_name: str = cwd.split("/")[-1]
    print(f"Uninstalling {project_name}.")

    # find the systemd service file
    systemd_service: str = [file for file in os.listdir() if file.endswith(".service")][0]

    if not systemd_service:
        print(f"Systemd service file not found in {cwd}. Exiting.")
        sys.exit()

    # commands to execute
    commands: tp.List[str] = [
        f"sudo systemctl stop {systemd_service}",
        f"sudo systemctl disable {systemd_service}",
        f"sudo rm /etc/systemd/system/{systemd_service}",
        "sudo systemctl daemon-reload",
        "rm -rf .venv",
        "rm -f poetry.lock",
    ]

    for command, i in zip(commands, range(len(commands))):
        print(f"\nExecuting command {i + 1}/{len(commands)}: {command}")
        subprocess.run(command, shell=True)

    print(f"\nDaemon for the project {project_name} has been uninstalled from this machine.")
