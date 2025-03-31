from setuptools import setup, find_packages

setup(
    name="MCP Filesystem Tool",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # List your project dependencies here
        # For example:
        # "requests>=2.25.1",
        # "pandas>=1.2.0",
    ],
    author="0kenx",
    author_email="your.email@example.com",
    description="MCP Filesystem Tool with advanced diff editing",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/0kenx/mcp-servers",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
) 