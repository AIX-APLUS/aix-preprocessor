package io.aix.preprocessor;

import org.apache.hadoop.conf.Configuration;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.hadoop.ParquetReader;
import org.apache.parquet.hadoop.example.GroupReadSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Keeps the executor's own attributes file out of the extracted rows. Each executor file reaches only
 * child processes through XDG_CONFIG_HOME, and the test JVM's environment is left unchanged.
 */
class GitAttributesIsolationTest {
    private static final Map<String, String> IDENTITY = Map.of(
            "GIT_AUTHOR_NAME", "Tester", "GIT_AUTHOR_EMAIL", "tester@example.test",
            "GIT_AUTHOR_DATE", "2020-01-01T00:00:00Z", "GIT_COMMITTER_NAME", "Tester",
            "GIT_COMMITTER_EMAIL", "tester@example.test", "GIT_COMMITTER_DATE", "2020-01-01T00:00:00Z");
    /** Commands whose output the replay and history index depend on. */
    private static final String[][] PROBES = {
            {"check-attr", "merge", "diff", "--", "Clean.java", "Conflict.java"},
            {"merge-tree", "--write-tree", "--name-only", "left", "right"},
            {"log", "-1", "--numstat", "--format=", "right", "--", "Clean.java"},
    };

    @TempDir Path temp;
    private Path clean, source;

    /** One two-parent merge: Clean.java merges cleanly and Conflict.java has a text conflict. */
    @BeforeEach void createSource() throws Exception {
        clean = Files.createDirectory(temp.resolve("xdg-clean"));
        source = Files.createDirectory(temp.resolve("source"));
        read(source, "init", "-q", "-b", "main");
        String lines = "one\ntwo\nthree\nfour\nfive\nsix\n";
        commit("base", lines, "base\n");
        String base = read(source, "rev-parse", "HEAD").strip();
        read(source, "switch", "-q", "-c", "left");
        commit("left", lines.replace("one", "first"), "left\n");
        read(source, "switch", "-q", "-c", "right", base);
        commit("right", lines.replace("six", "last"), "right\n");
        // Record the merge without running one, so no merge attributes shape the fixture.
        String merge = read(source, "commit-tree", "-p", "left", "-p", "right", "-m", "merge", "left^{tree}").strip();
        read(source, "update-ref", "refs/heads/main", merge);
        read(source, "switch", "-q", "main");
    }

    @Test void userMergeUnionKeepsTextConflictLabels() throws Exception {
        Path union = userAttributes("union", "*.java merge=union\n");
        Path mirror = mirror();
        // Positive control: Git, isolated as the extractor was before this fix, applies the user's file.
        assertEquals("Conflict.java: merge: union\n", read(union, mirror, "check-attr", "merge", "--", "Conflict.java"));
        assertEquals(1, git(clean, mirror, "merge-tree", "--write-tree", "left", "right").status());
        assertEquals(0, git(union, mirror, "merge-tree", "--write-tree", "left", "right").status());

        var expected = extract(clean, "clean");
        assertEquals(Map.of("Clean.java", "false", "Conflict.java", "true"), labels(expected));
        assertEquals(expected, extract(union, "union"));
    }

    @Test void userDiffUnsetKeepsJavaHistoryRows() throws Exception {
        Path binary = userAttributes("nodiff", "*.java -diff\n");
        Path mirror = mirror();
        // Positive control: the same file turns the history index's line counts into binary markers.
        assertEquals("Clean.java: diff: unset\n", read(binary, mirror, "check-attr", "diff", "--", "Clean.java"));
        assertEquals("1\t1\tClean.java", read(clean, mirror, PROBES[2]).strip());
        assertEquals("-\t-\tClean.java", read(binary, mirror, PROBES[2]).strip());

        var expected = extract(clean, "clean");
        assertEquals(Map.of("Clean.java", "false", "Conflict.java", "true"), labels(expected));
        assertEquals(expected, extract(binary, "nodiff"));
    }

    @Test void repositoryAttributesApplyAsBeforeIsolation() throws Exception {
        String rules = "Clean.java -diff\nConflict.java merge=union\n";
        Files.writeString(source.resolve(".gitattributes"), rules);
        read(source, "add", "--", ".gitattributes");
        read(source, "commit", "-q", "-m", "attributes");
        Path mirror = mirror();
        // A bare repository may or may not read HEAD's .gitattributes, depending on Git. Compare only.
        assertSameAsBeforeIsolation(mirror);
        Files.writeString(Files.createDirectories(mirror.resolve("info")).resolve("attributes"), rules);
        // A work tree reads tracked .gitattributes. A bare repository reads $GIT_DIR/info/attributes.
        for (Path repository : List.of(source, mirror)) {
            var results = assertSameAsBeforeIsolation(repository);
            assertEquals("Clean.java: merge: unspecified\nClean.java: diff: unset\n"
                    + "Conflict.java: merge: union\nConflict.java: diff: unspecified\n", results.get(0).text());
            assertEquals(0, results.get(1).status(), "merge=union should resolve Conflict.java");
            assertEquals("-\t-\tClean.java", results.get(2).text().strip());
        }
    }

