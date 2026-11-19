import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Base64;
import java.util.StringJoiner;

import org.apache.parquet.column.page.PageReadStore;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.example.data.simple.convert.GroupRecordConverter;
import org.apache.parquet.hadoop.ParquetFileReader;
import org.apache.parquet.io.ColumnIOFactory;
import org.apache.parquet.io.LocalInputFile;
import org.apache.parquet.schema.MessageType;
import org.apache.parquet.schema.MessageTypeParser;

/** Test-only adapter for the Parquet libraries already present in the application jar. */
class DumpParquet {
    private static final MessageType EXPECTED = MessageTypeParser.parseMessageType("""
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

    public static void main(String[] args) throws Exception {
        var output = new PrintWriter(System.out, false, StandardCharsets.US_ASCII);
        try (var file = ParquetFileReader.open(new LocalInputFile(Path.of(args[0])))) {
            var actual = file.getFooter().getFileMetaData().getSchema();
            if (!EXPECTED.equals(actual)) {
                throw new IllegalArgumentException("Unexpected Parquet schema:\n" + actual);
            }
            var columns = new ColumnIOFactory().getColumnIO(actual);
            PageReadStore pages;
            while ((pages = file.readNextRowGroup()) != null) {
                try (var group = pages) {
                    var records = columns.getRecordReader(group, new GroupRecordConverter(actual));
                    for (long index = 0; index < group.getRowCount(); index++) {
                        output.println(encode(records.read()));
                    }
                }
            }
        }
        if (output.checkError()) throw new java.io.IOException("Could not write Parquet rows");
    }

    private static String encode(Group row) {
        var values = new StringJoiner("\t");
        for (int i = 0; i < EXPECTED.getFieldCount(); i++) {
            var type = EXPECTED.getType(i).asPrimitiveType().getPrimitiveTypeName();
            values.add(switch (type) {
                // Preserve arbitrary source bytes, including tabs, CR/LF and Unicode.
                case BINARY -> Base64.getEncoder().encodeToString(row.getBinary(i, 0).getBytes());
                case INT32 -> Integer.toString(row.getInteger(i, 0));
                case FLOAT -> Double.toString(row.getFloat(i, 0));
                case BOOLEAN -> Boolean.toString(row.getBoolean(i, 0));
                default -> throw new IllegalStateException("Unsupported type " + type);
            });
        }
        return values.toString();
    }
}
