# perceval-puppet

Bundle of Perceval backends for Puppet, Inc. ecosystem.

## Backends

The backends currently managed by this package support the next repositories:

* Puppet Forge

## Requirements

* Python >= 3.4
* python3-requests >= 2.7
* perceval >= 0.5

## Installation

To install this package you will need to clone the repository first:

```
$ git clone https://github.com/grimoirelab/perceval-puppet.git
```

In this case, [setuptools](http://setuptools.readthedocs.io/en/latest/) package will be required.
Make sure it is installed before running the next commands:

```
$ pip3 install -r requirements.txt
$ python3 setup.py install
```

## Examples

### Puppet Forge

```
$ perceval puppetforge
```

## License

Licensed under GNU General Public License (GPL), version 3 or later.
