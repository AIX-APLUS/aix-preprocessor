package io.aix.preprocessor;

import java.io.*;
import java.nio.charset.StandardCharsets;

/** Shares a persistent cat-file session. Requests and responses are paired under one lock. */
final class BlobReader implements AutoCloseable {
    private final Process process;
    private final DataInputStream input;
    BlobReader(Git git) throws IOException {
        process = git.start("cat-file", "--batch");
        input = new DataInputStream(new BufferedInputStream(process.getInputStream()));
    }

    synchronized byte[] read(String sha) throws IOException {
        var request = process.getOutputStream();
        request.write((sha + "\n").getBytes(StandardCharsets.US_ASCII));
        request.flush();
        var header = new StringBuilder();
        int b;
        while ((b = input.read()) != '\n') {
            if (b < 0) throw new EOFException("Missing blob response for " + sha);
            header.append((char)b);
        }
        String[] parts = header.toString().split(" ");
        if (parts.length != 3 || !parts[0].equals(sha) || !parts[1].equals("blob"))
            throw new IOException("Unexpected cat-file response: " + header);
        byte[] body = new byte[Integer.parseInt(parts[2])];
        input.readFully(body);
        if (input.read() != '\n') throw new IOException("Truncated blob " + sha);
        return body;
    }

    public void close() throws IOException {
        process.destroy();
        input.close();
    }
}
