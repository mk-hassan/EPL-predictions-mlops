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

This will set up all required packages as specified in the `Pipfile`.

---

## Initializing Pre-commit Hooks

To enable automated code quality and security checks before each commit, initialize pre-commit in your project:

### Setup Tasks

- [ ] **Install pre-commit (if not already installed):**
  ```bash
  pipenv install --dev pre-commit
  ```

- [ ] **Install the pre-commit hooks:**
  ```bash
  pre-commit install
  ```

- [ ] **(Optional) Install commit-msg and other hook types:**
  ```bash
  pre-commit install --hook-type commit-msg
  ```

---

### What pre-commit will do

- [x] Automatically runs code formatters (Black, isort, Ruff) on staged files before each commit.
- [x] Runs linters (pylint) and security scanners (Bandit) to check code quality and security.
- [x] Prevents commits if code does not meet quality or security standards.
- [x] Helps maintain consistent code style and catch issues early.

You can manually run all hooks on all files with:
```bash
pre-commit run --all
```
