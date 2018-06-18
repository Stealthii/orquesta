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

from orchestra import exceptions as exc
from orchestra import graphing
from orchestra.tests.unit import base


EXPECTED_WF_GRAPH = {
    'directed': True,
    'graph': [],
    'nodes': [
        {
            'id': 'task1'
        },
        {
            'id': 'task2'
        },
        {
            'id': 'task3'
        },
        {
            'id': 'task4'
        },
        {
            'id': 'task5',
            'barrier': '*'
        },
        {
            'id': 'task6'
        },
        {
            'id': 'task7'
        },
        {
            'id': 'task8'
        },
        {
            'id': 'task9'
        }
    ],
    'adjacency': [
        [
            {
                'id': 'task2',
                'key': 0,
                'criteria': None
            },
            {
                'id': 'task4',
                'key': 0,
                'criteria': None
            },
            {
                'id': 'task7',
                'key': 0,
                'criteria': None
            },
            {
                'id': 'task9',
                'key': 0,
                'criteria': None
            }
        ],
        [
            {
                'id': 'task3',
                'key': 0,
                'criteria': None
            }
        ],
        [
            {
                'id': 'task5',
                'key': 0,
                'criteria': None
            }
        ],
        [
            {
                'id': 'task5',
                'key': 0,
                'criteria': None
            }
        ],
        [
            {
                'id': 'task6',
                'key': 0,
                'criteria': None
            }
        ],
        [],
        [
            {
                'id': 'task8',
                'key': 0,
                'criteria': None
            }
        ],
        [
            {
                'id': 'task9',
                'key': 0,
                'criteria': None
            }
        ],
        []
    ],
    'multigraph': True
}


