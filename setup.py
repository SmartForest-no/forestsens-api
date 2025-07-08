
from setuptools import setup, find_packages

setup(
    name='forestsensapi',
    version='0.1.0',
    description='Python client for ForestSens API and OCI uploads',
    author='Johannes Rahlf',
    author_email='johannes.rahlf@nibio.no',
    packages=find_packages(),
    install_requires=[
        'oci',
        'requests',
        'tqdm'
    ],
    python_requires='>=3.7',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
