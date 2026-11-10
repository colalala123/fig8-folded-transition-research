"""Offline tests: never start MCP, HFSS, network, or any subprocess."""
import ast
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import mcp_adapter as m


class AdapterSafety(unittest.TestCase):
    def test_write_is_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'record.json'
            m.write(p,{'failed': True})
            with self.assertRaises(FileExistsError):m.write(p,{'failed':False})
            self.assertTrue(m.read(p)['failed'])

    def test_stop_prevents_launch_before_client(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)
            m.write(r/'authorization.json',{'execution_authorized':True,'total_Analyze_limit':185})
            m.write(r/'STOP.json',{'status':'stopped_before_1a'})
            with patch.object(m,'client',side_effect=AssertionError('must not connect')):
                with self.assertRaisesRegex(RuntimeError,'R4 stopped'):
                    asyncio.run(m.run(r,'launch'))

    def test_bad_authorization_prevents_client(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)
            m.write(r/'authorization.json',{'execution_authorized':False,'total_Analyze_limit':185})
            with patch.object(m,'client',side_effect=AssertionError('must not connect')):
                with self.assertRaisesRegex(RuntimeError,'Authorization mismatch'):
                    asyncio.run(m.run(r,'health'))

    def test_adapter_has_only_explicit_diagnostic_tool_calls(self):
        tree=ast.parse(Path(m.__file__).read_text(encoding='utf-8'))
        names=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='call':
                self.assertIsInstance(n.args[1],ast.Constant)
                names.append(n.args[1].value)
        self.assertEqual(set(names),{'list_aedt_sessions','check_aedt_connection','launch_aedt'})


if __name__=='__main__':unittest.main(verbosity=2)
