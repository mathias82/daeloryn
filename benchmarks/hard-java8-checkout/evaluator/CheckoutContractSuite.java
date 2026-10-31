package dev.daeloryn.benchmark;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** Evaluator-owned contract assertions. Public development case, not a blind holdout. */
public final class CheckoutContractSuite {
    private static final Instant NOW = Instant.parse("2026-01-01T00:00:00Z");
    private static final Clock CLOCK = Clock.fixed(NOW, ZoneOffset.UTC);
    private static int failed;
    private static int count;
    private interface Check { void run() throws Exception; }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    private static Throwable rejected(Check operation) throws Exception {
        try { operation.run(); }
        catch (RuntimeException expected) { return expected; }
        throw new AssertionError("operation accepted invalid input or a failed transaction");
    }
    private static CheckoutRequest request(String tenant, String id, LineItem... lines) {
        return new CheckoutRequest(tenant, id, Arrays.asList(lines), NOW.plusSeconds(60));
    }
    private static LineItem line(String sku, int units, long cents) {
        return new LineItem(sku, units, cents);
    }
    private static final class Gateway implements PaymentGateway {
        final AtomicInteger charges = new AtomicInteger();
        final AtomicInteger refunds = new AtomicInteger();
        volatile boolean reject;
        volatile boolean failRefund;
        public String charge(String tenant, String id, long cents) {
            if (reject) throw new IllegalStateException("payment-rejected-before-effect");
            return "charge-" + charges.incrementAndGet();
        }
        public void refund(String id) {
            refunds.incrementAndGet();
            if (failRefund) throw new IllegalStateException("refund-unconfirmed");
        }
    }
    private static final class FailingStore implements OrderStore {
        public CheckoutResult find(String tenant, String id) { return null; }
        public void save(CheckoutResult result) { throw new IllegalStateException("save-failed"); }
    }
    private static final class Fixture {
        final StockStore stock = new StockStore();
        final Gateway gateway = new Gateway();
        final CheckoutService service;
        Fixture() { this(new InMemoryOrderStore()); }
        Fixture(OrderStore store) {
            stock.seed("A", 100);
            stock.seed("B", 0);
            service = new CheckoutService(stock, gateway, store, CLOCK);
        }
        void unchanged() {
            require(stock.available("A") == 100, "rejected operation changed A stock");
            require(gateway.charges.get() == 0, "rejected operation charged payment");
        }
    }
    private static boolean mentions(Throwable error, String marker) {
        return mentions(error, marker, Collections.newSetFromMap(
            new java.util.IdentityHashMap<Throwable, Boolean>()));
    }
    private static boolean mentions(Throwable error, String marker, java.util.Set<Throwable> seen) {
        if (error == null || !seen.add(error)) return false;
        if (String.valueOf(error.getMessage()).contains(marker)) return true;
        if (mentions(error.getCause(), marker, seen)) return true;
        for (Throwable suppressed : error.getSuppressed()) {
            if (mentions(suppressed, marker, seen)) return true;
        }
        return false;
    }
    private static void test(String id, Check check) {
        count++;
        try { check.run(); System.out.println("PASS " + id); }
        catch (Throwable error) {
            failed++;
            System.out.println("FAIL " + id + " " + error.getClass().getSimpleName()
                + ": " + error.getMessage());
        }
    }
    private static void invalidQuantity(final int quantity) throws Exception {
        final Fixture f = new Fixture();
        rejected(() -> f.service.checkout(request("t", "r", line("A", quantity, 5))));
        f.unchanged();
    }
    public static void main(String[] args) {
        test("valid-order", () -> {
            Fixture f = new Fixture();
            CheckoutResult result = f.service.checkout(request("t", "r", line("A", 2, 15)));
            require(result.totalCents() == 30, "incorrect exact total");
            require(f.stock.available("A") == 98 && f.gateway.charges.get() == 1, "wrong effects");
        });
        test("expiry-equality", () -> {
            Fixture f = new Fixture();
            rejected(() -> f.service.checkout(new CheckoutRequest("t", "r",
                Arrays.asList(line("A", 1, 5)), NOW)));
            f.unchanged();
        });
        test("past-expiry-control", () -> {
            Fixture f = new Fixture();
            rejected(() -> f.service.checkout(new CheckoutRequest("t", "r",
                Arrays.asList(line("A", 1, 5)), NOW.minusSeconds(1))));
            f.unchanged();
        });
        test("zero-quantity", () -> invalidQuantity(0));
        test("negative-quantity", () -> invalidQuantity(-1));
        test("excess-quantity", () -> {
            Fixture f = new Fixture(); f.stock.seed("A", 2000);
            rejected(() -> f.service.checkout(request("t", "r", line("A", 1001, 5))));
            require(f.stock.available("A") == 2000 && f.gateway.charges.get() == 0, "invalid side effects");
        });
        test("empty-lines", () -> {
            Fixture f = new Fixture();
            rejected(() -> f.service.checkout(request("t", "r")));
            f.unchanged();
        });
        test("blank-sku", () -> {
            Fixture f = new Fixture(); f.stock.seed(" ", 5);
            rejected(() -> f.service.checkout(request("t", "r", line(" ", 1, 5))));
            require(f.stock.available(" ") == 5, "blank SKU reserved"); f.unchanged();
        });
        for (final long price : new long[] {0, -1}) {
            test("invalid-price-" + price, () -> {
                Fixture f = new Fixture();
                rejected(() -> f.service.checkout(request("t", "r", line("A", 1, price))));
                f.unchanged();
            });
        }
        test("multiplication-overflow", () -> {
            Fixture f = new Fixture();
            rejected(() -> f.service.checkout(request("t", "r", line("A", 2, Long.MAX_VALUE))));
            f.unchanged();
        });
        test("addition-overflow", () -> {
            Fixture f = new Fixture();
            rejected(() -> f.service.checkout(request("t", "r",
                line("A", 1, Long.MAX_VALUE), line("A", 1, 1)))); f.unchanged();
        });
        test("later-line-stock-rollback", () -> {
            Fixture f = new Fixture();
            rejected(() -> f.service.checkout(request("t", "r", line("A", 2, 5), line("B", 1, 5))));
            f.unchanged();
        });
        test("payment-rejection-releases-stock", () -> {
            Fixture f = new Fixture(); f.gateway.reject = true;
            rejected(() -> f.service.checkout(request("t", "r", line("A", 2, 5)))); f.unchanged();
        });
        test("save-failure-compensation", () -> {
            Fixture f = new Fixture(new FailingStore());
            rejected(() -> f.service.checkout(request("t", "r", line("A", 2, 5))));
            require(f.stock.available("A") == 100, "reserved stock leaked");
            require(f.gateway.charges.get() == 1 && f.gateway.refunds.get() == 1, "charge uncompensated");
        });
        test("failed-refund-is-visible", () -> {
            Fixture f = new Fixture(new FailingStore()); f.gateway.failRefund = true;
            Throwable error = rejected(() -> f.service.checkout(request("t", "r", line("A", 2, 5))));
            require(f.gateway.refunds.get() == 1, "refund was not attempted");
            require(mentions(error, "refund-unconfirmed"), "refund failure hidden");
            require(mentions(error, "save-failed"), "original persistence failure lost");
        });
        test("sequential-idempotency-control", () -> {
            Fixture f = new Fixture();
            f.service.checkout(request("t", "r", line("A", 2, 5)));
            f.service.checkout(request("t", "r", line("A", 2, 5)));
            require(f.stock.available("A") == 98 && f.gateway.charges.get() == 1, "duplicate effect");
        });
        test("different-details-same-id", () -> {
            Fixture f = new Fixture(); f.service.checkout(request("t", "r", line("A", 2, 5)));
            rejected(() -> f.service.checkout(request("t", "r", line("A", 3, 5))));
            require(f.stock.available("A") == 98 && f.gateway.charges.get() == 1, "duplicate effect");
        });
        test("tenant-independent-ids", () -> {
            Fixture f = new Fixture();
            f.service.checkout(request("t1", "r", line("A", 2, 5)));
            CheckoutResult second = f.service.checkout(request("t2", "r", line("A", 3, 5)));
            require("t2".equals(second.tenantId()) && second.totalCents() == 15, "cross-tenant result");
            require(f.gateway.charges.get() == 2 && f.stock.available("A") == 95, "tenants share effects");
        });
        test("receipt-isolation", () -> {
            Fixture f = new Fixture(); f.service.checkout(request("t1", "r", line("A", 2, 5)));
            require(f.service.receipt("t2", "r") == null, "cross-tenant disclosure");
        });
        test("concurrent-duplicates", () -> {
            for (int round = 0; round < 10; round++) {
                final Fixture f = new Fixture();
                final CountDownLatch start = new CountDownLatch(1);
                ExecutorService pool = Executors.newFixedThreadPool(8);
                List<Future<CheckoutResult>> tasks = new ArrayList<Future<CheckoutResult>>();
                try {
                    for (int i = 0; i < 8; i++) tasks.add(pool.submit(() -> {
                        if (!start.await(3, TimeUnit.SECONDS)) throw new IllegalStateException("start timeout");
                        return f.service.checkout(request("t", "r", line("A", 2, 5)));
                    }));
                    start.countDown();
                    for (Future<CheckoutResult> task : tasks) task.get(3, TimeUnit.SECONDS);
                    require(f.gateway.charges.get() == 1 && f.stock.available("A") == 98, "duplicate effect");
                } finally { pool.shutdownNow(); }
            }
        });
        test("stock-safe-positive-control", () -> {
            StockStore stock = new StockStore(); stock.seed("A", 3);
            stock.reserve("A", 2); require(stock.available("A") == 1, "reserve incorrect");
            stock.release("A", 2); require(stock.available("A") == 3, "release incorrect");
        });
        test("immutable-request-control", () -> {
            List<LineItem> lines = new ArrayList<LineItem>(); lines.add(line("A", 1, 5));
            CheckoutRequest request = new CheckoutRequest("t", "r", lines, NOW.plusSeconds(60));
            lines.clear(); require(request.lines().size() == 1, "input alias retained");
            rejected(() -> request.lines().clear());
        });
        System.out.println("SUMMARY total=" + count + " passed=" + (count - failed) + " failed=" + failed);
        if (failed > 0) System.exit(1);
    }
}
