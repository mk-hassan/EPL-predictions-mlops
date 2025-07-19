## Setting Up the Environment

To activate and install the dependencies for this project, follow these steps:

1. **Activate Pipenv Shell**
   Open your terminal and navigate to the project directory:
   ```bash
   cd /path/to/EPL-predictions
   ```

2. **Install Dependencies Using uv (Recommended)**
   If you have `uv` installed, set the environment variable and run:
   ```bash
   export PIPENV_INSTALLER=uv
   pipenv install
   ```
   This will use `uv` for faster and more reliable dependency installation.

3. **If uv Is Not Found**
   If you do not have `uv` installed, Pipenv will fall back to using `pip`.
   You can install dependencies normally:
   ```bash
   pipenv install
   ```

4. **Activate the Virtual Environment**
   After installation, activate the environment:
   ```bash
   pipenv shell
   ```

This will set up all required packages as specified
