package io.aix.preprocessor;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Executes independent Git plumbing commands without a shell or shared working tree. */
record Git(Path directory) {
    record Result(int status, byte[] bytes) {
        String text() { return new String(bytes, StandardCharsets.UTF_8); }
        List<String> fields() { return List.of(text().split("\u0000", -1)); }
    }

    Process start(String... arguments) throws IOException {
        // Git reads the account's attributes file ($XDG_CONFIG_HOME/git/attributes or ~/.config/git/attributes)
        // even without global config. It could relabel conflicts or drop line counts. Replace it for this
        // command only. The repository's .gitattributes and info/attributes still apply.
        var command = new ArrayList<>(List.of("git", "--literal-pathspecs", "-C", directory.toString(),
                "-c", "core.attributesFile=/dev/null"));
        command.addAll(List.of(arguments));
        var builder = new ProcessBuilder(command).redirectError(ProcessBuilder.Redirect.INHERIT);
        Map<String, String> env = builder.environment();
        env.keySet().removeIf(key -> key.startsWith("GIT_"));
        env.put("LC_ALL", "C");
        env.put("GIT_CONFIG_NOSYSTEM", "1");
        env.put("GIT_CONFIG_GLOBAL", "/dev/null");
        env.put("GIT_ATTR_NOSYSTEM", "1");
        return builder.start();
    }

    Result run(String... arguments) throws IOException, InterruptedException {
        var process = start(arguments);
        try (var stdout = process.getInputStream()) {
            var bytes = stdout.readAllBytes();
            return new Result(process.waitFor(), bytes);
        } finally {
            process.destroyForcibly();
        }
    }

    Result read(String... arguments) throws IOException, InterruptedException {
        var result = run(arguments);
        if (result.status() != 0) throw new IOException("git " + arguments[0] + " failed (" + result.status() + ")");
        return result;
    }
}
