from setuptools import setup, find_packages

# Read the README.md for the long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="filesystem",
    version="0.1.0",
    packages=find_packages(where="."),
    package_dir={"": "."},
    install_requires=[
        "argparse>=1.4.0",
        "filelock>=3.18.0",
        "httpx>=0.28.1",
        "mcp[cli]>=1.5.0",
    ],
    author="0kenx",
    author_email="",
    entry_points={
        "console_scripts": [
            "filesystem-server=filesystem.main:main",
        ],
    },
    description="MCP Servers Filesystem",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/0kenx/mcp-servers",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
)
