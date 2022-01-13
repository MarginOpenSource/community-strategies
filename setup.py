#!/usr/bin/env python

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="margin_community_strategies",
    version="0.0.4",
    author="Margin UG",
    author_email="contact@margin.io",
    description="Strategies for the Margin Strategy Editor provided by the community",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MarginOpenSource/community-strategies",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=["margin-strategy-sdk"],
    python_requires='>=3.6',
)
