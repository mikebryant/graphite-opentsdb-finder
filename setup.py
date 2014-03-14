'''Setup file for graphite-opentsdb.'''
from setuptools import find_packages, setup
from graphite_opentsdb.version import __VERSION__

setup(
    name                 ='graphite-opentsdb',
    version              = __VERSION__,
    packages             = find_packages(),
    description          = 'A graphite storage plugin for OpenTSDB.',
    author               = 'Mike Bryant',
    author_email         = 'mike@mikebryant.me.uk',
    install_requires     = ['django', 'django-cacheback', 'graphite-web', 'requests'],
    include_package_data = True,
    test_suite           = 'setuptest.setuptest.SetupTestSuite',
    tests_require        = ['django-setuptest', 'httmock', 'mock'],
    url                  = 'https://github.com/mikebryant/graphite-opentsdb-finder',
    classifiers          = [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
    ],
)
