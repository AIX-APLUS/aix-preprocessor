package io.aix.preprocessor;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;

/** Distinguishes full ancestry from both first-parent history and unrelated indexed refs. */
class HistoryIndexTest {
    @TempDir Path repo;

    @Test void sharesOneIndexAcrossBasesWithoutIncludingUnreachableChanges() throws Exception {
        var git = new Git(repo);
        git.read("init", "-b", "main");
        git.read("config", "user.name", "Tester");
        git.read("config", "user.email", "first@example.test");
        String path = "nested/space and [brackets].java";
        Files.createDirectories(repo.resolve("nested"));
        Files.writeString(repo.resolve(path), "root\n");
        git.read("add", ".");
        git.read("commit", "-m", "root");
        String root = git.read("rev-parse", "HEAD").text().strip();

        git.read("switch", "-c", "unrelated");
        Files.writeString(repo.resolve(path), "other\n");
        git.read("commit", "-am", "unreachable from main");
        git.read("switch", "-c", "side", "main");
        git.read("config", "user.email", "second@example.test");
        Files.writeString(repo.resolve(path), "side\n");
        git.read("commit", "-am", "reachable side");
        git.read("switch", "main");
        git.read("merge", "--no-ff", "-s", "ours", "side", "-m", "keep main tree");

        var index = new HistoryIndex(git);
        assertEquals(new History(1, 0, 1, 1f, 1, 0), index.at(root).history(path));
        String tip = git.read("rev-parse", "HEAD").text().strip();
        assertEquals(new History(2, 0, 2, 0.5f, 2, 1), index.at(tip).history(path));
    }
}
