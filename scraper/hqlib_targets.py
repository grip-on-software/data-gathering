"""
Script to parse default values for targets and low targets from all versions of
the quality reporting tool.
"""

from argparse import ArgumentParser, Namespace
import ast
from datetime import datetime
from distutils.version import LooseVersion
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
# We need to import a normal import of hqlib before we can import from utils
# pylint: disable=unused-import
import hqlib.domain
from hqlib.utils import version_number_to_numerical
from gatherer.domain import Source
from gatherer.git import Git_Repository
from gatherer.log import Log_Setup
from gatherer.utils import get_local_datetime
from gatherer.version_control.repo import FileNotFoundException, Version

Targets = Dict[str, Union[str, bool, Dict[str, Any]]]

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain quality reporting targets"
    parser = ArgumentParser(description=description)
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

    def __init__(self) -> None:
        self._class_name: Optional[str] = None
        self._target_name: Optional[str] = None
        self._abstract = False
        self._targets: Targets = {}
        self._class_targets: Dict[str, Targets] = {}

    @property
    def class_targets(self) -> Dict[str, Targets]:
        """
        Retrieve the target norms for all classes detected thus far.
        """

        return self._class_targets

    def visit_Assign(self, node: ast.Assign) -> None:
        """
        Visit an assignment node in the AST.
        """

        for target in node.targets:
            self.visit(target)
        self.visit(node.value)
        self._target_name = None

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """
        Visit a type-annotated assignment node in the AST.
        """

        self.visit(node.target)
        if node.value is not None:
            self.visit(node.value)
        self._target_name = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """
        Visit a class definition in the AST.
        """

        self._class_name = node.name
        self._abstract = False
        self._targets = {}

        # Inherit values from superclasses
        for base in node.bases:
            self.visit(base)

        for subnode in node.body:
            self.visit(subnode)

        if self._targets:
            value_map = self._targets.pop('numerical_value_map')
            if isinstance(value_map, dict):
                self._targets = {
                    key: str(value_map[str(value)] if value in value_map else value)
                    for key, value in self._targets.items()
                }

            self._targets['_abstract'] = self._abstract
            self._class_targets[self._class_name] = self._targets

    def _inherit_superclass(self, name: str) -> None:
        if self._class_name is not None:
            if name in self._class_targets:
                self._targets.update(self._class_targets[name])
            elif name.endswith('IsBetterMetric'):
                if name.startswith('Lower'):
                    self._targets['direction'] = "-1"
                elif name.startswith('Higher'):
                    self._targets['direction'] = "1"

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """
        Visit an attribute name in the AST.
        """

        self._inherit_superclass(node.attr)

    def visit_Name(self, node: ast.Name) -> None:
        """
        Visit a variable name in the AST.
        """

        if self._class_name is not None:
            if node.id in self.TARGETS:
                self._target_name = node.id
            elif node.id in self.OLD_TARGETS:
                self._target_name = self.OLD_TARGETS[node.id]
            else:
                self._inherit_superclass(node.id)

    def visit_Num(self, node: ast.Num) -> None:
        """
        Visit a literal number in the AST.
        """

        if self._target_name is not None:
            self._targets[self._target_name] = str(node.n)

    def visit_Str(self, node: ast.Str) -> None:
        """
        Visit a literal string in the AST.
        """

        if "Subclass responsibility" in str(node.s):
            self._abstract = True
        elif self._target_name is not None:
            self._targets[self._target_name] = str(node.s)

    def visit_Dict(self, node: ast.Dict) -> None:
        """
        Visit a literal dictionary object in the AST.
        """

        if self._target_name == 'numerical_value_map':
            value_map: Dict[str, complex] = {}
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Str) and isinstance(value, ast.Num):
                    value_map[key.s] = value.n
            self._targets[self._target_name] = value_map

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """
        Visit a type annotation in the AST.

        Ignore type annotation nodes so that they do not interfere with the
        target name and value parsing.
        """

    def visit_Call(self, node: ast.Call) -> None:
        """
        Visit a call in the AST.
        """

        if self._target_name is not None:
            if not isinstance(node.func, ast.Name):
                logging.warning('Expression in %s for %s: %s', self._class_name,
                                self._target_name, ast.dump(node.func))
            elif node.func.id == 'LooseVersion' and \
                isinstance(node.args[0], ast.Str):
                arg = LooseVersion(node.args[0].s).version
                number = version_number_to_numerical(arg)
                self._targets[self._target_name] = str(number)

    def visit_Raise(self, node: ast.Raise) -> None:
        """
        Visit a function definition in the AST.
        """

        if self._class_name is not None and \
            isinstance(node.exc, ast.Name) and \
            node.exc.id == 'NotImplementedError':
            self._abstract = True

class Metric_Target_Tracker:
    """
    Class which keeps track of updates to metric targets.
    """

    def __init__(self, from_revision: Version) -> None:
        self._all_class_targets: Dict[str, Targets] = {}
        self._version_targets: List[Targets] = []
        self._latest_version = from_revision
        self._latest_date: Optional[datetime] = None

    @classmethod
    def get_from_revision(cls) -> Optional[Version]:
        """
        Retrieve the revision that was parsed by an earlier run.
        """

        update_path = Path('hqlib_targets_update.json')
        if not update_path.exists():
            return None

        with update_path.open('r') as update_file:
            return json.load(update_file)

    def update(self, version: Dict[str, str],
               class_targets: Dict[str, Targets]) -> None:
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
                version_target: Targets = {
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

    def export(self) -> None:
        """
        Export the version targets to a JSON file.
        """

        with open('data_hqlib.json', 'w') as targets_file:
            json.dump(self._version_targets, targets_file, indent=4)
        with open('hqlib_targets_update.json', 'w') as update_file:
            json.dump(self._latest_version, update_file)

def parse(path: str, start: Version, repo: Git_Repository,
          tracker: Metric_Target_Tracker) -> None:
    """
    Parse all files that are changed in revisions from `start` that exist
    within the `path` in the quality report library repository `repo`, and
    collect the detected metric targets in the `tracker`.
    """

    logging.info('Analyzing path %s', path)
    for version in repo.get_versions(filename=path, from_revision=start,
                                     descending=False, stats=False):
        metric_visitor = Metric_Visitor()
        commit = repo.repo.commit(version['version_id'])
        for file_path in commit.stats.files.keys():
            if not file_path.startswith(path) or '{' in file_path:
                continue

            try:
                contents = repo.get_contents(file_path,
                                             revision=version['version_id'])
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

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    modules = (
        'python/qualitylib', 'qualitylib', 'quality_report', 'hqlib',
        'backend/hqlib'
    )
    paths = tuple(str(Path(mod, 'metric')) for mod in modules)

    source = Source.from_type('git', name='quality-report',
                              url='https://github.com/ICTU/quality-report.git')
    repo = Git_Repository.from_source(source, args.repo,
                                      checkout=args.checkout, pull=True)

    start = args.from_revision
    if start is None:
        start = Metric_Target_Tracker.get_from_revision()
    tracker = Metric_Target_Tracker(start)

    for path in paths:
        parse(path, start, repo, tracker)

    tracker.export()


if __name__ == "__main__":
    main()
