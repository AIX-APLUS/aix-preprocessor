package io.aix.preprocessor;

import org.apache.hadoop.conf.Configuration;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.hadoop.ParquetReader;
import org.apache.parquet.hadoop.example.GroupReadSupport;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
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

    private static void change(Path repo, String clean, String conflict) throws Exception {
        Files.writeString(repo.resolve("Clean.java"), clean);
        Files.writeString(repo.resolve("Conflict.java"), conflict + "\n");
        Files.writeString(repo.resolve("ignore.txt"), conflict + "\n");
    }
}
