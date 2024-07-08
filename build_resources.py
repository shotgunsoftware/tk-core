import sys
import subprocess
import os


# Set the Python environment variable. If 'PYTHONPATH' is not set, use the default path "/usr/bin/"
# or you can override the Python environment path for a specific virtual environment
PYTHON_ENV = os.getenv("PYTHONPATH", "/usr/bin/")

# List of commands to build QT resources
COMMANDS = [
    [
        "tk-build-qt-resources",
        "-p",
        PYTHON_ENV,
        "-py",
        "python/tank/authentication/ui",
        "-q",
        "python/tank/authentication/resources",
        "-uf",
        "login_dialog",
        "-rf",
        "resources",
        "-i",
        ".qt_abstraction",
    ],
    [
        "tk-build-qt-resources",
        "-p",
        PYTHON_ENV,
        "-py",
        "python/tank/platform/qt",
        "-q",
        "python/tank/platform/qt",
        "-uf",
        "tank_dialog",
        "item",
        "busy_dialog",
        "-ufn",
        "ui_tank_dialog",
        "ui_item",
        "ui_busy_dialog",
        "-rf",
        "resources",
        "-i",
        ".",
    ],
]


def install_package(package):
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)
        print(f"Package {package} installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while installing {package}. Error output: {e.stderr}")


def run_commands():
    for command in COMMANDS:
        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            print(f"Command executed successfully. Output:, {result.stdout}")
        except subprocess.CalledProcessError as e:
            print(
                f"An error occurred while executing the command. Error output: {e.stderr}"
            )


if __name__ == "__main__":
    install_package(
        "git+https://github.com/shotgunsoftware/tk-toolchain.git#egg=tk-toolchain"
    )
    run_commands()
