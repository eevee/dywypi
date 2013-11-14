from setuptools import setup, find_packages

about = {}
with open("dywypi/__about__.py") as fp:
    exec(fp.read(), about)

ASYNCIO_DEPENDENCY = "asyncio>=0.1.1"

install_requires = [
    ASYNCIO_DEPENDENCY,
]

setup(
    name=about["__title__"],
    version=about["__version__"],

    description=about["__summary__"],
    license=about["__license__"],
    url=about["__uri__"],

    author=about["__author__"],
    author_email=about["__email__"],

    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: BSD",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: Implementation :: CPython",
    ],

    packages=find_packages(exclude=["tests", "tests.*"]),

    install_requires=install_requires,
)
