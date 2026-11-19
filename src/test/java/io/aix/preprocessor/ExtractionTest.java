package io.aix.preprocessor;

import org.apache.hadoop.conf.Configuration;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.hadoop.ParquetReader;
import org.apache.parquet.hadoop.example.GroupReadSupport;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.File;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.DosFileAttributes;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/** Exercises actual side-branch histories, Git replay, and Parquet round trips. */
class ExtractionTest {
    @TempDir Path temp;

    @Test void extractsSideBranchesAndWritesIdenticalParallelOutput() throws Exception {
        var repo = Files.createDirectory(temp.resolve("repo"));
        var git = new Git(repo);
        git.read("init", "-b", "main");
        git.read("config", "user.email", "test@example.com");
        git.read("config", "user.name", "Test");
        String original = "one\ntwo\nthree\nfour\nfive\nsix\n";
        Files.writeString(repo.resolve("Clean.java"), original);
        Files.writeString(repo.resolve("Conflict.java"), "old\n");
        Files.writeString(repo.resolve("ignore.txt"), "old\n");
        git.read("add", ".");
        git.read("commit", "-m", "initial");
        for (int i = 0; i < 2; i++) {
            git.read("switch", "-c", "topic" + i, "main");
            change(repo, original.replace("one", "first"), "left" + i);
            git.read("commit", "-am", "left");
            git.read("switch", "-c", "side" + i, "main");
            change(repo, original.replace("six", "last"), "right" + i);
            git.read("commit", "-am", "right");
            assertEquals(1, git.run("merge", "--no-edit", "topic" + i).status());
            Files.writeString(repo.resolve("Conflict.java"), "resolved\n");
            Files.writeString(repo.resolve("ignore.txt"), "resolved\n");
            git.read("add", ".");
            git.read("commit", "-m", "resolve");
        }
        git.read("switch", "main");

        Path serial = temp.resolve("serial.parquet"), parallel = temp.resolve("parallel.parquet");
        Main.main(new String[]{repo.toString(), "--output", serial.toString(), "--threads", "1"});
        Main.main(new String[]{"extract", repo.toString(), "--output", parallel.toString(), "--threads", "4"});
        try (var entries = Files.list(temp)) {
            assertTrue(entries.noneMatch(path -> path.getFileName().toString().startsWith(".aix-")),
                    "temporary extraction directory left next to the output");
        }
        assertEquals(-1L, Files.mismatch(serial, parallel));
        var target = new org.apache.hadoop.fs.Path(serial.toUri());
        var counts = new HashMap<String, Integer>();
        try (var reader = ParquetReader.builder(new GroupReadSupport(), target)
                .withConf(new Configuration()).build()) {
            Group row;
            while ((row = reader.read()) != null) {
                assertEquals(15, row.getType().getFieldCount());
                String path = row.getString("base_path", 0);
                counts.merge(path, 1, Integer::sum);
                assertEquals(path.equals("Conflict.java"), row.getBoolean("has_text_conflict", 0));
                assertEquals(path.equals("Clean.java") ? original : "old\n", row.getString("base_code", 0));
                assertEquals(1, row.getInteger("commit_count_90d", 0));
                assertEquals(1f, row.getFloat("top_author_share_90d", 0));
                assertEquals(path.equals("Clean.java") ? 6 : 1, row.getInteger("lines_added_90d", 0));
            }
        }
        assertEquals(Map.of("Clean.java", 2, "Conflict.java", 2), counts);
        assertEquals("", git.read("status", "--porcelain").text());
        assertThrows(java.nio.file.FileAlreadyExistsException.class,
                () -> Main.main(new String[]{repo.toString(), "--output", serial.toString()}));
    }

    @Test void deletesReadOnlyObjectFilesWrittenByGit() throws Exception {
        var tree = Files.createDirectory(temp.resolve("tree"));
        var git = new Git(tree);
        git.read("init", "-q");
        Files.writeString(tree.resolve("blob.txt"), "loose object\n");
        String id = git.read("hash-object", "-w", "--", "blob.txt").text().strip();
        Path object = tree.resolve(".git/objects/" + id.substring(0, 2) + "/" + id.substring(2));
        assertTrue(Files.isRegularFile(object));
        if (File.separatorChar == '\\') {
            assertTrue(Files.readAttributes(object, DosFileAttributes.class).isReadOnly(),
                    "expected a DOS read-only loose object from Git for Windows");
            assertThrows(AccessDeniedException.class, () -> Files.delete(object));
        }
        Main.deleteTree(tree);
        assertFalse(Files.exists(tree));
    }

    @Test void closingBlobReaderReleasesMirrorForImmediateDeletion() throws Exception {
        Path mirror = Files.createDirectory(temp.resolve("mirror.git"));
        Path source = Files.writeString(temp.resolve("example.txt"), "a blob\n");
        var git = new Git(mirror);
        git.read("init", "--bare", "-q");
        String sha = git.read("hash-object", "-w", "--", source.toString()).text().strip();
        try (var blobs = new BlobReader(git)) {
            assertArrayEquals(Files.readAllBytes(source), blobs.read(sha));
        }
        Main.deleteTree(mirror);
        assertFalse(Files.exists(mirror));
    }

    @Test void cleanupPreservesDirectoryLinkTarget() throws Exception {
        Path outside = Files.createDirectory(temp.resolve("outside"));
        Path sentinel = Files.writeString(outside.resolve("sentinel.txt"), "keep me");
        Path tree = Files.createDirectory(temp.resolve("tree"));
        Path link = tree.resolve("link");
        if (File.separatorChar == '\\') {
            // Directory junctions require no symlink privilege on normal NTFS volumes.
            var command = new ProcessBuilder("cmd.exe", "/d", "/c", "mklink", "/J", "tree\\link", "outside")
                    .directory(temp.toFile()).inheritIO().start();
            assertEquals(0, command.waitFor(), "could not create fixture directory junction");
        } else {
            Files.createSymbolicLink(link, outside);
        }
        assertTrue(Files.isSameFile(link.resolve("sentinel.txt"), sentinel));
        Main.deleteTree(tree);
        assertFalse(Files.exists(tree));
        assertEquals("keep me", Files.readString(sentinel));
    }

    private static void change(Path repo, String clean, String conflict) throws Exception {
        Files.writeString(repo.resolve("Clean.java"), clean);
        Files.writeString(repo.resolve("Conflict.java"), conflict + "\n");
        Files.writeString(repo.resolve("ignore.txt"), conflict + "\n");
    }
}
