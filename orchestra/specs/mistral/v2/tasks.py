# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
import logging
import re
import six
from six.moves import queue

from orchestra import exceptions as exc
from orchestra.expressions import base as expr
from orchestra.specs.mistral.v2 import base
from orchestra.specs.mistral.v2 import policies
from orchestra.specs import types
from orchestra.utils import dictionary as dx


LOG = logging.getLogger(__name__)


ON_CLAUSE_SCHEMA = {
    'oneOf': [
        types.NONEMPTY_STRING,
        types.UNIQUE_STRING_OR_YAQL_CONDITION_LIST
    ]
}


class TaskDefaultsSpec(base.Spec):
    _schema = {
        'type': 'object',
        'properties': {
            'concurrency': policies.CONCURRENCY_SCHEMA,
            'retry': policies.RetrySpec,
            'wait-before': policies.WAIT_BEFORE_SCHEMA,
            'wait-after': policies.WAIT_AFTER_SCHEMA,
            'pause-before': policies.PAUSE_BEFORE_SCHEMA,
            'timeout': policies.TIMEOUT_SCHEMA,
            'on-complete': ON_CLAUSE_SCHEMA,
            'on-success': ON_CLAUSE_SCHEMA,
            'on-error': ON_CLAUSE_SCHEMA
        },
        'additionalProperties': False
    }


class TaskSpec(base.Spec):
    _schema = {
        'type': 'object',
        'properties': {
            'join': {
                'oneOf': [
                    {'enum': ['all']},
                    types.POSITIVE_INTEGER
                ]
            },
            'with-items': {
                'oneOf': [
                    types.NONEMPTY_STRING,
                    types.UNIQUE_STRING_LIST
                ]
            },
            'concurrency': policies.CONCURRENCY_SCHEMA,
            'action': types.NONEMPTY_STRING,
            'workflow': types.NONEMPTY_STRING,
            'input': types.NONEMPTY_DICT,
            'publish': types.NONEMPTY_DICT,
            'retry': policies.RetrySpec,
            'wait-before': policies.WAIT_BEFORE_SCHEMA,
            'wait-after': policies.WAIT_AFTER_SCHEMA,
            'pause-before': policies.PAUSE_BEFORE_SCHEMA,
            'timeout': policies.TIMEOUT_SCHEMA,
            'on-complete': ON_CLAUSE_SCHEMA,
            'on-success': ON_CLAUSE_SCHEMA,
            'on-error': ON_CLAUSE_SCHEMA
        },
        'additionalProperties': False,
        'anyOf': [
            {
                'not': {
                    'type': 'object',
                    'required': ['action', 'workflow']
                },
            },
            {
                'oneOf': [
                    {
                        'type': 'object',
                        'required': ['action']
                    },
                    {
                        'type': 'object',
                        'required': ['workflow']
                    }
                ]
            }
        ]
    }

    _context_evaluation_sequence = [
        'join',
        'with-items',
        'concurrency',
        'action',
        'workflow',
        'input',
        'publish',
        'on-complete',
        'on-success',
        'on-error'
    ]

    _context_inputs = [
        'publish'
    ]

    def has_join(self):
        return hasattr(self, 'join') and self.join

    def finalize_context(self, next_task_name, criteria, in_ctx):
        expected_criteria_pattern = "<\% task_state\(\w+\) in \['succeeded'\] \%>"
        new_ctx = {}
        errors = []

        if not re.match(expected_criteria_pattern, criteria[0]):
            return in_ctx, errors

        task_publish_spec = getattr(self, 'publish') or {}

        try:
            new_ctx = {
                var_name: expr.evaluate(var_expr, in_ctx)
                for var_name, var_expr in six.iteritems(task_publish_spec)
            }
        except exc.ExpressionEvaluationException as e:
            errors.append(str(e))

        out_ctx = dx.merge_dicts(in_ctx, new_ctx, overwrite=True)

        for key in list(out_ctx.keys()):
            if key.startswith('__'):
                out_ctx.pop(key)

        return out_ctx, errors