class WorkflowGraphTest(base.WorkflowGraphTest):

    def _add_tasks(self, wf_graph):
        for i in range(1, 10):
            wf_graph.add_task('task' + str(i))

    def _add_transitions(self, wf_graph):
        wf_graph.add_transition('task1', 'task2')
        wf_graph.add_transition('task2', 'task3')
        wf_graph.add_transition('task1', 'task4')
        wf_graph.add_transition('task3', 'task5')
        wf_graph.add_transition('task4', 'task5')
        wf_graph.add_transition('task5', 'task6')
        wf_graph.add_transition('task1', 'task7')
        wf_graph.add_transition('task7', 'task8')
        wf_graph.add_transition('task1', 'task9')
        wf_graph.add_transition('task8', 'task9')

    def _add_barriers(self, wf_graph):
        wf_graph.update_task('task5', barrier='*')

    def _prep_graph(self):
        wf_graph = graphing.WorkflowGraph()

        self._add_tasks(wf_graph)
        self._add_transitions(wf_graph)
        self._add_barriers(wf_graph)

        return wf_graph

    def test_graph(self):
        wf_graph = self._prep_graph()

        self.assert_graph_equal(wf_graph, EXPECTED_WF_GRAPH)

    def test_graph_roots(self):
        wf_graph = self._prep_graph()

        expected = [{'id': 'task1', 'name': 'task1'}]

        self.assertListEqual(wf_graph.roots, expected)

    def test_skip_add_tasks(self):
        wf_graph = graphing.WorkflowGraph()

        self._add_transitions(wf_graph)
        self._add_barriers(wf_graph)

        self.assert_graph_equal(wf_graph, EXPECTED_WF_GRAPH)

    def test_duplicate_add_tasks(self):
        wf_graph = self._prep_graph()

        self._add_tasks(wf_graph)

        self.assert_graph_equal(wf_graph, EXPECTED_WF_GRAPH)

    def test_duplicate_add_transitions(self):
        wf_graph = self._prep_graph()

        self._add_transitions(wf_graph)

        self.assert_graph_equal(wf_graph, EXPECTED_WF_GRAPH)

    def test_get_task(self):
        wf_graph = self._prep_graph()

        expected = {'id': 'task1'}
        self.assertDictEqual(wf_graph.get_task('task1'), expected)

    def test_get_nonexistent_task(self):
        wf_graph = self._prep_graph()

        self.assertRaises(
            exc.InvalidTask,
            wf_graph.get_task,
            'task999'
        )

    def test_update_task(self):
        wf_graph = self._prep_graph()

        expected = {'id': 'task1'}
        self.assertDictEqual(wf_graph.get_task('task1'), expected)

        # Update task with new attributes.
        wf_graph.update_task('task1', attr1='foobar', attr2='fubar')
        expected = {'id': 'task1', 'attr1': 'foobar', 'attr2': 'fubar'}
        self.assertDictEqual(wf_graph.get_task('task1'), expected)

        # Update an existing attribute.
        wf_graph.update_task('task1', attr2='foobar')
        expected = {'id': 'task1', 'attr1': 'foobar', 'attr2': 'foobar'}
        self.assertDictEqual(wf_graph.get_task('task1'), expected)

    def test_update_nonexistent_task(self):
        wf_graph = self._prep_graph()

        self.assertRaises(
            exc.InvalidTask,
            wf_graph.update_task,
            'task999',
            attr1='foobar'
        )

    def test_get_task_attributes(self):
        wf_graph = self._prep_graph()

        wf_graph.update_task('task1', attr1='foobar')
        wf_graph.update_task('task2', attr1='foobar')
        wf_graph.update_task('task4', attr1='foobar')

        expected = {
            'task1': 'foobar',
            'task2': 'foobar',
            'task3': None,
            'task4': 'foobar',
            'task5': None,
            'task6': None,
            'task7': None,
            'task8': None,
            'task9': None
        }

        self.assertDictEqual(wf_graph.get_task_attributes('attr1'), expected)

    def test_get_transition(self):
        wf_graph = self._prep_graph()

        expected = ('task1', 'task2', 0, {'criteria': None})
        self.assertEqual(wf_graph.get_transition('task1', 'task2'), expected)

    def test_get_nonexistent_transition(self):
        wf_graph = self._prep_graph()

        self.assertRaises(
            exc.InvalidTaskTransition,
            wf_graph.get_transition,
            'task998',
            'task999'
        )

    def test_get_ambiguous_transition(self):
        wf_graph = graphing.WorkflowGraph()

        self._add_tasks(wf_graph)

        wf_graph._graph.add_edge('task1', 'task2')
        wf_graph._graph.add_edge('task1', 'task2')

        self.assertRaises(
            exc.AmbiguousTaskTransition,
            wf_graph.get_transition,
            'task1',
            'task2'
        )

    def test_add_ambiguous_transition(self):
        wf_graph = graphing.WorkflowGraph()

        self._add_tasks(wf_graph)

        wf_graph._graph.add_edge('task1', 'task2')
        wf_graph._graph.add_edge('task1', 'task2')

        self.assertRaises(
            exc.AmbiguousTaskTransition,
            wf_graph.add_transition,
            'task1',
            'task2'
        )

    def test_get_next_transitions(self):
        wf_graph = self._prep_graph()

        expected_transitions = [
            ('task1', 'task2', 0, {'criteria': None}),
            ('task1', 'task4', 0, {'criteria': None}),
            ('task1', 'task7', 0, {'criteria': None}),
            ('task1', 'task9', 0, {'criteria': None})
        ]

        self.assertListEqual(
            sorted(wf_graph.get_next_transitions('task1')),
            sorted(expected_transitions)
        )

    def test_get_prev_transitions(self):
        wf_graph = self._prep_graph()

        expected_transitions = [
            ('task3', 'task5', 0, {'criteria': None}),
            ('task4', 'task5', 0, {'criteria': None})
        ]

        self.assertListEqual(
            sorted(wf_graph.get_prev_transitions('task5')),
            sorted(expected_transitions)
        )

    def test_barrier_task(self):
        wf_graph = self._prep_graph()

        self.assertTrue(wf_graph.has_barrier('task5'))
        self.assertFalse(wf_graph.has_barrier('task9'))

    def test_split_from_reused_task(self):
        wf_graph = self._prep_graph()

        self.assertFalse(
            len(wf_graph.get_prev_transitions('task5')) > 1 and
            not wf_graph.has_barrier('task5')
        )

        self.assertTrue(
            len(wf_graph.get_prev_transitions('task9')) > 1 and
            not wf_graph.has_barrier('task9')
        )
