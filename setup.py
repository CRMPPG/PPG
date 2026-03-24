from setuptools import setup, find_packages

setup(
    name="ppg",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "pandas>=2.1.0",
        "selenium>=4.15.0",
        "fake-useragent>=1.4.0",
        "SQLAlchemy>=2.0.0",
        "python-dotenv>=1.0.0",
        "rich>=13.7.0",
        "click>=8.1.0",
        "tenacity>=8.2.0",
    ],
    entry_points={
        "console_scripts": [
            "ppg=ppg.cli:cli",
        ],
    },
)
