"""Studio consumes recorded metadata and never executes interview providers."""
import test_system

import copy
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.graphs.manage import list_sessions
from app.graphs.studio import build_inspector, clean_report, finalization_inspector
from app.graphs.topology import plan_nodes


def report(kind, roles=()):
    names = plan_nodes(kind, roles)
    return {'session_id': '00000000-0000-4000-8000-000000000001', 'executions': [{
        'thread_id': kind + ':1:v1', 'kind': kind, 'status': 'succeeded',
        'plan_nodes': names, 'plan_matches': True,
        'operations': [{'key':'node:' + name, 'status':'succeeded', 'attempts':1,
                        'duration_ms':index + 1, 'paid':False} for index, name in enumerate(names)]}]}


class StudioInspectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_inspection_streams_real_node_names_without_database_or_provider_execution(self):
        value = report('prepare')
        before = copy.deepcopy(value)
        with patch('app.graphs.manage.inspect', AsyncMock(side_effect=AssertionError('No DB lookup'))), \
             patch('app.ai.model_router.provider_post', AsyncMock(side_effect=AssertionError('No provider'))):
            graph = build_inspector('prepare')
            events = [event async for event in graph.astream({'inspection':value}, stream_mode='updates')]
        self.assertEqual([next(iter(event)) for event in events], ['load_metadata', *plan_nodes('prepare')])
        final = events[-1]['commit']
        self.assertEqual([item['node'] for item in final['observed_nodes']], plan_nodes('prepare'))
        self.assertTrue(all(item['status'] == 'succeeded' for item in final['observed_nodes']))
        self.assertEqual(value, before)

    async def test_failed_and_unrecorded_nodes_remain_visible_without_retry(self):
        value = report('turn')
        value['executions'][0]['status'] = 'failed'
        value['executions'][0]['operations'] = value['executions'][0]['operations'][:3]
        value['executions'][0]['operations'][-1]['status'] = 'failed'
        output = await build_inspector('turn').ainvoke({'inspection':value})
        self.assertEqual(output['mode'], 'read_only_inspection')
        self.assertEqual(output['observed_nodes'][2]['status'], 'failed')
        self.assertEqual(output['observed_nodes'][3]['status'], 'not_recorded')
        self.assertEqual(value['executions'][0]['operations'][-1]['attempts'], 1)

    async def test_plan_mismatch_cannot_be_presented_as_the_selected_pipeline(self):
        value = report('prepare')
        value['executions'][0]['plan_matches'] = False
        with self.assertRaises(ValueError):
            await build_inspector('prepare').ainvoke({'inspection':value})

    async def test_finalization_inspector_preserves_configured_panel_order(self):
        roles = ['manager','hr']
        value = report('finalize', roles)
        graph = finalization_inspector({'configurable': {'panel_roles':roles}})
        output = await graph.ainvoke({'inspection':value})
        self.assertEqual([item['node'] for item in output['observed_nodes']], plan_nodes('finalize', roles))
        with self.assertRaises(ValueError):
            await finalization_inspector({}).ainvoke({'inspection':value})

    async def test_extra_content_is_not_copied_to_inspector_output(self):
        marker = 'PRIVATE_CV_TRANSCRIPT_PASSWORD_MARKER'
        value = report('prepare')
        value['candidate'] = marker
        value['executions'][0]['output'] = marker
        value['executions'][0]['operations'][0]['output'] = marker
        value['executions'][0]['operations'][0]['telemetry'] = {'unexpected_content':marker}
        self.assertNotIn(marker, json.dumps(clean_report(value)))
        output = await build_inspector('prepare').ainvoke({'inspection':value})
        self.assertNotIn(marker, json.dumps(output))


class GraphSessionListTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_system.SystemTests.asyncSetUp
    asyncTearDown = test_system.SystemTests.asyncTearDown
    register = test_system.SystemTests.register
    form = test_system.SystemTests.form
    create = test_system.SystemTests.create

    async def test_list_filters_legacy_sessions_and_omits_candidate_content(self):
        legacy = await self.create()
        self.assertEqual(legacy.status_code, 200)
        with patch.object(settings, 'orchestration_engine', 'langgraph'):
            created = await self.create()
        result = await list_sessions()
        self.assertEqual([item['session_id'] for item in result['sessions']], [created.json()['session_id']])
        self.assertEqual(set(result['sessions'][0]), {'session_id','status','graph_version','created_at'})
        for invalid in (0, 101):
            with self.assertRaises(ValueError):
                await list_sessions(invalid)
