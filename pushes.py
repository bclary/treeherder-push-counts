#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import datetime
import json
import logging
import random
import re
import requests
import time
import urlparse

def get_remote_text(url):
    """Return the string containing the contents of a remote url if the
    request is successful, otherwise return None.

    :param url: url of content to be retrieved.
    """
    logger = logging.getLogger()

    try:
        parse_result = urlparse.urlparse(url)
        if not parse_result.scheme or parse_result.scheme.startswith('file'):
            local_file = open(parse_result.path)
            with local_file:
                return local_file.read()

        while True:
            try:
                r = requests.get(url, headers={'user-agent': 'autophone'})
                if r.ok:
                    return r.text
                elif r.status_code == 503:
                    # Server is too busy.
                    # See https://bugzilla.mozilla.org/show_bug.cgi?id=1146983#c10
                    logger.warning("HTTP 503 Server Too Busy: url %s", url)
                else:
                    logger.warning("Unable to open url %s : %s",
                                   url, r.reason)
                    return None
            except requests.ConnectionError, e:
                logger.warning("ConnectionError: %s. Will retry..." % e)

            # Wait and try again.
            time.sleep(60 + random.randrange(0, 30, 1))
    except Exception:
        logger.exception('Unable to open %s', url)

    return None


def get_remote_json(url):
    """Return the json representation of the contents of a remote url if
    the HTTP response code is 200, otherwise return None.

    :param url: url of content to be retrieved.
    """
    logger = logging.getLogger()
    content = get_remote_text(url)
    if content:
        content = json.loads(content)
    logger.debug('get_remote_json(%s): %s', url, content)
    return content


def parse_args():
    """Return the parsed arguments."""

    parser = argparse.ArgumentParser(description="""
Retrieve push counts from Treeherder by repository, date and test labels.
""")

    parser.add_argument("--treeherder",
                        dest="treeherder",
                        default='https://treeherder.mozilla.org',
                        help="Treeherder url. Defaults to https://treeherder.mozilla.org")
    parser.add_argument("--start-date",
                        dest="start_date",
                        default=None,
                        help="start date CCYY-MM-DD. (default: today's date).")
    parser.add_argument("--end-date",
                        dest="end_date",
                        default=None,
                        help="end date CCYY-MM-DD. (default: start date + 1 day).")
    parser.add_argument("--repo",
                        dest="repos",
                        action="append",
                        default=[],
                        help="List of repositories to query. Example mozilla-central.")
    parser.add_argument("--list-repos",
                        dest="list_repos",
                        action="store_true",
                        default=False,
                        help="List available repositories.")
    parser.add_argument("--test-label",
                        dest='test_labels',
                        action="append",
                        default=[],
                        help="Output counts of test jobs matching list of regular expressions "
                        "matching test labels. See the output of  ./mach taskgraph tasks --json "
                        "for example labels. If not specified, output count of total pushes.")
    parser.add_argument("--consolidate",
                        dest='consolidate',
                        action="store_true",
                        default=False,
                        help="By default, counts will be grouped by the full test label. "
                        "Specify --consolidate to group counts by the specified test label "
                        "patterns rather than full test label.")
    parser.add_argument("--delimiter",
                        dest='delimiter',
                        default=',',
                        help="Field delimiter defaults to ','.")
    return parser.parse_args()


def datestr(date):
    return datetime.datetime.strftime(date, '%Y-%m-%d')


def get_date_range(start_datestr, end_datestr):
    """Return tuple (start_date, end_date) from input date arguments."""

    if not start_datestr:
        start_datestr = datestr(datetime.datetime.now())
    start_date = datetime.datetime.strptime(start_datestr, '%Y-%m-%d')

    if not end_datestr:
        end_datestr = datestr(start_date + datetime.timedelta(days=1))
    end_date = datetime.datetime.strptime(end_datestr, '%Y-%m-%d')

    return (start_date, end_date)


