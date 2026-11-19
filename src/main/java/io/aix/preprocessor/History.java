package io.aix.preprocessor;

import java.util.HashMap;

/** File-path statistics from ordinary commits reachable from the sample's merge base. */
record History(int commits, int daysSinceChange, int authors, float topShare, int additions, int deletions) {
    private static final long DAY = 86_400;

    /** Returns null for an unobservable last change or non-text numstat in the window. */
    static History collect(Git git, String base, long timestamp, String path) throws Exception {
        var fields = git.read("log", "--full-history", "--no-merges", "--root", "--no-renames",
                "--no-ext-diff", "--no-textconv", "--numstat", "-z", "--format=commit%x00%ct%x00%ae",
                base, "--", path).fields();
        var counts = new HashMap<String, Integer>();
        long last = Long.MIN_VALUE;
        int commits = 0, added = 0, removed = 0, maximum = 0;
        for (int i = 0; i < fields.size() - 1;) {
            if (!fields.get(i++).equals("commit")) throw new IllegalStateException("Unexpected git log record");
            long time = Long.parseLong(fields.get(i++));
            String author = fields.get(i++);
            // A historical directory can occupy today's file path. Match the exact path.
            while (i < fields.size() - 1 && !fields.get(i).equals("commit")) {
                var stat = fields.get(i++).stripLeading().split("\t", 3);
                if (!stat[2].equals(path) || time > timestamp) continue;
                last = Math.max(last, time);
                if (timestamp - time > 90 * DAY) continue;
                if (stat[0].equals("-") || stat[1].equals("-")) return null;
                added = Math.addExact(added, Integer.parseInt(stat[0]));
                removed = Math.addExact(removed, Integer.parseInt(stat[1]));
                maximum = Math.max(maximum, counts.merge(author, 1, Integer::sum));
                commits++;
            }
        }
        if (last == Long.MIN_VALUE) return null;
        return new History(commits, Math.toIntExact((timestamp - last) / DAY), counts.size(),
                commits == 0 ? 0f : (float) maximum / commits, added, removed);
    }
}
