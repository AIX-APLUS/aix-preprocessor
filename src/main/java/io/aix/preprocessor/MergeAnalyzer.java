package io.aix.preprocessor;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

/** Replays one two-parent merge and matches text-conflict messages to jointly edited Java blobs. */
final class MergeAnalyzer {
    private final Git git;
    private final String repo;
    private final Map<String, LongAdder> skipped = new ConcurrentHashMap<>();

    private final HistoryIndex historyIndex;
    private final BlobReader blobs;

    MergeAnalyzer(Git git, String repo, HistoryIndex historyIndex, BlobReader blobs) {
        this.git = git;
        this.repo = repo;
        this.historyIndex = historyIndex;
        this.blobs = blobs;
    }
    private void skip(String reason) { skipped.computeIfAbsent(reason, k -> new LongAdder()).increment(); }
    Map<String, LongAdder> skips() { return new TreeMap<>(skipped); }

    private record Edit(String blob, String destination) {}

    private Map<String, Edit> edits(String base, String tip) throws Exception {
        var fields = git.read("diff", "--raw", "-z", "--no-abbrev", "--find-renames",
                "--no-ext-diff", base, tip).fields();
        var edits = new TreeMap<String, Edit>();
        for (int i = 0; i < fields.size() - 1;) {
            var header = fields.get(i++).split(" ");
            String path = fields.get(i++);
            char status = header[4].charAt(0);
            String dest = status == 'R' || status == 'C' ? fields.get(i++) : path;
            if (path.indexOf(0xfffd) >= 0 || dest.indexOf(0xfffd) >= 0) continue;
            if (!path.endsWith(".java") || !dest.endsWith(".java")) continue;
            if ((status == 'M' || status == 'R') && header[0].startsWith(":100")
                    && header[1].startsWith("100") && !header[2].equals(header[3])) {
                edits.put(path, new Edit(header[2], dest));
            }
        }
        return edits;
    }

    List<Sample> analyze(String revision) throws Exception {
        var ids = revision.split(" ");
        String merge = ids[0], first = ids[1], second = ids[2];
        var bases = git.run("merge-base", "--all", first, second);
        if (bases.status() > 1) throw new java.io.IOException("merge-base failed for " + merge);
        var ancestors = bases.text().lines().toList();
        if (ancestors.size() != 1) { skip("no unique merge base"); return List.of(); }
        String base = ancestors.get(0);
        if (base.equals(first) || base.equals(second)) return List.of();
        var left = edits(base, first);
        if (left.isEmpty()) return List.of();
        var right = edits(base, second);
        left.keySet().retainAll(right.keySet());
        if (left.isEmpty()) return List.of();
        var replay = Replay.of(git, first, second);
        var snapshot = historyIndex.at(base);
        var rows = new ArrayList<Sample>();
        for (var entry : left.entrySet()) {
            String path = entry.getKey();
            Edit edit = entry.getValue();
            var names = List.of(path, edit.destination(), right.get(path).destination());
            if (names.stream().anyMatch(replay.other()::contains)) { skip("non-text conflict"); continue; }
            var bytes = blobs.read(edit.blob());
            String code;
            try { code = StandardCharsets.UTF_8.newDecoder().decode(ByteBuffer.wrap(bytes)).toString(); }
            catch (CharacterCodingException ex) { skip("non-UTF-8 source"); continue; }
            if (code.indexOf(0) >= 0) { skip("binary base"); continue; }
            var history = snapshot.history(path);
            if (history == null) { skip("unavailable history"); continue; }
            rows.add(new Sample(repo, merge, first, second, base, path, edit.blob(), code, history,
                    names.stream().anyMatch(replay.text()::contains)));
        }
        return rows;
    }

    /** Uses Git's machine-readable message types. Unclassified unmerged paths are excluded. */
    private record Replay(Set<String> text, Set<String> other) {
        static Replay of(Git git, String first, String second) throws Exception {
            var result = git.run("merge-tree", "--write-tree", "-z", first, second);
            if (result.status() == 0) return new Replay(Set.of(), Set.of());
            if (result.status() != 1) throw new java.io.IOException("merge-tree failed for " + first + " " + second);
            var fields = result.fields();
            var unmerged = new HashSet<String>();
            var text = new HashSet<String>();
            var other = new HashSet<String>();
            int i = 1;
            while (!fields.get(i).isEmpty()) {
                String stage = fields.get(i++);
                unmerged.add(stage.substring(stage.indexOf('\t') + 1));
            }
            for (i++; i < fields.size() - 1;) {
                int count = Integer.parseInt(fields.get(i++));
                var paths = fields.subList(i, i + count);
                i += count;
                String type = fields.get(i++);
                i++; // Localized human-readable message.
                if (type.equals("CONFLICT (contents)")) text.addAll(paths);
                else if (!type.equals("Auto-merging")) other.addAll(paths);
            }
            unmerged.removeAll(text);
            other.addAll(unmerged);
            return new Replay(text, other);
        }
    }
}