class Treeherder(object):
    def __init__(self, treeherder_url):
        if not treeherder_url:
            raise Exception('treeherder url is required')

        self.treeherder_url = treeherder_url.rstrip('/')
        self.repository_api_url = '%s/api/repository/' % self.treeherder_url
        repository_json = get_remote_json(self.repository_api_url)
        if not repository_json:
            raise Exception('No repositories found at %s' % self.repository_api_url)

        self.repository_urls = dict([ (o['name'], o['url']) for o in repository_json ])

    def list_repos(self):
        repos = self.repository_urls.keys()
        repos.sort()
        for repo in repos:
            print '%-30s %s' % (repo, self.repository_urls[repo])

    def get_pushes(self, repo, start_date, end_date):
        start_datestr = datestr(start_date)
        end_datestr = datestr(end_date)
        pushes_url = '%s/json-pushes?startdate=%s&enddate=%s' % (
            self.repository_urls[repo], start_datestr, end_datestr)
        return get_remote_json(pushes_url)

    def get_changeset_resultset(self, repo, revision):
        resultset_url = '%s/api/project/%s/push/?full=true&count=10&revision=%s' % (
            self.treeherder_url, repo, revision)
        return get_remote_json(resultset_url)

    def get_jobs(self, repo, changeset_resultset_id):
        jobs_url = '%s/api/project/%s/jobs/?return_type=list&count=2000&result_set_id=%s' % (
            self.treeherder_url, repo, changeset_resultset_id)
        return get_remote_json(jobs_url)


    def output_headers(self, has_test_labels, delimiter):
        if has_test_labels: # Count all pushes but not individual test jobs.
            print delimiter.join(['date', 'repo', 'test_label', 'count'])
        else:
            print delimiter.join(['date', 'repo', 'count'])

    def output_counts(self, repo, re_test_labels, delimiter, consolidate, start_date, end_date):
        current_date = start_date

        while current_date < end_date:
            next_date = current_date + datetime.timedelta(days=1)
            pushes_json = self.get_pushes(repo, current_date, next_date)
            if pushes_json:
                push_ids = pushes_json.keys()
                push_ids.sort()
                if not re_test_labels: # Count all pushes but not individual test jobs.
                    count = int(push_ids[-1]) - int(push_ids[0]) + 1
                    print delimiter.join([datestr(current_date), repo, str(count)])
                else:
                    label_counts = {}
                    for push_id in push_ids:
                        changeset = pushes_json[push_id]['changesets'][-1]
                        changeset_resultset_json = self.get_changeset_resultset(repo, changeset)
                        for changeset_result in changeset_resultset_json['results']:
                            changeset_resultset_id = changeset_result['id']
                            jobs_json = self.get_jobs(repo, changeset_resultset_id)

                            for jobs_results in jobs_json['results']:
                                jobs_results_dict = dict(zip(jobs_json['job_property_names'],
                                                             jobs_results))
                                for re_label in re_test_labels:
                                    if re_label.search(jobs_results_dict['job_type_name']):
                                        if consolidate:
                                            label_key = re_label.pattern
                                        else:
                                            label_key = jobs_results_dict['job_type_name']

                                        label_counts[label_key] = label_counts.get(label_key, 0) + 1

                    label_keys = label_counts.keys()
                    label_keys.sort()
                    for label_key in label_keys:
                        print delimiter.join([
                            datestr(current_date),
                            repo,
                            label_key,
                            str(label_counts[label_key])
                        ])

            current_date = next_date


def main():

    logging.basicConfig()
    logger = logging.getLogger()

    args = parse_args()

    try:
        treeherder = Treeherder(args.treeherder)
    except:
        logger.exception('Initializing treeherder')
        return 1

    if args.list_repos:
        treeherder.list_repos()
        return 0

    re_test_labels = []
    for test_label_pattern in args.test_labels:
        re_test_labels.append(re.compile(test_label_pattern))

    (start_date, end_date) = get_date_range(args.start_date, args.end_date)

    treeherder.output_headers(len(re_test_labels) > 0, args.delimiter)
    for repo in args.repos:
        treeherder.output_counts(repo, re_test_labels, args.delimiter, args.consolidate, start_date, end_date)


if __name__ == '__main__':
    main()
