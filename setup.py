"""Setup script for the Neo project."""

from setuptools import setup, find_packages

# Function to read the requirements file
def read_requirements(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Function to read the README file for long description
def read_readme(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

# Read version from VERSION file
with open("VERSION", "r", encoding='utf-8') as f:
    version = f.read().strip()

# Read requirements and README
requirements = read_requirements('requirements.txt')
readme = read_readme('README.md')

# Read development requirements
dev_requirements = [
    req
    for req in requirements
    if any(
        dev_tool in req for dev_tool in ["pytest", "black", "isort", "mypy", "pylint"]
    )
]

# Core requirements (excluding dev requirements)
core_requirements = [req for req in requirements if req not in dev_requirements]

setup(
    name="neo",
    version=version,
    author="Neo Team",
    description="CLI application for interacting with LLMs to build software",
    long_description=readme,
    long_description_content_type='text/markdown',
    url='https://github.com/rahulgovind/neo',
    packages=find_packages(),
    install_requires=core_requirements,
    extras_require={
        "dev": dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "neo=src.apps.cli:main",
            "neo-web=src.apps.web.launcher:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
)