class TaskMappingSpec(base.MappingSpec):
    _schema = {
        'type': 'object',
        'minProperties': 1,
        'patternProperties': {
            '^\w+$': TaskSpec
        }
    }

    def get_task(self, task_name):
        return self[task_name]

    def get_next_tasks(self, task_name, *args, **kwargs):
        task_spec = self.get_task(task_name)
        conditions = kwargs.get('conditions')

        if not conditions:
            conditions = [
                'on-complete',
                'on-error',
                'on-success'
            ]

        next_tasks = []

        for condition in conditions:
            for task in getattr(task_spec, condition) or []:
                next_tasks.append(
                    list(task.items())[0] + (condition,)
                    # The task attribute is either a name or
                    # it's a dict that contains name and expr.
                    if isinstance(task, dict)
                    else (task, None, condition)
                )

        return sorted(next_tasks, key=lambda x: x[0])

    def get_prev_tasks(self, task_name, *args, **kwargs):
        prev_tasks = []
        conditions = kwargs.get('conditions')

        for name, task_spec in six.iteritems(self):
            for next_task in self.get_next_tasks(name, conditions=conditions):
                if task_name == next_task[0]:
                    prev_tasks.append(
                        (name, next_task[1], next_task[2])
                    )

        return sorted(prev_tasks, key=lambda x: x[0])

    def get_start_tasks(self):
        start_tasks = [
            (task_name, None, None)
            for task_name in self.keys()
            if not self.get_prev_tasks(task_name)
        ]

        return sorted(start_tasks, key=lambda x: x[0])

    def is_join_task(self, task_name):
        task_spec = self.get_task(task_name)

        return task_spec.join is not None

    def is_split_task(self, task_name):
        return (
            not self.is_join_task(task_name) and
            len(self.get_prev_tasks(task_name)) > 1
        )

    def in_cycle(self, task_name):
        traversed = []
        q = queue.Queue()

        for task in self.get_next_tasks(task_name):
            q.put(task[0])

        while not q.empty():
            next_task_name = q.get()

            # If the next task matches the original task, then it's in a loop.
            if next_task_name == task_name:
                return True

            # If the next task has already been traversed but didn't match the
            # original task, then there's a loop but the original task is not
            # in the loop.
            if next_task_name in traversed:
                return False

            for task in self.get_next_tasks(next_task_name):
                q.put(task[0])

            traversed.append(next_task_name)

        return False

    def has_cycles(self):
        for task_name, task_spec in six.iteritems(self):
            if self.in_cycle(task_name):
                return True

        return False

    def inspect_context(self, parent=None):
        ctxs = {}
        errors = []
        parent_ctx = parent.get('ctx', []) if parent else []
        rolling_ctx = list(set(parent_ctx))
        q = queue.Queue()

        for task in self.get_start_tasks():
            q.put((task[0], copy.deepcopy(rolling_ctx)))

        while not q.empty():
            task_name, task_ctx = q.get()

            if not task_ctx:
                task_ctx = ctxs.get(task_name, [])

            task_spec = self.get_task(task_name)

            spec_path = parent.get('spec_path') + '.' + task_name
            schema_path = (
                parent.get('schema_path') + '.' + 'properties.' + task_name
            )

            task_parent = {
                'ctx': task_ctx,
                'spec_path': spec_path,
                'schema_path': schema_path
            }

            result = task_spec.inspect_context(parent=task_parent)
            errors.extend(result[0])
            task_ctx = list(set(task_ctx + result[1]))
            rolling_ctx = list(set(rolling_ctx + task_ctx))

            for task in self.get_next_tasks(task_name):
                next_task_spec = self.get_task(task[0])

                if not next_task_spec.has_join():
                    q.put((task[0], task_ctx))
                else:
                    ctxs[task[0]] = list(set(ctxs.get(task[0], []) + task_ctx))
                    q.put((task[0], None))

        return (errors, rolling_ctx)
