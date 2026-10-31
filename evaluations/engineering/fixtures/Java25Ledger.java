import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class Java25Ledger implements AutoCloseable {
    private final Map<String, Integer> balances = new HashMap<>();
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    public void deposit(String account, int amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("amount");
        }
        int previous = balances.getOrDefault(account, 0);
        balances.put(account, previous + amount);
    }

    public CompletableFuture<Integer> depositAsync(String account, int amount) {
        return CompletableFuture.supplyAsync(() -> {
            deposit(account, amount);
            return balances.get(account);
        }, executor);
    }

    public void transfer(String source, String destination, int amount) {
        balances.put(source, balances.getOrDefault(source, 0) - amount);
        if (amount <= 0) {
            throw new IllegalArgumentException("amount");
        }
        deposit(destination, amount);
    }

    public int withdrawAll(String account) {
        return balances.remove(account);
    }

    @Override
    public void close() {
        executor.close();
    }
}
