from setuptools import setup, find_packages
import os

# Read version from VERSION file
with open("VERSION", "r") as f:
    version = f.read().strip()

# Read requirements from requirements.txt
with open("requirements.txt", "r") as f:
    # Filter out comments and empty lines
    requirements = [
        line.strip() 
        for line in f.readlines() 
        if line.strip() and not line.startswith("#")
    ]

# Read development requirements
dev_requirements = [
    req for req in requirements 
    if any(dev_tool in req for dev_tool in ["pytest", "black", "isort", "mypy", "pylint"])
]

# Core requirements (excluding dev requirements)
core_requirements = [
    req for req in requirements
    if req not in dev_requirements
]

setup(
    name="neo",
    version=version,
    description="CLI application for interacting with LLMs to build software",
    author="Neo Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=core_requirements,
    extras_require={
        "dev": dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "neo=src.cli:main",
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
)