from setuptools import setup, find_packages

setup(
    name="filesystem",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "argparse>=1.4.0",
        "filelock>=3.18.0",
        "httpx>=0.28.1",
        # Remove logging as it's part of standard library
    ],
    author="0kenx",
    description="MCP Servers Filesystem",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/0kenx/mcp-servers",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
) 