# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, 51 Franklin Street, Fifth Floor, Boston, MA 02110-1335, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import logging

import requests

from ...utils import urljoin


logger = logging.getLogger(__name__)


MAX_ITEMS = 100
PUPPET_FORGE_URL = "https://forge.puppet.com/"


class PuppetForgeClient:
    """Puppet forge REST API client.

    This class implements a simple client to retrieve data
    from a Puppet forge using its REST API v3.

    :param base_url: URL of the Puppet forge server
    :param max_items: number maximum of items per requested

    :raises BackendError: when an error occurs initilizing the
        client
    """
    RMODULES = 'modules'
    RRELEASES = 'releases'

    PLIMIT = 'limit'
    PMODULE = 'module'
    PSHOW_DELETED = 'show_deleted'
    PSORT_BY = 'sort_by'

    VLATEST_RELEASE = 'latest_release'
    VRELEASE_DATE = 'release_date'


    def __init__(self, base_url, max_items=MAX_ITEMS):
        self.base_url = base_url
        self.max_items = max_items

    def modules(self):
        """Fetch modules pages."""

        resource = self.RMODULES

        params = {
            self.PLIMIT : self.max_items,
            self.PSORT_BY : self.VLATEST_RELEASE
        }

        for page in self._fetch(resource, params):
            yield page

    def releases(self, owner, module):
        """Fetch the releases of a module."""

        resource = self.RRELEASES

        params = {
            self.PMODULE : owner + '-' + module,
            self.PLIMIT : self.max_items,
            self.PSHOW_DELETED : 'true',
            self.PSORT_BY : self.VRELEASE_DATE,
        }

        for page in self._fetch(resource, params):
            yield page

    def _fetch(self, resource, params):
        """Fetch a resource.

        Method to fetch and to iterate over the contents of a
        type of resource. The method returns a generator of
        pages for that resource and parameters.

        :param resource: type of the resource
        :param params: parameters to filter

        :returns: a generator of pages for the requested resource
        """
        url = urljoin(self.base_url, 'v3', resource)

        do_fetch = True

        while do_fetch:
            logger.debug("Puppet forge client calls resource: %s params: %s",
                         resource, str(params))

            r = requests.get(url, params=params)
            r.raise_for_status()
            yield r.text

            next_url = r.json()['pagination']['next']

            if next_url:
                # Params are already included in the URL
                url = urljoin(self.base_url, next_url)
                params = {}
            else:
                do_fetch = False
