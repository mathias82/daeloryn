// Deliberately unsafe review fixture for a Java 25-capable project. NEVER deploy.
import java.util.concurrent.Executors;

class Java25Worker {
    void process(Iterable<Runnable> tasks) {
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (var task : tasks) {
                executor.submit(task); // no concurrency bound or backpressure
            }
        }
    }

    void interruptedOperation() {
        try {
            Thread.sleep(1000);
        } catch (InterruptedException ex) {
            // deliberately swallows interrupt; cancellation signal is lost
        }
    }
}
