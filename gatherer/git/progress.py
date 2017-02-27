"""
Module that tracks and logs Git command progress output.
"""

import logging
from git import RemoteProgress

class Progress_Filter(logging.Filter):
    """
    Filters git progress logging messages based on their contextual data.
    """

    def __init__(self, update_ratio=1):
        super(Progress_Filter, self).__init__()
        self._update_ratio = update_ratio
        self._relevant_op_codes = set([RemoteProgress.COUNTING])

    @property
    def update_ratio(self):
        """
        Retrieve the update ratio parameter of this filter.
        """

        return self._update_ratio

    def filter(self, record):
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

    _op_codes = {
        RemoteProgress.COUNTING: 'Counting objects',
        RemoteProgress.COMPRESSING: 'Compressing objects',
        RemoteProgress.WRITING: 'Writing objects',
        RemoteProgress.RECEIVING: 'Receiving objects',
        RemoteProgress.RESOLVING: 'Resolving deltas',
        RemoteProgress.FINDING_SOURCES: 'Finding sources',
        RemoteProgress.CHECKING_OUT: 'Checking out files'
    }

    def __init__(self, update_ratio=1):
        super(Git_Progress, self).__init__()
        self._logger = logging.getLogger()
        self._logger.addFilter(Progress_Filter(update_ratio=update_ratio))

    def update(self, op_code, cur_count, max_count=None, message=''):
        stage_op = op_code & RemoteProgress.STAGE_MASK
        action_op = op_code & RemoteProgress.OP_MASK
        if action_op in self._op_codes:
            log_extra = {
                'op_code': action_op,
                'done': stage_op == RemoteProgress.END,
                'cur_count': cur_count,
                'max_count': max_count
            }
            if max_count is not None and max_count != '':
                ratio = cur_count / float(max_count)
                log_extra['ratio'] = ratio
                count = '{0:>3.0%} ({1:.0f}/{2:.0f})'.format(ratio, cur_count,
                                                             max_count)
            else:
                count = '{0:.0f}'.format(cur_count)

            if stage_op == RemoteProgress.END:
                token = RemoteProgress.TOKEN_SEPARATOR + RemoteProgress.DONE_TOKEN
            else:
                token = ''

            line = '{0}: {1}{2}'.format(self._op_codes[action_op], count, token)
            self._logger.info('Git: %s', line, extra=log_extra)
        else:
            self._logger.warning('Unexpected Git progress opcode: 0x%x',
                                 op_code, extra={'op_code': op_code})

    def line_dropped(self, line):
        self._logger.info('Git: %s', line, extra={'dropped': True})
