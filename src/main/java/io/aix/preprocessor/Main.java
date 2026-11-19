package io.aix.preprocessor;

import java.io.Closeable;
import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.DosFileAttributeView;
import java.util.Arrays;

/** CLI for extracting a single unsplit Java merge dataset from a local repository. */
public final class Main {
    private static final String USAGE = "aix-preprocessor extract REPO [--output FILE] [--threads N] [--rename-limit N] [--repo-id OWNER/REPO]\n"
            + DatasetSplitter.USAGE + "\n" + DatasetStats.USAGE + "\n" + DatasetMerger.USAGE;
    private Main() {}

    /** Runs extraction from local refs and publishes the finished Parquet file. */
    public static void main(String[] args) throws Exception {
        if (args.length == 0 || args[0].equals("--help")) {
            System.out.println(USAGE);
            return;
        }
        if (args[0].equals("extract")) {
            extract(Arrays.copyOfRange(args, 1, args.length));
        } else if (args[0].equals("merge")) {
            DatasetMerger.run(Arrays.copyOfRange(args, 1, args.length));
        } else if (args[0].equals("stats")) {
            if (args.length == 2 && args[1].equals("--help")) {
                System.out.println(DatasetStats.USAGE);
                return;
            }
            if (args.length != 2) {
                System.err.println(DatasetStats.USAGE);
                System.exit(2);
            }
            try {
                DatasetStats.print(Path.of(args[1]));
            } catch (IOException | RuntimeException ex) {
                System.err.println("Cannot read " + args[1] + ". Provide a readable 15-column Parquet file produced by extract or split.");
                System.exit(2);
            }
        } else if (args[0].equals("split")) {
            if (args.length == 2 && args[1].equals("--help")) {
                System.out.println(DatasetSplitter.USAGE);
                return;
            }
            if (args.length != 2 && !(args.length == 4 && args[2].equals("--output-dir"))) {
                throw new IllegalArgumentException(DatasetSplitter.USAGE);
            }
            DatasetSplitter.run(Path.of(args[1]), Path.of(args.length == 4 ? args[3] : "splits"));
        } else if (Files.isDirectory(Path.of(args[0]))) {
            extract(args); // Accept the original repository-first invocation.
        } else {
            throw new IllegalArgumentException("Unknown command: " + args[0] + "\n" + USAGE);
        }
    }

    private static void extract(String[] args) throws Exception {
        if (args.length == 1 && args[0].equals("--help")) {
            System.out.println(USAGE);
            return;
        }
        if (args.length == 0) throw new IllegalArgumentException(USAGE);
        Path source = Path.of(args[0]).toRealPath();
        var original = new Git(source);
        int threads = Math.min(8, Runtime.getRuntime().availableProcessors());
        Path output = Path.of("samples.parquet").toAbsolutePath();
        String repo = null;
        Integer renameLimit = null;
        for (int i = 1; i < args.length; i += 2) {
            if (i + 1 == args.length) throw new IllegalArgumentException(USAGE);
            switch (args[i]) {
                case "--output" -> output = Path.of(args[i + 1]).toAbsolutePath();
                case "--threads" -> threads = Integer.parseInt(args[i + 1]);
                case "--rename-limit" -> {
                    renameLimit = Integer.parseInt(args[i + 1]);
                    if (renameLimit < 0) throw new IllegalArgumentException("--rename-limit must be nonnegative");
                }
                case "--repo-id" -> repo = args[i + 1];
                default -> throw new IllegalArgumentException(USAGE);
            }
        }
        if (threads < 1) throw new IllegalArgumentException("--threads must be positive");
        if (Files.exists(output)) throw new FileAlreadyExistsException(output.toString());
        if (original.read("rev-parse", "--is-shallow-repository").text().strip().equals("true"))
            throw new IOException("Full repository history is required");
        if (repo == null) repo = repositoryId(source, original);
        Files.createDirectories(output.getParent());
        Path temp = Files.createTempDirectory(output.getParent(), ".aix-");
        // Preserve the extraction error if removing the temporary tree fails as well.
        try (Closeable cleanup = () -> deleteTree(temp)) {
            Path mirror = temp.resolve("mirror.git");
            original.read("clone", "--quiet", "--mirror", "--shared", "--", source.toString(), mirror.toString());
            var snapshot = new Git(mirror);
            if (renameLimit != null) snapshot.read("config", "--local", "diff.renameLimit", renameLimit.toString());
            Path partial = temp.resolve("dataset.parquet");
            try (var writer = new DatasetWriter(partial)) {
                Extraction.run(snapshot, repo, threads, writer);
            }
            Files.createLink(output, partial); // Atomically publish without clobbering concurrent output.
        }
        System.err.println("Saved " + output);
    }

    /** Deletes a private extraction tree without descending through links or Windows junctions. */
    static void deleteTree(Path root) throws IOException {
        Files.walkFileTree(root, new SimpleFileVisitor<>() {
            @Override public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attributes)
                    throws IOException {
                // JDK 17 reports directory junctions as both directories and "other" files.
                if (attributes.isOther()) {
                    Files.delete(dir);
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
                deleteFile(file);
                return FileVisitResult.CONTINUE;
            }

            @Override public FileVisitResult postVisitDirectory(Path dir, IOException failure) throws IOException {
                if (failure != null) throw failure;
                Files.delete(dir);
                return FileVisitResult.CONTINUE;
            }
        });
    }

    private static void deleteFile(Path path) throws IOException {
        try {
            Files.delete(path);
        } catch (AccessDeniedException denied) {
            if (File.separatorChar != '\\') throw denied;
            var view = Files.getFileAttributeView(path, DosFileAttributeView.class, LinkOption.NOFOLLOW_LINKS);
            if (view == null) throw denied;
            var attributes = view.readAttributes();
            if (!attributes.isRegularFile() || !attributes.isReadOnly()) throw denied;
            // Git for Windows marks loose objects read-only. Do not change filesystem ACLs.
            view.setReadOnly(false);
            Files.delete(path);
        }
    }

    private static String repositoryId(Path source, Git git) throws Exception {
        var remote = git.run("config", "--get", "remote.origin.url");
        if (remote.status() == 0) {
            String url = remote.text().strip();
            String path = null;
            if (url.contains("://")) path = URI.create(url).getPath();
            else if (url.matches("[^/]+:.+")) path = url.substring(url.indexOf(':') + 1);
            if (path != null && !path.isBlank()) return path.replaceFirst("^/+", "").replaceFirst("\\.git/?$", "");
        }
        return source.getFileName().toString().replaceFirst("\\.git$", "");
    }
}
