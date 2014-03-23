import sys

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


# From py.test documentation: make `setup.py test` run py.test
class PyTestCommand(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # Can't import globally, as py.test might not yet be installed
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


# Fetch metadata from a module without risking importing __init__.py
# TODO dywypi's __init__.py is empty so this might be unnecessary...
about = {}
with open("dywypi/__about__.py") as fp:
    exec(fp.read(), about)


# Only depend on asyncio if it's not in stdlib
backport_deps = []
if sys.version_info < (3, 4):
    backport_deps.append('enum34')
    # 0.1.1 has a critical SSL fix, I believe
    backport_deps.append('asyncio>=0.1.1')


setup(
    name=about["__title__"],
    version=about["__version__"],

    description=about["__summary__"],
    license=about["__license__"],
    url=about["__uri__"],

    long_description="Please see the project GitHub for README and docs.",

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
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: CPython",
    ],

    packages=find_packages(exclude=["dywypi.tests", "dywypi.tests.*"]),

    cmdclass=dict(
        test=PyTestCommand,
    ),
    tests_require=['pytest>=2.5'],
    install_requires=backport_deps + [
        'aiohttp',
    ],
)