    /** Compares the extractor's Git with Git isolated as before this fix, using an empty user configuration. */
    private List<Git.Result> assertSameAsBeforeIsolation(Path repository) throws Exception {
        var results = new ArrayList<Git.Result>();
        for (String[] probe : PROBES) {
            var before = git(clean, repository, probe);
            var after = new Git(repository).run(probe);
            String context = repository.getFileName() + ": git " + String.join(" ", probe);
            assertEquals(before.status(), after.status(), context);
            assertEquals(before.text(), after.text(), context);
            results.add(after);
        }
        return results;
    }

    /** Runs the CLI in a child JVM, so the executor's XDG_CONFIG_HOME reaches only its Git processes. */
    private Map<String, Map<String, String>> extract(Path xdg, String name) throws Exception {
        Path output = temp.resolve(name + ".parquet");
        String java = ProcessHandle.current().info().command()
                .orElse(Path.of(System.getProperty("java.home"), "bin", "java").toString());
        var builder = new ProcessBuilder(java, "-cp", System.getProperty("java.class.path"), Main.class.getName(),
                "extract", source.toString(), "--repo-id", "test/attributes", "--threads", "1",
                "--output", output.toString()).redirectErrorStream(true);
        builder.environment().put("XDG_CONFIG_HOME", xdg.toString());
        var process = builder.start();
        process.getOutputStream().close();
        String log = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        assertEquals(0, process.waitFor(), log);
        var rows = new TreeMap<String, Map<String, String>>();
        try (var reader = ParquetReader.builder(new GroupReadSupport(), new org.apache.hadoop.fs.Path(output.toUri()))
                .withConf(new Configuration()).build()) {
            for (Group row; (row = reader.read()) != null;) {
                var fields = new LinkedHashMap<String, String>();
                for (int i = 0; i < row.getType().getFieldCount(); i++)
                    fields.put(row.getType().getFieldName(i), row.getValueToString(i, 0));
                assertEquals(15, fields.size());
                assertNull(rows.put(fields.get("base_path"), fields), "duplicate row");
            }
        }
        return rows;
    }

    private static Map<String, String> labels(Map<String, Map<String, String>> rows) {
        var labels = new TreeMap<String, String>();
        rows.forEach((path, fields) -> labels.put(path, fields.get("has_text_conflict")));
        return labels;
    }

    private Path userAttributes(String name, String rules) throws Exception {
        Path xdg = temp.resolve("xdg-" + name);
        Files.writeString(Files.createDirectories(xdg.resolve("git")).resolve("attributes"), rules);
        return xdg;
    }

    /** A bare mirror like the extractor's, where replay and history indexing run. */
    private Path mirror() throws Exception {
        Path mirror = temp.resolve("probe.git");
        read(source, "clone", "--quiet", "--mirror", "--shared", "--", source.toString(), mirror.toString());
        return mirror;
    }

    private void commit(String message, String cleanCode, String conflictCode) throws Exception {
        Files.writeString(source.resolve("Clean.java"), cleanCode);
        Files.writeString(source.resolve("Conflict.java"), conflictCode);
        read(source, "add", "--", "Clean.java", "Conflict.java");
        read(source, "commit", "-q", "-m", message);
    }

    private String read(Path directory, String... arguments) throws Exception {
        return read(clean, directory, arguments);
    }

    private static String read(Path xdg, Path directory, String... arguments) throws Exception {
        var result = git(xdg, directory, arguments);
        assertEquals(0, result.status(), "git " + String.join(" ", arguments));
        return result.text();
    }

    /** Runs Git with the extractor's environment before this fix, plus the given XDG_CONFIG_HOME. */
    private static Git.Result git(Path xdg, Path directory, String... arguments) throws Exception {
        var command = new ArrayList<>(List.of("git", "--literal-pathspecs", "-C", directory.toString()));
        command.addAll(List.of(arguments));
        var builder = new ProcessBuilder(command).redirectError(ProcessBuilder.Redirect.INHERIT);
        var env = builder.environment();
        env.keySet().removeIf(key -> key.toUpperCase(Locale.ROOT).startsWith("GIT_"));
        env.putAll(Map.of("LC_ALL", "C", "GIT_CONFIG_NOSYSTEM", "1", "GIT_CONFIG_GLOBAL", "/dev/null",
                "GIT_ATTR_NOSYSTEM", "1", "XDG_CONFIG_HOME", xdg.toString()));
        env.putAll(IDENTITY);
        var process = builder.start();
        process.getOutputStream().close();
        byte[] bytes = process.getInputStream().readAllBytes();
        return new Git.Result(process.waitFor(), bytes);
    }
}
