package io.aix.preprocessor;

/** File-path statistics from ordinary commits reachable from the sample's merge base. */
record History(int commits, int daysSinceChange, int authors, float topShare, int additions, int deletions) {}
