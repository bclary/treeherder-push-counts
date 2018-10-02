# treeherder-push-counts
Retrieve push counts from Treeherder by date and test labels

      usage: pushes.py [-h] [--treeherder TREEHERDER] [--start-date START_DATE]
		       [--end-date END_DATE] [--repo REPOS] [--list-repos]
		       [--test-label TEST_LABELS] [--consolidate]
		       [--delimiter DELIMITER]

      Retrieve push counts from Treeherder by repository, date and test labels.

      optional arguments:
	-h, --help            show this help message and exit
	--treeherder TREEHERDER
			      Treeherder url. Defaults to
			      https://treeherder.mozilla.org
	--start-date START_DATE
			      start date CCYY-MM-DD. (default: today's date).
	--end-date END_DATE   end date CCYY-MM-DD. (default: start date + 1 day).
	--repo REPOS          List of repositories to query. Example mozilla-
			      central.
	--list-repos          List available repositories.
	--test-label TEST_LABELS
			      Output counts of test jobs matching list of regular
			      expressions matching test labels. See the output of
			      ./mach taskgraph tasks --json for example labels. If
			      not specified, output count of total pushes.
	--consolidate         By default, counts will be grouped by the full test
			      label. Specify --consolidate to group counts by the
			      specified test label patterns rather than full test
			      label.
	--delimiter DELIMITER
			      Field delimiter defaults to ','.
