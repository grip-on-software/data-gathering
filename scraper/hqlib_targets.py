"""
Script to parse default values for targets and low targets from all versions of
the quality reporting tool.
"""

import argparse
import ast
from distutils.version import LooseVersion
import json
import logging
import os.path
import hqlib.domain
from hqlib.utils import version_number_to_numerical
from gatherer.domain import Source
from gatherer.git import Git_Repository
from gatherer.log import Log_Setup
from gatherer.utils import get_local_datetime
from gatherer.version_control.repo import FileNotFoundException

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain quality reporting targets"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--repo', default='quality-report',
                        help='path to the quality reporting Git repository')
    parser.add_argument('--checkout', action='store_true', default=False,
                        help='Check out the quality reporting repository tree')
    parser.add_argument('--from-revision', dest='from_revision', default=None,
                        help='revision to start from gathering metric targets')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

class Metric_Visitor(ast.NodeVisitor):
    """
    Visitor of an abstract syntax tree of a metrics definition file.
    """

    # pylint: disable=invalid-name
    TARGETS = (
        'target_value', 'low_target_value', 'perfect_value',
        'numerical_value_map'
    )
    OLD_TARGETS = {
        'target_factor': 'target_value',
        'low_target_factor': 'low_target_value'
    }

    def __init__(self):
        self.class_name = None
        self.target_name = None
        self.abstract = False
        self.targets = {}
        self.class_targets = {}

    def visit(self, node):
        """
        Visit a node in the AST.
        """

        prev_target_name = self.target_name
        super(Metric_Visitor, self).visit(node)
        if prev_target_name is not None and self.target_name is not None:
            self.target_name = None

    def visit_ClassDef(self, node):
        """
        Visit a class definition in the AST.
        """

        self.class_name = node.name
        self.abstract = False
        self.targets = {}

        # Inherit values from superclasses
        for base in node.bases:
            self.visit(base)

        for subnode in node.body:
            self.visit(subnode)

        if self.targets:
            if 'numerical_value_map' in self.targets:
                value_map = self.targets.pop('numerical_value_map')
                self.targets = dict([
                    (key, str(value_map[value]))
                    if value in value_map else (key, value)
                    for key, value in self.targets.items()
                ])

            self.targets['_abstract'] = self.abstract
            self.class_targets[self.class_name] = self.targets

    def _inherit_superclass(self, name):
        if self.class_name is not None:
            if name in self.class_targets:
                self.targets.update(self.class_targets[name])
            elif name.endswith('IsBetterMetric'):
                if name.startswith('Lower'):
                    self.targets['direction'] = "-1"
                elif name.startswith('Higher'):
                    self.targets['direction'] = "1"

    def visit_Attribute(self, node):
        """
        Visit an attribute name in the AST.
        """

        self._inherit_superclass(node.attr)

    def visit_Name(self, node):
        """
        Visit a variable name in the AST.
        """

        if self.class_name is not None:
            if node.id in self.TARGETS:
                self.target_name = node.id
            elif node.id in self.OLD_TARGETS:
                self.target_name = self.OLD_TARGETS[node.id]
            else:
                self._inherit_superclass(node.id)

    def visit_Num(self, node):
        """
        Visit a literal number in the AST.
        """

        if self.target_name is not None:
            self.targets[self.target_name] = str(node.n)

    def visit_Str(self, node):
        """
        Visit a literal string in the AST.
        """

        if "Subclass responsibility" in str(node.s):
            self.abstract = True

        if self.target_name is not None:
            self.targets[self.target_name] = str(node.s)

    def visit_Dict(self, node):
        """
        Visit a literal dictionary object in the AST.
        """

        if self.target_name == 'numerical_value_map':
            value = dict(zip([key.s for key in node.keys],
                             [value.n for value in node.values]))
            self.targets[self.target_name] = value

    def visit_Call(self, node):
        """
        Visit a call in the AST.
        """

        if self.target_name is not None and node.func.id == 'LooseVersion':
            arg = LooseVersion(node.args[0].s).version
            number = version_number_to_numerical(arg)
            self.targets[self.target_name] = str(number)

    def visit_Raise(self, node):
        """
        Visit a function definition in the AST.
        """

        if self.class_name is not None:
            if isinstance(node.exc, ast.Name) and \
                node.exc.id == 'NotImplementedError':
                self.abstract = True

class Metric_Target_Tracker(object):
    """
    Class which keeps track of updates to metric targets.
    """

    def __init__(self, from_revision):
        self._all_class_targets = {}
        self._version_targets = []
        self._latest_version = from_revision
        self._latest_date = None

    @classmethod
    def get_from_revision(cls):
        """
        Retrieve the revision that was parsed by an earlier run.
        """

        filename = 'hqlib_targets_update.json'
        if not os.path.exists(filename):
            return None

        with open(filename) as update_file:
            return json.load(update_file)

    def update(self, version, class_targets):
        """
        Update the version targets based on the provided class targets.

        This checks if any targets have been updated compared to previous
        versions of the class targets.
        """

        for class_name, targets in class_targets.items():
            if targets.get('_abstract'):
                continue

            if class_name not in self._all_class_targets or \
                    self._all_class_targets[class_name] != targets:
                version_target = {
                    'class_name': class_name,
                    'version_id': version['version_id'],
                    'commit_date': version['commit_date']
                }
                version_target.update(targets)
                version_target.pop('_abstract')
                self._version_targets.append(version_target)

        self._all_class_targets.update(class_targets)

        commit_date = get_local_datetime(version['commit_date'])
        if self._latest_date is None or commit_date > self._latest_date:
            self._latest_date = commit_date
            self._latest_version = version['version_id']

    def export(self):
        """
        Export the version targets to a JSON file.
        """

        with open('data_hqlib.json', 'w') as targets_file:
            json.dump(self._version_targets, targets_file, indent=4)
        with open('hqlib_targets_update.json', 'w') as update_file:
            json.dump(self._latest_version, update_file)

def main():
    """
    Main entry point.
    """

    args = parse_args()
    modules = (
        'python/qualitylib', 'qualitylib', 'quality_report', 'hqlib',
        'backend/hqlib'
    )
    paths = tuple(os.path.join(mod, 'metric') for mod in modules)

    source = Source.from_type('git', name='quality-report',
                              url='https://github.com/ICTU/quality-report.git')
    repo = Git_Repository.from_source(source, args.repo,
                                      checkout=args.checkout, pull=True)

    start = args.from_revision
    if start is None:
        start = Metric_Target_Tracker.get_from_revision()
    tracker = Metric_Target_Tracker(start)

    for path in paths:
        logging.info('Analyzing path %s', path)
        for version in repo.get_versions(filename=path, from_revision=start,
                                         descending=False, stats=False):
            metric_visitor = Metric_Visitor()
            commit = repo.repo.commit(version['version_id'])
            for file_path in commit.stats.files.keys():
                if not file_path.startswith(path) or '{' in file_path:
                    continue

                try:
                    contents = repo.get_contents(file_path, revision=commit)
                except FileNotFoundException:
                    logging.exception('Could not find file %s in version %s',
                                      file_path, version['version_id'])
                    continue

                try:
                    parse_tree = ast.parse(contents, file_path, 'exec')
                except SyntaxError:
                    logging.exception('Syntax error in file %s in version %s',
                                      file_path, version['version_id'])
                    continue

                metric_visitor.visit(parse_tree)

            tracker.update(version, metric_visitor.class_targets)

    tracker.export()


if __name__ == "__main__":
    main()
