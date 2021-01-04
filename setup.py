import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="g-python",
    version="0.1.2",
    author="sirjonasxx",
    author_email="sirjonasxx@hotmail.com",
    description="G-Earth extension interface for Python.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sirjonasxx/G-Python",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.2',
)
