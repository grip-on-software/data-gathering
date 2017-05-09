"""
Script to parse default values for targets and low targets from all versions of
the quality reporting tool.
"""

import argparse
import ast
import json
import logging
import os.path
from gatherer.domain import Source
from gatherer.git import Git_Repository
from gatherer.log import Log_Setup
from gatherer.version_control import FileNotFoundException

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain quality reporting targets"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--repo', default='quality-report',
                        help='path to the quality reporting Git repository')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

class Metric_Visitor(ast.NodeVisitor):
    """
    Visitor of an abstract syntax tree of a metrics definition file.
    """

    # pylint: disable=invalid-name
    TARGETS = ('target_value', 'low_target_value', 'perfect_value')

    def __init__(self):
        self.class_name = None
        self.target_name = None
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
        self.targets = {}

        for subnode in node.body:
            self.visit(subnode)

        if self.targets:
            self.class_targets[self.class_name] = self.targets

    def visit_Name(self, node):
        """
        Visit a variable name in the AST.
        """

        if self.class_name is not None and node.id in self.TARGETS:
            self.target_name = node.id

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

        if self.target_name is not None:
            self.targets[self.target_name] = str(node.s)

class Metric_Target_Tracker(object):
    """
    Class which keeps track of updates to metric targets.
    """

    def __init__(self):
        self._all_class_targets = {}
        self._version_targets = []

    def update(self, version, class_targets):
        """
        Update the version targets based on the provided class targets.

        This checks if any targets have been updated compared to previous
        versions of the class targets.
        """

        for class_name, targets in class_targets.items():
            if class_name not in self._all_class_targets or \
                    self._all_class_targets[class_name] != targets:
                version_target = {
                    'class_name': class_name,
                    'version_id': version['version_id'],
                    'commit_date': version['commit_date']
                }
                version_target.update(targets)
                self._version_targets.append(version_target)

        self._all_class_targets.update(class_targets)

    def export(self):
        """
        Export the version targets to a JSON file.
        """

        with open('export/data_hqlib.json', 'w') as targets_file:
            json.dump(self._version_targets, targets_file)

def main():
    """
    Main entry point.
    """

    args = parse_args()
    modules = ('python/qualitylib', 'qualitylib', 'quality_report', 'hqlib')
    paths = tuple(os.path.join(mod, 'metric') for mod in modules)

    source = Source.from_type('git', name='quality-report',
                              url='https://github.com/ICTU/quality-report.git')
    repo = Git_Repository.from_source(source, args.repo)

    tracker = Metric_Target_Tracker()
    for path in paths:
        for version in repo.get_versions(filename=path, descending=False,
                                         stats=False):
            metric_visitor = Metric_Visitor()
            logging.info('%s: %s', version['version_id'], version['commit_date'])
            commit = repo.repo.commit(version['version_id'])
            for file_path in commit.stats.files.keys():
                if not file_path.startswith(path):
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
