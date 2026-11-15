"""Checks for the standalone project layout; run from tarefa2."""
import ast
import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectStructureTests(unittest.TestCase):
    def test_required_files(self):
        for name in ('README.md', 'requirements.txt', '.gitignore',
                     'src/main.py', 'src/swcore_mixin.py',
                     'utils/common/config.py'):
            with self.subTest(file=name):
                self.assertTrue((ROOT / name).is_file())

    def test_python_sources_parse(self):
        for folder in ('src', 'utils'):
            for path in (ROOT / folder).rglob('*.py'):
                with self.subTest(file=str(path.relative_to(ROOT))):
                    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

    def test_imports_and_cache_belong_to_copy(self):
        for folder in ('src', 'utils'):
            for path in (ROOT / folder).rglob('*.py'):
                parts = list(path.relative_to(ROOT).with_suffix('').parts)
                if parts[-1] == '__init__':
                    parts.pop()
                name = '.'.join(parts)
                with self.subTest(module=name):
                    module = importlib.import_module(name)
                    self.assertTrue(Path(module.__file__).resolve().is_relative_to(ROOT))
        from utils.common.cache import CACHE_DIR
        self.assertEqual(CACHE_DIR, ROOT / '.cache')

    def test_no_nested_git_or_linked_source(self):
        self.assertFalse((ROOT / '.git').exists())
        for folder in ('src', 'utils'):
            for path in (ROOT / folder).rglob('*'):
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertFalse(path.is_symlink())
                    self.assertTrue(path.resolve().is_relative_to(ROOT))
                    self.assertNotEqual(path.name, '.git')


if __name__ == '__main__':
    unittest.main()
