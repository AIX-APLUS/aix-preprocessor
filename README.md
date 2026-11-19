# aix-preprocessor

`aix-preprocessor` builds a dataset for studying merge conflicts in Java projects. Give it a local Git repository and it writes one Parquet row per Java file that both sides of a merge edited. Each row pairs the source code and file history at the merge base with a label from replaying the merge. You can use the same rows to compare models trained on code, history, or both.

## Build

Install a JDK supported by the bundled Gradle wrapper (tested with JDK 17 and 25) and Git 2.43 or later, then run this from the project directory:

```sh
./gradlew build
```

The Gradle wrapper runs the tests and builds **`build/libs/aix-preprocessor.jar`** with its Java dependencies included. To run it on another machine, copy that JAR and make sure Java 17 or later and Git are on its `PATH`. In IntelliJ IDEA, use the Gradle wrapper and select your installed JDK as the Gradle JVM.

## Extract a dataset

For example, if you have a full clone of JabRef at `../jabref`, run:

```sh
java -jar build/libs/aix-preprocessor.jar extract ../jabref \
  --output jabref.parquet --threads 4
```

Only the repository path is required. The command expects a full Git history and rejects shallow clones. At startup, it indexes commit parents and Java path changes in memory. Each merge shares that index and restricts lookups to ancestors of its own base. The index lasts for one run. When extraction finishes, it prints the number of two-parent merges visited, rows written, and positive samples.

| Option | What it controls | Default |
| --- | --- | --- |
| `--output FILE` | Path for the new Parquet file. Choose a fresh filename for each run. | `samples.parquet` in the current directory |
| `--threads N` | Maximum number of merges to analyze concurrently. Use a positive integer. | Available processors, capped at 8 |
| `--rename-limit N` | Set Git’s `diff.renameLimit` in the temporary mirror. For a warning recommending 3411, try 5000. Higher limits can slow down large comparisons. | Git default |
| `--repo-id ID` | Value written to the `repo_id` column, e.g. `JabRef/jabref`. | Inferred from the origin URL, with the repository directory name as a fallback |

### Which branches does it read?

The extractor uses the refs already present in your clone, including local branches, remote-tracking branches such as `origin/feature`, and tags. A merge reachable from several refs is processed once. This can turn up merges on a feature branch even if the branch never landed on `main`.

Fetching is a separate step. If you want the latest refs covered by your clone's fetch configuration, run `git -C ../jabref fetch origin` before extraction.

## How a file gets its label

For each two-parent merge with a single merge base, the extractor looks for regular `.java` files that existed at the base and changed in content on both sides. It follows renames that Git detects between the base and each parent. It then replays the merge with `git merge-tree` and reads the result for each candidate file.

For example, if both branches edited `Parser.java` and `Lexer.java`, but only `Parser.java` had a text conflict, the dataset gets two rows: `Parser.java` with `true` and `Lexer.java` with `false`. The label describes what Git reproduced with its built-in merge drivers. The original developer may have encountered a different result with custom drivers.

The extractor skips structural and binary conflicts, source it cannot decode as UTF-8, and files for which it cannot compute the required history statistics. It replays merges in a temporary mirror that shares the source repository's Git objects. Leave object pruning until the run finishes. The output directory must support hard links so the writer can publish the completed Parquet file safely.

## Parquet columns

A row is identified by `(repo_id, merge_sha, base_path)`. All 15 columns are required.

| Columns | Type | Contents |
| --- | --- | --- |
| `repo_id`, `merge_sha` | string | Repository identifier and the merge commit being replayed |
| `parent1_sha`, `parent2_sha`, `base_sha` | string | The two parents in Git order and their merge base |
| `base_path`, `base_blob_sha`, `base_code` | string | Repository-relative path, Git blob ID, and full Java source at the base |
| `commit_count_90d`, `author_count_90d` | int32 | Number of commits touching the file and number of distinct author emails in the window |
| `top_author_share_90d` | float32 | Fraction of those commits made by the most frequent author |
| `lines_added_90d`, `lines_deleted_90d` | int32 | Lines added and deleted in the window |
| `days_since_last_change` | int32 | Whole days since the most recent change, even when it predates the window |
| `has_text_conflict` | boolean | Whether Git reported a text conflict for this file |

The 90-day window ends at the merge base's committer timestamp. History includes non-merge commits reachable from that base and uses the file's path at the base. If the file changed names earlier, edits under its old name fall outside these counts. All five 90-day statistics are zero when the window contains no edits.

## Run the tests

```sh
./gradlew test
```

The integration test creates a local repository with side-branch merges, runs the extractor with one and four workers, and reads the Parquet output back to check the rows and labels.

## Split a dataset

```sh
java -jar build/libs/aix-preprocessor.jar split jabref.parquet --output-dir splits
```

The input is a Parquet file produced by `extract`. The command creates
`train.parquet`, `val.parquet`, and `test.parquet` under the output directory
(default `./splits`). Choose a directory where all three filenames are available.
The summary shows each file's row count, percentage of all input rows, and positive count.

Within each repository, all rows for a given file path stay together.
The splitter targets 70/15/15 for both rows and positive examples.
Large file groups can shift the final percentages, and very small datasets can yield
empty splits. Assignment is deterministic even if the input rows are reordered.
Each output preserves all 15 columns and the relative input order of its rows.
