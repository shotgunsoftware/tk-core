import sys

# Store the current platform in constants here to centralize the OS tests, and
# provide a standard way of determining the current OS.
on_windows = sys.platform == "win32"
on_linux = sys.platform.startswith("linux")
on_macos = sys.platform == "darwin"
