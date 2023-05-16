"""
Module that tracks and logs Git command progress output.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import logging
from typing import Dict, NamedTuple, Optional, Set, Union, overload
from git import RemoteProgress

LogRecord = NamedTuple('LogRecord', [('dropped', bool),
                                     ('done', bool),
                                     ('op_code', int),
                                     ('ratio', float),
                                     ('cur_count', int)])

class Progress_Filter(logging.Filter):
    """
    Filters git progress logging messages based on their contextual data.
    """

    def __init__(self, update_ratio: int = 1) -> None:
        super().__init__()
        self._update_ratio = update_ratio
        self._relevant_op_codes: Set[int] = {RemoteProgress.COUNTING}

    @property
    def update_ratio(self) -> int:
        """
        Retrieve the update ratio parameter of this filter.
        """

        return self._update_ratio

    # pylint: disable=function-redefined
    @overload
    def filter(self, record: LogRecord) -> bool:
        ...

    @overload
    def filter(self, record: logging.LogRecord) -> bool:
        ...

    def filter(self, record) -> bool:
        if hasattr(record, 'dropped') and record.dropped:
            return True

        if not hasattr(record, 'done'):
            return True

        if record.done or record.op_code in self._relevant_op_codes:
            return True
        if hasattr(record, 'ratio'):
            if int(record.ratio * 100) % self._update_ratio == 0:
                return True
        elif record.cur_count % self._update_ratio == 0:
            return True

        return False

class Git_Progress(RemoteProgress):
    """
    Progress delegate which outputs Git progress to logging.
    """

    _op_codes: Dict[int, str] = {
        RemoteProgress.COUNTING: 'Counting objects',
        RemoteProgress.COMPRESSING: 'Compressing objects',
        RemoteProgress.WRITING: 'Writing objects',
        RemoteProgress.RECEIVING: 'Receiving objects',
        RemoteProgress.RESOLVING: 'Resolving deltas',
        RemoteProgress.FINDING_SOURCES: 'Finding sources',
        RemoteProgress.CHECKING_OUT: 'Checking out files'
    }

    def __init__(self, update_ratio: int = 1) -> None:
        super().__init__()
        self._logger = logging.getLogger()
        self._logger.addFilter(Progress_Filter(update_ratio=update_ratio))

    def update(self, op_code: int, cur_count: int,
               max_count: Optional[int] = None, message: str = '') -> None:
        stage_op = op_code & RemoteProgress.STAGE_MASK
        action_op = op_code & RemoteProgress.OP_MASK
        if action_op in self._op_codes:
            log_extra: Dict[str, Union[bool, int, float]] = {
                'op_code': action_op,
                'done': stage_op == RemoteProgress.END,
                'cur_count': cur_count
            }
            if max_count is not None and max_count != '':
                ratio = cur_count / float(max_count)
                log_extra['ratio'] = ratio
                count = f'{ratio:>3.0%} ({cur_count:.0f}/{max_count:.0f})'
            else:
                count = f'{cur_count:.0f}'

            token = ''
            if stage_op == RemoteProgress.END:
                token = f'{RemoteProgress.TOKEN_SEPARATOR}{RemoteProgress.DONE_TOKEN}'

            text = self._op_codes[action_op]
            line = f'{text}: {count}{token}'
            self._logger.info('Git: %s', line, extra=log_extra)
        else:
            self._logger.warning('Unexpected Git progress opcode: 0x%x',
                                 op_code, extra={'op_code': op_code})

    def line_dropped(self, line: str) -> None:
        self._logger.info('Git: %s', line, extra={'dropped': True})
