package io.aix.preprocessor;

import java.io.IOException;
import java.nio.file.Path;
import org.apache.hadoop.conf.Configuration;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.hadoop.ParquetFileReader;
import org.apache.parquet.hadoop.ParquetReader;
import org.apache.parquet.hadoop.example.GroupReadSupport;
import org.apache.parquet.io.LocalInputFile;

/** Shared schema check and streaming reader for extracted datasets. */
final class DatasetInput {
    static void validate(Path input) throws IOException {
        try (var footer = ParquetFileReader.open(new LocalInputFile(input))) {
            if (!DatasetWriter.SCHEMA.equals(footer.getFooter().getFileMetaData().getSchema())) {
                throw new IOException("Expected the 15-column Parquet schema produced by extract");
            }
        }
    }

    static ParquetReader<Group> reader(Path path, Configuration config) throws IOException {
        return ParquetReader.builder(new GroupReadSupport(), new org.apache.hadoop.fs.Path(path.toUri()))
                .withConf(config).build();
    }
}
