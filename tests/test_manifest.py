from __future__ import annotations

import unittest

from core.manifest import ToolManifest


class TestManifest(unittest.TestCase):
    def test_manifest_validation_and_compatibility(self) -> None:
        manifest = ToolManifest.from_dict(
            {
                "tool_id": "calendar_tool",
                "name": "calendar_tool",
                "version": "0.2.1",
                "description": "Manage calendar entries",
                "capabilities": ["read", "create"],
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "compatibility": {"guara_core": ">=0.1.0,<1.0.0"},
            }
        )
        self.assertTrue(manifest.is_compatible_with_core("0.1.0"))
        self.assertTrue(manifest.is_compatible_with_core("0.9.3"))
        self.assertFalse(manifest.is_compatible_with_core("1.0.0"))

    def test_manifest_rejects_invalid_semver(self) -> None:
        with self.assertRaises(ValueError):
            ToolManifest.from_dict(
                {
                    "tool_id": "bad_tool",
                    "name": "bad_tool",
                    "version": "v1",
                    "description": "invalid semver",
                    "capabilities": ["run"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            )
