#!/usr/bin/env python
from setuptools import setup, find_packages


with open('README.md') as readme_file:
    README = readme_file.read()


install_requires = [
    'boto3>=1.9.8,<2.0.0',
    'botocore>=1.12.5,<2.0.0',
    'chalice>=1.6.0,<2.0.0',
    'click>=6.6,<7.0',
    'pip>=9,<11',
    'PyYAML>=3.13,<4.0',
]

setup(
    name='zerv',
    version='0.1.0',
    description="CLI Tool",
    long_description=README,
    author="Henoc Díaz",
    author_email='self@henocdz.com',
    url='https://github.com/henocdz/zerv',
    packages=find_packages(exclude=['tests']),
    install_requires=install_requires,
    license="GNU General Public License v3 (GPLv3)",
    package_data={'chalice': ['*.json']},
    include_package_data=True,
    zip_safe=False,
    keywords='zerv',
    entry_points={
        'console_scripts': [
            'zerv = zerv.cli.handler:main',
        ]
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Topic :: Software Development :: Build Tools',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
    ],
)
