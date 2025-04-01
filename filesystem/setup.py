from setuptools import setup, find_packages

setup(
    name="filesystem",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "filelock>=3.18.0",
        "httpx>=0.28.1",
    ],
    author="0kenx",
    description="MCP Servers Filesystem",
    long_description="MCP Servers Filesystem",  # Fallback if README.md doesn't exist
    url="https://github.com/0kenx/mcp-servers",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
