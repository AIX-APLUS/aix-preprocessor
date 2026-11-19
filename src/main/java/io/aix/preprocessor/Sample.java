package io.aix.preprocessor;

/** One merge and one base-path, including only pre-merge-base features and the replay label. */
record Sample(String repo, String merge, String first, String second, String base, String path,
              String blob, String code, History history, boolean conflict) {}
