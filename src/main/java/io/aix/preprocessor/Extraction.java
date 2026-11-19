package io.aix.preprocessor;

import java.util.ArrayDeque;
import java.util.List;
import java.util.Iterator;
import java.util.concurrent.*;

/** Bounded parallel merge analysis with ordered writes and explicit worker shutdown. */
final class Extraction {
    static void run(Git git, String repo, int threads, DatasetWriter writer) throws Exception {
        var revisions = git.read("rev-list", "--all", "--parents", "--min-parents=2", "--max-parents=2")
                .text().lines().iterator();
        if (!revisions.hasNext()) {
            System.err.println("0 two-parent merges, 0 samples");
            return;
        }
        System.err.println("Indexing commit ancestry and Java file changes...");
        var history = new HistoryIndex(git);
        try (var blobs = new BlobReader(git)) {
            analyze(revisions, new MergeAnalyzer(git, repo, history, blobs), threads, writer);
        }
    }

    private static void analyze(Iterator<String> revisions, MergeAnalyzer analyzer,
                                int threads, DatasetWriter writer) throws Exception {
        var executor = Executors.newFixedThreadPool(threads);
        var pending = new ArrayDeque<Future<List<Sample>>>();
        long merges = 0, rows = 0, positives = 0;
        try {
            while (revisions.hasNext() || !pending.isEmpty()) {
                while (revisions.hasNext() && pending.size() < 2L * threads) {
                    String revision = revisions.next();
                    pending.addLast(executor.submit(() -> analyzer.analyze(revision)));
                }
                for (var sample : pending.removeFirst().get()) {
                    writer.write(sample);
                    rows++;
                    if (sample.conflict()) positives++;
                }
                if (++merges % 100 == 0) System.err.printf("%d merges, %d samples%n", merges, rows);
            }
        } finally {
            executor.shutdownNow();
            while (!executor.awaitTermination(1, TimeUnit.SECONDS)) { /* Wait before deleting the mirror. */ }
        }
        System.err.printf("%d two-parent merges, %d samples, %d positives. Skips: %s%n",
                merges, rows, positives, analyzer.skips());
    }
}
