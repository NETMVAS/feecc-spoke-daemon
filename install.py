import os
import subprocess
import sys
import typing as tp


def generate_systemd_service(
        filename: str,
        path_placeholder: str = "PROJECT_DIRECTORY",
        user_placeholder: str = "PROJECT_USER"
) -> None:
    """replaces placeholder in the service file to match the actual data"""
    actual_path: str = os.path.dirname(os.path.realpath(__file__))
    actual_user: str = os.getlogin()
    new_lines: tp.List[str] = []

    with open(filename, "r") as file:
        for line in file.readlines():
            if path_placeholder in line:
                line = line.replace(path_placeholder, actual_path)

            if user_placeholder in line:
                line = line.replace(user_placeholder, actual_user)

            new_lines.append(line)

    with open(filename, "w") as file:
        file.writelines(new_lines)


if __name__ == "__main__":
    # check if running with sudo
    if os.getuid() != 0:
        print("This script must be executed with Root permissions.")
        sys.exit()

    # get own repository name
    cwd: str = os.path.dirname(os.path.realpath(__file__))
    project_name: str = cwd.split("/")[-1]
    print(f"Starting installation of {project_name}.")

    # find the systemd service file
    systemd_service: str = [file for file in os.listdir() if file.endswith(".service")][0]

    if not systemd_service:
        print(f"Systemd service file not found in {cwd}. Exiting.")
        sys.exit()
    else:
        # generate a valid systemd service for the daemon
        generate_systemd_service(systemd_service)

    # commands to execute
    commands: tp.List[str] = [
        "poetry install --no-dev --no-interaction",  # install dependencies using poetry
        f"sudo cp {systemd_service} /etc/systemd/system/",
        "sudo systemctl daemon-reload",
        f"sudo systemctl enable {systemd_service}",
        f"sudo systemctl start {systemd_service}",
        f"sleep 5 && sudo systemctl status {systemd_service}",
    ]

    for command, i in zip(commands, range(len(commands))):
        print(f"\nExecuting command {i + 1}/{len(commands)}: {command}")
        subprocess.run(command, shell=True)

    print(f"\nDaemon for the project {project_name} has been installed on this machine.")
    print(f"To uninstall {project_name} run 'sudo python3 uninstall.py'.")
