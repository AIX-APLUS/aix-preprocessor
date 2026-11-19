"""Check the physical source-preservation oracle on disposable Git fixtures."""

from pathlib import Path
import tempfile
import unittest

from fixture import create_fixture
from verify import check_workspace, git, snapshot


class SourcePreservationTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.repo = create_fixture(self.root / "input")

    def test_git_private_files_and_empty_directories_are_observable(self):
        for name in (".git/hooks/review-hook", ".git/info/exclude", ".git/objects/info/alternates"):
            with self.subTest(name=name):
                path = self.repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                # An empty alternates list is valid and leaves every visible object unchanged.
                path.write_bytes(b"")
                before = snapshot(self.repo)
                check_workspace(self.repo, before, self.root)
                path.write_bytes(b"\n")
                with self.assertRaises(AssertionError):
                    check_workspace(self.repo, before, self.root)
                path.unlink()
                with self.assertRaises(AssertionError):
                    check_workspace(self.repo, before, self.root)

        before = snapshot(self.repo)
        (self.repo / ".git/empty-directory").mkdir()
        with self.assertRaises(AssertionError):
            check_workspace(self.repo, before, self.root)

    def test_repack_preserves_refs_and_object_ids_but_changes_storage(self):
        git(self.repo, "-c", "user.name=Review", "-c", "user.email=review@example.test",
            "tag", "-a", "loose-tag", "-m", "reachable loose object", "HEAD")
        refs = git(self.repo, "show-ref")
        object_list = ("cat-file", "--batch-all-objects", "--batch-check=%(objectname)")
        objects = set(git(self.repo, *object_list).splitlines())
        before = snapshot(self.repo)
        git(self.repo, "repack", "-ad")
        self.assertEqual(refs, git(self.repo, "show-ref"))
        self.assertEqual(objects, set(git(self.repo, *object_list).splitlines()))
        with self.assertRaises(AssertionError):
            check_workspace(self.repo, before, self.root)

    def test_index_encoding_changes_without_changes_to_staged_entries(self):
        git(self.repo, "update-index", "--index-version", "2")
        staged = git(self.repo, "ls-files", "--stage", "-z")
        before = snapshot(self.repo)
        git(self.repo, "update-index", "--index-version", "4")
        self.assertEqual(staged, git(self.repo, "ls-files", "--stage", "-z"))
        with self.assertRaises(AssertionError):
            check_workspace(self.repo, before, self.root)

    def test_symlink_target_content_is_outside_the_snapshot(self):
        target = self.root / "outside"
        target.write_bytes(b"before")
        link = self.repo / "link"
        try:
            link.symlink_to(target)
        except OSError as unavailable:
            if getattr(unavailable, "winerror", None) == 1314:
                self.skipTest("Windows account lacks the symlink creation privilege")
            raise
        before = snapshot(self.repo)
        target.write_bytes(b"after")
        check_workspace(self.repo, before, self.root)
        link.unlink()
        link.symlink_to(self.root / "different-target")
        with self.assertRaises(AssertionError):
            check_workspace(self.repo, before, self.root)
