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

import sys
import unittest

import httpretty
import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backends.puppet.puppet_forge import PuppetForgeClient


PUPPET_FORGE_URL = 'http://example.com'
PUPPET_FORGE_MODULES_URL = PUPPET_FORGE_URL + '/v3/modules'
PUPPET_FORGE_RELEASES_URL = PUPPET_FORGE_URL + '/v3/releases'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    modules_bodies = [
        read_file('data/puppet_forge/puppet_forge_modules.json', 'rb'),
        read_file('data/puppet_forge/puppet_forge_modules_next.json', 'rb')
    ]
    ceph_body =  read_file('data/puppet_forge/puppet_forge_releases_ceph.json', 'rb')


    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()

        if uri.startswith(PUPPET_FORGE_MODULES_URL):
            body = modules_bodies.pop(0)
        elif uri.startswith(PUPPET_FORGE_RELEASES_URL):
            params = last_request.querystring
            module = params['module'][0]

            if module == 'norisnetwork-ceph':
                body = ceph_body
        else:
            raise

        http_requests.append(last_request)

        return (200, headers, body)

    httpretty.register_uri(httpretty.GET,
                           PUPPET_FORGE_MODULES_URL,
                           responses=[
                                httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                           ])
    httpretty.register_uri(httpretty.GET,
                           PUPPET_FORGE_RELEASES_URL,
                           responses=[
                                httpretty.Response(body=request_callback) \
                                    for _ in range(1)
                           ])

    return http_requests


class TestPuppetForgeClient(unittest.TestCase):
    """PuppetForgeClient REST API unit tests.

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    def test_init(self):
        """Test initialization"""

        client = PuppetForgeClient(PUPPET_FORGE_URL, max_items=2)
        self.assertEqual(client.base_url, PUPPET_FORGE_URL)
        self.assertEqual(client.max_items, 2)

    @httpretty.activate
    def test_modules(self):
        """Test modules API call"""

        http_requests = setup_http_server()

        client = PuppetForgeClient(PUPPET_FORGE_URL, max_items=2)

        # Call API
        modules = client.modules()
        result = [module for module in modules]

        self.assertEqual(len(result), 2)

        expected = [
            {
             'limit' : ['2'],
             'sort_by' : ['latest_release']
            },
            {
             'limit' : ['2'],
             'offset' : ['2'],
             'sort_by' : ['latest_release']
            },
        ]

        self.assertEqual(len(http_requests), 2)

        for x in range(0, len(http_requests)):
            req = http_requests[x]
            self.assertEqual(req.method, 'GET')
            self.assertRegex(req.path, '/v3/modules')
            self.assertDictEqual(req.querystring, expected[x])

    @httpretty.activate
    def test_releases(self):
        """Test releases API call"""

        http_requests = setup_http_server()

        client = PuppetForgeClient(PUPPET_FORGE_URL, max_items=2)

        # Call API
        releases = client.releases('norisnetwork', 'ceph')
        result = [release for release in releases]

        self.assertEqual(len(result), 1)

        expected = [
            {
             'limit' : ['2'],
             'module' : ['norisnetwork-ceph'],
             'show_deleted' : ['true'],
             'sort_by' : ['release_date']
            }
        ]

        self.assertEqual(len(http_requests), 1)

        for x in range(0, len(http_requests)):
            req = http_requests[x]
            self.assertEqual(req.method, 'GET')
            self.assertRegex(req.path, '/v3/releases')
            self.assertDictEqual(req.querystring, expected[x])


if __name__ == "__main__":
    unittest.main(warnings='ignore')
