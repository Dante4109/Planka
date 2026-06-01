from pathlib import Path
from setuptools import setup, find_packages

here = Path(__file__).parent.resolve()

version_ns = {}
version_file = here / "src" / "planka_tools" / "_version.py"
if version_file.exists():
    exec(version_file.read_text(), version_ns)
package_version = version_ns.get("__version__", "0.0.0")

setup(
    name="planka_tools",
    version=package_version,
    description="Planka Docker management and card automation CLI",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "typer>=0.12.0",
        "python-dotenv>=1.0.0",
        "apscheduler>=3.10.0",
        "requests>=2.31.0",
        "bcrypt>=4.0.0",
    ],
    entry_points={
        "console_scripts": [
            "pt = planka_tools.cli:main",
        ],
    },
)
