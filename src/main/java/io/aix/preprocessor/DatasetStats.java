package io.aix.preprocessor;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Locale;
import org.apache.hadoop.conf.Configuration;
import org.apache.parquet.example.data.Group;

/** Summarizes conflict labels without reading the source code column. */
final class DatasetStats {
    static final String USAGE = "aix-preprocessor stats INPUT.parquet";

    static void print(Path input) throws IOException {
        DatasetInput.validate(input);
        var config = new Configuration();
        config.set("parquet.read.schema", "message merge_sample { required boolean has_text_conflict; }");
        long total = 0, positives = 0;
        try (var reader = DatasetInput.reader(input, config)) {
            Group row;
            while ((row = reader.read()) != null) {
                total++;
                if (row.getBoolean("has_text_conflict", 0)) positives++;
            }
        }
        String rate = total == 0 ? "N/A" : String.format(Locale.ROOT, "%.2f%%", 100.0 * positives / total);
        System.out.printf("Samples: %d%nPositives: %d%nPositive rate: %s%n", total, positives, rate);
    }
}
