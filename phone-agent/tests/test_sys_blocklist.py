"""Tests for the Phase 5 system tools blocklist.

Validates pattern semantics, comment/blank handling, fail-closed behaviour,
and mtime-based reload caching without requiring an Android environment.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Make `import tools.sys_common` work when run as a bare script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import sys_common
from tools.sys_common import SystemToolError, check_blocklist, load_blocklist


class TestSysBlocklist(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        self.patch_config = patch("tools.sys_common.CONFIG_DIR", self.temp_path / "config")
        self.patch_agent = patch("tools.sys_common.AGENT_DIR", self.temp_path / "agent")
        self.patch_config.start()
        self.patch_agent.start()
        
        sys_common._blocklist_cache = None

    def tearDown(self) -> None:
        sys_common._blocklist_cache = None
        self.patch_agent.stop()
        self.patch_config.stop()
        self.temp_dir.cleanup()

    def _write_blocklist(self, content: str, mtime: float | None = None) -> None:
        path = sys_common.CONFIG_DIR / sys_common.BLOCKLIST_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if mtime is not None:
            os.utime(path, (mtime, mtime))

    def _write_default_blocklist(self, content: str) -> None:
        path = sys_common.AGENT_DIR / "config" / sys_common.BLOCKLIST_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_pattern_semantics(self) -> None:
        patterns = r"""^rm\s+(-[a-zA-Z-]+\s+)*/(\s|$|\*)
^mkfs\.
^fdisk
^dd\s+.*if=/dev/(zero|u?random)
mount\s+-o\s+remount,rw\s+/
wipe_data
recovery\s+--wipe_data
^fastboot
flash_image
unlock_bootloader
"""
        self._write_blocklist(patterns)

        blocked = [
            "rm -rf /",
            "rm -rf / --no-preserve-root",
            "rm -rf /*",
            "rm -f -r /",
            "mkfs.ext4 /dev/block/sda",
            "fdisk /dev/block/sda",
            "dd if=/dev/zero of=/dev/block/sda",
            "dd if=/dev/urandom of=/dev/block/sda",
            "mount -o remount,rw /",
            "am broadcast -a masterclear wipe_data",
            "fastboot flashing unlock",
            "unlock_bootloader",
        ]
        
        for cmd in blocked:
            with self.subTest(cmd=cmd):
                with self.assertRaises(SystemToolError) as ctx:
                    check_blocklist(cmd)
                self.assertEqual(ctx.exception.code, "FORBIDDEN_COMMAND")
                self.assertTrue(hasattr(ctx.exception, "code"))
                self.assertTrue(hasattr(ctx.exception, "message"))

        allowed = [
            "echo hello",
            "am force-stop com.android.chrome",
            "pidof -s com.android.chrome",
            # Intentionally out of scope: the list guards bare-root deletion, not every destructive path.
            "rm -rf /data/local/tmp/scratch",
            "dd if=/sdcard/a.img of=/sdcard/b.img",
            "settings get global airplane_mode_on",
        ]
        
        for cmd in allowed:
            with self.subTest(cmd=cmd):
                check_blocklist(cmd)

    def test_comments_and_blanks(self) -> None:
        self._write_blocklist("# comment\n\n^valid$\n   \n# another")
        patterns = load_blocklist()
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].pattern, "^valid$")

    def test_invalid_regex_handling(self) -> None:
        self._write_blocklist("[unclosed\n^valid$\n(unbalanced")
        patterns = load_blocklist()
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].pattern, "^valid$")
        with self.assertRaises(SystemToolError):
            check_blocklist("valid")

    def test_fail_closed_comments_only(self) -> None:
        self._write_blocklist("# just comments\n\n")
        with self.assertRaises(SystemToolError) as ctx:
            check_blocklist("ls")
        self.assertEqual(ctx.exception.code, "BLOCKLIST_UNAVAILABLE")
        self.assertTrue(hasattr(ctx.exception, "message"))

    def test_fail_closed_all_uncompilable(self) -> None:
        self._write_blocklist("[unclosed\n(unbalanced")
        with self.assertRaises(SystemToolError) as ctx:
            check_blocklist("ls")
        self.assertEqual(ctx.exception.code, "BLOCKLIST_UNAVAILABLE")

    def test_fail_closed_missing_entirely(self) -> None:
        with self.assertRaises(SystemToolError) as ctx:
            check_blocklist("ls")
        self.assertEqual(ctx.exception.code, "BLOCKLIST_UNAVAILABLE")
        self.assertTrue(hasattr(ctx.exception, "message"))

    def test_repo_default_copy(self) -> None:
        self._write_default_blocklist("^from_default$")
        patterns = load_blocklist()
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].pattern, "^from_default$")
        
        installed = sys_common.CONFIG_DIR / sys_common.BLOCKLIST_NAME
        self.assertTrue(installed.exists())

    def test_mtime_based_reload(self) -> None:
        self._write_blocklist("^first$", mtime=1000.0)
        self.assertEqual(load_blocklist()[0].pattern, "^first$")

        self._write_blocklist("^second$", mtime=2000.0)
        patterns = load_blocklist()
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].pattern, "^second$")
        
        with self.assertRaises(SystemToolError):
            check_blocklist("second")
        
        # Cache replacement ensures the old pattern no longer blocks.
        check_blocklist("first")


class TestShippedBlocklist(unittest.TestCase):
    """Drive the real config/rish_blocklist.txt, not a copy of it — otherwise
    the shipped file could drift from the patterns the tests assert on and
    nothing would fail."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        repo = Path(__file__).resolve().parent.parent
        # CONFIG_DIR points at an empty temp dir, so _blocklist_path() seeds
        # it by copying the repo default — the file we actually ship.
        self.patch_config = patch("tools.sys_common.CONFIG_DIR",
                                  Path(self.temp_dir.name) / "config")
        self.patch_agent = patch("tools.sys_common.AGENT_DIR", repo)
        self.patch_config.start()
        self.patch_agent.start()
        sys_common._blocklist_cache = None

    def tearDown(self) -> None:
        sys_common._blocklist_cache = None
        self.patch_agent.stop()
        self.patch_config.stop()
        self.temp_dir.cleanup()

    def test_shipped_file_blocks_destructive_commands(self) -> None:
        for cmd in ["rm -rf /", "rm -rf / --no-preserve-root", "rm -rf /*",
                    "mkfs.ext4 /dev/block/sda", "fdisk /dev/block/sda",
                    "dd if=/dev/zero of=/dev/block/sda",
                    "mount -o remount,rw /", "fastboot flashing unlock",
                    "unlock_bootloader", "flash_image boot boot.img"]:
            with self.subTest(cmd=cmd):
                with self.assertRaises(SystemToolError) as ctx:
                    check_blocklist(cmd)
                self.assertEqual(ctx.exception.code, "FORBIDDEN_COMMAND")

    def test_shipped_file_allows_operational_commands(self) -> None:
        # The commands free_ram itself issues must never be self-blocked.
        for cmd in ["echo hello", "pidof -s com.android.chrome",
                    "am force-stop com.android.chrome",
                    "settings get global airplane_mode_on",
                    "device_config put activity_manager max_phantom_processes 2147483647"]:
            with self.subTest(cmd=cmd):
                check_blocklist(cmd)


if __name__ == "__main__":
    unittest.main()
