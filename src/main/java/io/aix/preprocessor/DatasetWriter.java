package io.aix.preprocessor;

import java.io.Closeable;
import java.io.IOException;
import java.nio.file.Path;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.example.data.simple.SimpleGroupFactory;
import org.apache.parquet.hadoop.ParquetWriter;
import org.apache.parquet.hadoop.example.ExampleParquetWriter;
import org.apache.parquet.hadoop.metadata.CompressionCodecName;
import org.apache.parquet.io.LocalOutputFile;
import org.apache.parquet.schema.MessageType;
import org.apache.parquet.schema.MessageTypeParser;

/** Single-owner Parquet sink. Every column is required, including zero-activity statistics. */
final class DatasetWriter implements Closeable {
    static final MessageType SCHEMA = MessageTypeParser.parseMessageType("""
            message merge_sample {
              required binary repo_id (STRING);
              required binary merge_sha (STRING);
              required binary parent1_sha (STRING);
              required binary parent2_sha (STRING);
              required binary base_sha (STRING);
              required binary base_path (STRING);
              required binary base_blob_sha (STRING);
              required binary base_code (STRING);
              required int32 commit_count_90d;
              required int32 days_since_last_change;
              required int32 author_count_90d;
              required float top_author_share_90d;
              required int32 lines_added_90d;
              required int32 lines_deleted_90d;
              required boolean has_text_conflict;
            }
            """);
    private final SimpleGroupFactory groups = new SimpleGroupFactory(SCHEMA);
    private final ParquetWriter<Group> writer;

    DatasetWriter(Path file) throws IOException {
        writer = ExampleParquetWriter.builder(new LocalOutputFile(file)).withType(SCHEMA)
                .withCompressionCodec(CompressionCodecName.SNAPPY).build();
    }

    void write(Group row) throws IOException { writer.write(row); }

    void write(Sample s) throws IOException {
        var h = s.history();
        writer.write(groups.newGroup().append("repo_id", s.repo()).append("merge_sha", s.merge())
                .append("parent1_sha", s.first()).append("parent2_sha", s.second())
                .append("base_sha", s.base()).append("base_path", s.path())
                .append("base_blob_sha", s.blob()).append("base_code", s.code())
                .append("commit_count_90d", h.commits()).append("days_since_last_change", h.daysSinceChange())
                .append("author_count_90d", h.authors()).append("top_author_share_90d", h.topShare())
                .append("lines_added_90d", h.additions()).append("lines_deleted_90d", h.deletions())
                .append("has_text_conflict", s.conflict()));
    }

    @Override public void close() throws IOException { writer.close(); }
}
