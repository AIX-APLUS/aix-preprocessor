package io.aix.preprocessor;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.apache.hadoop.conf.Configuration;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.hadoop.ParquetFileReader;
import org.apache.parquet.hadoop.ParquetReader;
import org.apache.parquet.hadoop.example.GroupReadSupport;
import org.apache.parquet.io.LocalInputFile;

/** Assigns entire repository paths to splits, then streams the original rows to disk. */
final class DatasetSplitter {
    static final String USAGE = "aix-preprocessor split INPUT.parquet [--output-dir DIR]";
    private static final List<String> NAMES = List.of("train", "val", "test");
    private static final double[] FRACTIONS = {0.70, 0.15, 0.15};

    private static class Counts {
        long rows;
        long positives;

        void add(long rowCount, long positiveCount) {
            rows += rowCount;
            positives += positiveCount;
        }
    }

    private static final class FileGroup extends Counts {
        final String path;
        final int tieBreaker;
        int split;

        FileGroup(String repo, String path) {
            this.path = path;
            this.tieBreaker = Objects.hash(repo, path);
        }
    }

    static void run(Path input, Path output) throws IOException {
        Files.createDirectories(output);
        for (String name : NAMES) {
            Path target = output.resolve(name + ".parquet");
            if (Files.exists(target)) throw new FileAlreadyExistsException(target.toString());
        }
        try (var footer = ParquetFileReader.open(new LocalInputFile(input))) {
            if (!DatasetWriter.SCHEMA.equals(footer.getFooter().getFileMetaData().getSchema())) {
                throw new IOException("Expected the 15-column Parquet schema produced by extract");
            }
        }
        var repositories = new HashMap<String, Map<String, FileGroup>>();
        var config = new Configuration();
        config.set("parquet.read.schema", """
                message merge_sample {
                  required binary repo_id (STRING);
                  required binary base_path (STRING);
                  required boolean has_text_conflict;
                }
                """);
        try (var reader = reader(input, config)) {
            Group row;
            while ((row = reader.read()) != null) {
                String repo = row.getString("repo_id", 0);
                String path = row.getString("base_path", 0);
                repositories.computeIfAbsent(repo, ignored -> new HashMap<>())
                        .computeIfAbsent(path, key -> new FileGroup(repo, key))
                        .add(1, row.getBoolean("has_text_conflict", 0) ? 1 : 0);
            }
        }
        repositories.values().forEach(groups -> assign(groups.values()));

        Path stage = Files.createTempDirectory(output, ".split-");
        var published = new ArrayList<Path>();
        Counts[] counts = {new Counts(), new Counts(), new Counts()};
        try {
            try (var train = new DatasetWriter(stage.resolve("train.parquet"));
                 var val = new DatasetWriter(stage.resolve("val.parquet"));
                 var test = new DatasetWriter(stage.resolve("test.parquet"));
                 var reader = reader(input, new Configuration())) {
                var writers = List.of(train, val, test);
                Group row;
                while ((row = reader.read()) != null) {
                    int split = repositories.get(row.getString("repo_id", 0)).get(row.getString("base_path", 0)).split;
                    writers.get(split).write(row);
                    counts[split].add(1, row.getBoolean("has_text_conflict", 0) ? 1 : 0);
                }
            }
            for (String name : NAMES) {
                String file = name + ".parquet";
                published.add(Files.createLink(output.resolve(file), stage.resolve(file)));
            }
        } catch (IOException ex) {
            for (Path path : published) Files.delete(path);
            throw ex;
        } finally {
            for (String name : NAMES) Files.deleteIfExists(stage.resolve(name + ".parquet"));
            Files.delete(stage);
        }
        long total = Arrays.stream(counts).mapToLong(c -> c.rows).sum();
        for (int i = 0; i < counts.length; i++) {
            var c = counts[i];
            System.out.printf(Locale.ROOT, "%s: %d rows (%.2f%% of %d), %d positives%n",
                    output.resolve(NAMES.get(i) + ".parquet"), c.rows,
                    total == 0 ? 0 : 100.0 * c.rows / total, total, c.positives);
        }
    }

    private static ParquetReader<Group> reader(Path path, Configuration config) throws IOException {
        return ParquetReader.builder(new GroupReadSupport(), new org.apache.hadoop.fs.Path(path.toUri()))
                .withConf(config).build();
    }

    /** Greedily minimizes the increase in squared error of row and positive shares. */
    private static void assign(Collection<FileGroup> groups) {
        var ordered = new ArrayList<>(groups);
        ordered.sort(Comparator.comparingLong((FileGroup g) -> g.rows).reversed()
                .thenComparingInt(g -> g.tieBreaker).thenComparing(g -> g.path));
        long rows = ordered.stream().mapToLong(g -> g.rows).sum();
        long positives = ordered.stream().mapToLong(g -> g.positives).sum();
        Counts[] assigned = {new Counts(), new Counts(), new Counts()};
        for (var group : ordered) {
            double best = Double.POSITIVE_INFINITY;
            for (int i = 0; i < assigned.length; i++) {
                double cost = delta(assigned[i].rows, group.rows, rows, FRACTIONS[i])
                        + delta(assigned[i].positives, group.positives, positives, FRACTIONS[i]);
                if (cost < best) {
                    best = cost;
                    group.split = i;
                }
            }
            assigned[group.split].add(group.rows, group.positives);
        }
    }

    private static double delta(long before, long added, long total, double target) {
        if (total == 0) return 0;
        double error = (double) before / total - target;
        double next = error + (double) added / total;
        return next * next - error * error;
    }
}
