# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2019 Bitergia
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
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#     Quan Zhou <quan@bitergia.com>
#

import json
import logging

from grimoirelab_toolkit.datetime import datetime_to_utc, str_to_datetime
from grimoirelab_toolkit.uris import urijoin


from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...utils import DEFAULT_DATETIME

CATEGORY_MODULE = "module"

MAX_ITEMS = 100
PUPPET_FORGE_URL = "https://forge.puppet.com/"

logger = logging.getLogger(__name__)


class PuppetForge(Backend):
    """Puppet Forge backend.

    Class to fetch the modules and their realeases stored in
    the Puppet's forge.

    :param max_items: maximum number of items requested on the same query
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve data
    :param ssl_verify: enable/disable SSL verification
    """
    version = '1.0.0'

    CATEGORIES = [CATEGORY_MODULE]
    EXTRA_SEARCH_FIELDS = {
        'module_group': ['module_group'],
        'slug': ['slug']
    }

    def __init__(self, max_items=MAX_ITEMS, tag=None, archive=None, ssl_verify=True):
        origin = PUPPET_FORGE_URL

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.max_items = max_items
        self.client = None

        self._owners = {}

    def fetch(self, category=CATEGORY_MODULE, from_date=DEFAULT_DATETIME):
        """Fetch the modules from the server.

        This method fetches a list of modules stored in the Puppet's
        forge. Releases data are included within each module.

        Take into account that items will be returned from the latest
        updated to the first one. This is the only order that Puppet
        forge API offers.

        :param from_date: obtain modules updated since this date

        :returns: a generator of modules
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = datetime_to_utc(from_date)

        kwargs = {'from_date': from_date}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the modules

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']

        logger.info("Fetching modules from %s", str(from_date))

        from_date_ts = datetime_to_utc(from_date).timestamp()

        nmodules = 0
        stop_fetching = False

        raw_pages = self.client.modules()

        for raw_modules in raw_pages:
            modules = [mod for mod in self.parse_json(raw_modules)]

            for module in modules:
                # Check timestamps to stop fetching more modules
                # because modules fetched sorted by 'updated_at'
                # from newest to oldest.
                updated_at_ts = self.metadata_updated_on(module)

                if from_date_ts > updated_at_ts:
                    stop_fetching = True
                    break

                owner = module['owner']['username']
                name = module['name']
                module['releases'] = self.__fetch_and_parse_releases(owner, name)
                module['owner_data'] = self.__get_or_fetch_owner(owner)

                yield module
                nmodules += 1

            if stop_fetching:
                break

        logger.info("Fetch process completed: %s modules fetched", nmodules)

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend supports items archive
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend does not support items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Puppet forge item."""

        item_id = item['owner']['username'] + '-' + item['name']
        return item_id

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Puppet forge item.

        The timestamp is extracted from 'updated_at' field and converted
        to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['updated_at']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Puppet forge item.

        This backend only generates one type of item which is
        'module'.
        """
        return CATEGORY_MODULE

    @staticmethod
    def parse_json(raw_json):
        """Parse a Puppet forge JSON stream.

        The method parses a JSON stream and returns a list
        with the parsed data.

        :param raw_json: JSON string to parse

        :returns: a list with the parsed data
        """
        result = json.loads(raw_json)

        if 'results' in result:
            result = result['results']

        return result

    def _init_client(self, from_archive=False):
        """Init client"""

        return PuppetForgeClient(PUPPET_FORGE_URL, self.max_items, self.archive, from_archive, self.ssl_verify)

    def __fetch_and_parse_releases(self, owner, module):
        logger.debug("Fetching and parsing releases from '%s'-'%s'",
                     owner, module)

        releases = []
        raw_pages = self.client.releases(owner, module)

        for raw_page in raw_pages:
            for release in self.parse_json(raw_page):
                releases.append(release)

        return releases

    def __get_or_fetch_owner(self, owner):
        if owner in self._owners:
            return self._owners[owner]

        logger.debug("Owner %s not found on client cache; fetching it", owner)

        raw_owner = self.client.user(owner)
        data = self.parse_json(raw_owner)

        self._owners[owner] = data

        return data


class PuppetForgeClient(HttpClient):
    """Puppet forge REST API client.

    This class implements a simple client to retrieve data
    from a Puppet forge using its REST API v3.

    :param base_url: URL of the Puppet forge server
    :param max_items: number maximum of items per requested
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification

    :raises BackendError: when an error occurs initilizing the
        client
    """
    RMODULES = 'modules'
    RRELEASES = 'releases'
    RUSER = 'users'

    PLIMIT = 'limit'
    PMODULE = 'module'
    PSHOW_DELETED = 'show_deleted'
    PSORT_BY = 'sort_by'

    VLATEST_RELEASE = 'latest_release'
    VRELEASE_DATE = 'release_date'

    def __init__(self, base_url, max_items=MAX_ITEMS, archive=None, from_archive=False, ssl_verify=True):
        super().__init__(base_url, archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        self.max_items = max_items

    def modules(self):
        """Fetch modules pages."""

        resource = self.RMODULES

        params = {
            self.PLIMIT: self.max_items,
            self.PSORT_BY: self.VLATEST_RELEASE
        }

        for page in self._fetch(resource, params):
            yield page

    def releases(self, owner, module):
        """Fetch the releases of a module."""

        resource = self.RRELEASES

        params = {
            self.PMODULE: owner + '-' + module,
            self.PLIMIT: self.max_items,
            self.PSHOW_DELETED: 'true',
            self.PSORT_BY: self.VRELEASE_DATE,
        }

        for page in self._fetch(resource, params):
            yield page

    def user(self, user):
        """Fetch user data."""

        resource = self.RUSER + '/' + user
        params = {}

        result = [page for page in self._fetch(resource, params)]

        return result[0]

    def _fetch(self, resource, params):
        """Fetch a resource.

        Method to fetch and to iterate over the contents of a
        type of resource. The method returns a generator of
        pages for that resource and parameters.

        :param resource: type of the resource
        :param params: parameters to filter

        :returns: a generator of pages for the requested resource
        """
        url = urijoin(self.base_url, 'v3', resource)

        do_fetch = True

        while do_fetch:
            logger.debug("Puppet forge client calls resource: %s params: %s",
                         resource, str(params))

            r = self.fetch(url, payload=params)
            yield r.text

            json_data = r.json()

            if 'pagination' in json_data:
                next_url = json_data['pagination']['next']

                if next_url:
                    # Params are already included in the URL
                    url = urijoin(self.base_url, next_url)
                    params = {}
                else:
                    do_fetch = False
            else:
                do_fetch = False


class PuppetForgeCommand(BackendCommand):
    """Class to run PuppetForge backend from the command line."""

    BACKEND = PuppetForge

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Puppet Forge argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              archive=True,
                                              ssl_verify=True)

        # Puppet Forge options
        group = parser.parser.add_argument_group('Puppet Forge arguments')
        group.add_argument('--max-items', dest='max_items',
                           type=int, default=MAX_ITEMS,
                           help="Maximum number of items requested on the same query")

        return parser
