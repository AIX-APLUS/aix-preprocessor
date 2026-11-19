package io.aix.preprocessor;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Read-only index of ordinary Java path edits and the complete parent graph of the snapshot. */
final class HistoryIndex {
    private static final long DAY = 86_400;
    private record Edit(int commit, int author, int added, int deleted) {}
    private final Map<String, Integer> ids = new HashMap<>();
    private final List<int[]> parents = new ArrayList<>();
    private final long[] times;
    private final Map<String, List<Edit>> paths = new HashMap<>();

    HistoryIndex(Git git) throws Exception {
        var graph = git.read("rev-list", "--parents", "--timestamp", "--all").text().lines().toList();
        times = new long[graph.size()];
        for (String line : graph) {
            var fields = line.split(" ");
            int id = id(fields[1]);
            times[id] = Long.parseLong(fields[0]);
            int[] links = new int[fields.length - 2];
            for (int i = 0; i < links.length; i++) links[i] = id(fields[i + 2]);
            while (parents.size() <= id) parents.add(null);
            parents.set(id, links);
        }
        indexChanges(git);
    }

    private int id(String sha) { return ids.computeIfAbsent(sha, ignored -> ids.size()); }

    private void indexChanges(Git git) throws Exception {
        var authors = new HashMap<String, Integer>();
        // This fixed wildcard is the only non-literal pathspec. Full history visits every parent.
        var process = git.start("--no-literal-pathspecs", "log", "--all", "--full-history", "--no-merges", "--root", "--no-renames",
                "--no-ext-diff", "--no-textconv", "--numstat", "-z", "--format=commit%x00%H%x00%ae", "--", "*.java");
        try (var input = new BufferedInputStream(process.getInputStream())) {
            int commit = -1, author = -1;
            String field;
            while ((field = next(input)) != null) {
                if (field.equals("commit")) {
                    commit = ids.get(next(input));
                    author = authors.computeIfAbsent(next(input), key -> authors.size());
                } else if (field.endsWith(".java")) {
                    var stat = field.stripLeading().split("\t", 3);
                    int added = stat[0].equals("-") ? -1 : Integer.parseInt(stat[0]);
                    int deleted = stat[1].equals("-") ? -1 : Integer.parseInt(stat[1]);
                    paths.computeIfAbsent(stat[2], key -> new ArrayList<>())
                            .add(new Edit(commit, author, added, deleted));
                }
            }
            if (process.waitFor() != 0) throw new IOException("Git history indexing failed");
        } finally { process.destroyForcibly(); }
    }

    private static String next(InputStream in) throws IOException {
        var bytes = new ByteArrayOutputStream();
        int b;
        while ((b = in.read()) > 0) bytes.write(b);
        if (b < 0 && bytes.size() == 0) return null;
        return bytes.toString(StandardCharsets.UTF_8);
    }

    /** Computes reachability once for all files of a merge, including side parents. */
    Snapshot at(String base) {
        int root = ids.get(base);
        var seen = new BitSet(times.length);
        var work = new ArrayDeque<Integer>();
        seen.set(root);
        work.push(root);
        while (!work.isEmpty()) {
            for (int p : parents.get(work.pop())) {
                if (!seen.get(p)) {
                    seen.set(p);
                    work.push(p);
                }
            }
        }
        return new Snapshot(seen, times[root]);
    }

    final class Snapshot {
        private final BitSet reachable;
        private final long timestamp;
        private Snapshot(BitSet reachable, long timestamp) {
            this.reachable = reachable;
            this.timestamp = timestamp;
        }

        History history(String path) {
            var authors = new HashMap<Integer, Integer>();
            long last = Long.MIN_VALUE;
            int count = 0, maximum = 0, added = 0, deleted = 0;
            for (var event : paths.getOrDefault(path, List.of())) {
                long time = times[event.commit()];
                if (!reachable.get(event.commit()) || time > timestamp) continue;
                last = Math.max(last, time);
                if (timestamp - time > 90 * DAY) continue;
                if (event.added() < 0 || event.deleted() < 0) return null;
                added = Math.addExact(added, event.added());
                deleted = Math.addExact(deleted, event.deleted());
                maximum = Math.max(maximum, authors.merge(event.author(), 1, Integer::sum));
                count++;
            }
            if (last == Long.MIN_VALUE) return null;
            return new History(count, Math.toIntExact((timestamp - last) / DAY), authors.size(),
                    count == 0 ? 0f : (float) maximum / count, added, deleted);
        }
    }
}
