# Flow Production Tracking Core API

## The `requirements` folder

The `requirements` folder contains subdirectories for different Python versions (e.g., `3.7`, `3.9`, `3.10`, and `3.11`). Each subdirectory includes the following files:

- **`requirements.txt`**: Specifies the dependencies for the corresponding Python version. This file is primarily used to document which packages are required for the application.
- **`frozen_requirements.txt`**: A frozen version of the dependencies, capturing exact package versions installed, including sub-dependencies, to ensure consistent and reproducible environments.
- **`pkgs.zip`**: A zip file containing the bundled packages for the corresponding Python version.

### How bundled packages are used

The `__init__.py` file in the `tank_vendor` folder dynamically references and loads packages from the appropriate `pkgs.zip` file in the `requirements` folder.

This approach centralizes the management of dependencies, ensuring that packages are versioned and bundled consistently across different Python versions.

### Updating and creating bundled packages

The `update_python_packages.py` script automates the creation and maintenance of the `pkgs.zip` file.

#### Workflow:

1. Update the `requirements.txt` file for the desired Python version.
2. Run the `update_python_packages.py` script to:
   - Install the specified dependencies in a temporary directory.
   - Create or update the `pkgs.zip` file with the required packages.
   - Generate the `frozen_requirements.txt` file for consistency.
3. Validate that the `pkgs.zip` file contains all necessary packages and matches the updated requirements.


### Maintaining dependencies

When adding new dependencies or updating existing ones:
1. Update the `requirements.txt` file for the corresponding Python version.
2. Regenerate the `pkgs.zip` and `frozen_requirements.txt` files using `update_python_packages.py`.
3. Ensure the `pkgs.zip` file includes all necessary packages and modules.

### Automated CVE checks

The `frozen_requirements.txt` files enable automated checks for vulnerabilities (CVEs) in the bundled packages. These files capture the exact versions of dependencies included in the `pkgs.zip` files, ensuring the application remains secure by providing visibility into potential vulnerabilities.

### Notes

The dynamic loading mechanism in `tank_vendor/__init__.py` ensures that bundled packages are accessed seamlessly from the `pkgs.zip` files, reducing duplication and simplifying dependency updates.

Careful attention to package structure and appropriate import mechanisms will help avoid runtime issues and ensure smooth integration of new dependencies.
