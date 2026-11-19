package io.aix.preprocessor;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.apache.hadoop.conf.Configuration;
import org.apache.parquet.example.data.Group;

/** Concatenates datasets in input order, retaining only sample keys in memory. */
final class DatasetMerger {
    static final String USAGE = "aix-preprocessor merge INPUT.parquet INPUT.parquet ... --output FILE";
    private record Key(String repo, String merge, String path) {}

    static void run(String[] args) throws IOException {
        if (args.length == 1 && args[0].equals("--help")) {
            System.out.println(USAGE);
            return;
        }
        var inputs = new ArrayList<Path>();
        Path output = null;
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--output") && output == null && i + 1 < args.length) {
                output = Path.of(args[++i]).toAbsolutePath();
            } else if (args[i].startsWith("--")) {
                throw new IllegalArgumentException(USAGE);
            } else {
                inputs.add(Path.of(args[i]));
            }
        }
        if (output == null || inputs.size() < 2) throw new IllegalArgumentException(USAGE);
        if (Files.exists(output)) throw new FileAlreadyExistsException(output.toString());
        Files.createDirectories(output.getParent());
        Path temp = Files.createTempDirectory(output.getParent(), ".merge-");
        Path staged = temp.resolve("merged.parquet");
        long total = 0, positives = 0;
        var seen = new HashSet<Key>();
        var config = new Configuration();
        try {
            try (var writer = new DatasetWriter(staged)) {
                for (Path input : inputs) {
                    long rows = 0;
                    try {
                        DatasetInput.validate(input);
                        try (var reader = DatasetInput.reader(input, config)) {
                            Group row;
                            while ((row = reader.read()) != null) {
                                var key = new Key(row.getString("repo_id", 0), row.getString("merge_sha", 0),
                                        row.getString("base_path", 0));
                                if (!seen.add(key)) throw new IOException("Duplicate sample: " + key);
                                writer.write(row);
                                rows++;
                                if (row.getBoolean("has_text_conflict", 0)) positives++;
                            }
                        }
                    } catch (IOException | RuntimeException ex) {
                        throw new IOException(input + ": " + ex.getMessage(), ex);
                    }
                    total += rows;
                    System.out.printf("%s: %d rows%n", input, rows);
                }
            }
            Files.createLink(output, staged);
        } finally {
            Files.deleteIfExists(staged);
            Files.delete(temp);
        }
        String rate = total == 0 ? "N/A" : String.format(Locale.ROOT, "%.2f%%", 100.0 * positives / total);
        System.out.printf("Saved %s: %d samples, %d positives (%s)%n", output, total, positives, rate);
    }
}
