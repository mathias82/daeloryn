package dev.daeloryn.benchmark;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Collections;

/** Public post-comparison recovery development cases, not unseen holdouts.
 * Block unresolved retries; do not infer gateway idempotency from a request ID.
 * Exceptions model possible provider outcomes without inventing a reconciliation API.
 */
public final class RecoveryContractSuite {
    static int count, failed;
    static final Clock CLOCK = Clock.fixed(Instant.parse("2026-01-01T00:00:00Z"), ZoneOffset.UTC);
    static class Gateway implements PaymentGateway {
        int charges, refunds;
        boolean timeout, reject, refundFails;
        public String charge(String tenant, String id, long total) {
            if (reject) throw new IllegalStateException("rejected before effect");
            charges++;
            if (timeout) throw new IllegalStateException("remote accepted, response lost");
            return "charge-" + charges;
        }
        public void refund(String id) {
            if (refundFails) throw new IllegalStateException("refund unreachable");
            refunds++;
        }
    }
    static class RejectingStore implements OrderStore {
        public CheckoutResult find(String tenant, String id) { return null; }
        public void save(CheckoutResult result) { throw new IllegalStateException("save rejected"); }
    }
    static StockStore stock() {
        StockStore result = new StockStore();
        result.seed("A", 20); result.seed("B", 20);
        return result;
    }
    static CheckoutRequest request(String sku) {
        return new CheckoutRequest("tenant", "same-id",
            Collections.singletonList(new LineItem(sku, 1, 100)),
            CLOCK.instant().plusSeconds(60));
    }
    static boolean rejected(CheckoutService service, CheckoutRequest request) {
        try { service.checkout(request); return false; }
        catch (RuntimeException expected) { return true; }
    }
    static void record(String id, boolean ok, String details) {
        count++;
        if (!ok) failed++;
        System.out.println((ok ? "PASS " : "FAIL ") + id + " | " + details);
    }
    public static void main(String[] args) {
        Gateway payment = new Gateway(); payment.refundFails = true;
        StockStore inventory = stock();
        CheckoutService service = new CheckoutService(inventory, payment, new RejectingStore(), CLOCK);
        boolean first = rejected(service, request("A"));
        boolean second = rejected(service, request("A"));
        record("no-recharge-after-failed-refund", first && second && payment.charges == 1,
               "charges=" + payment.charges + " stock=" + inventory.available("A"));

        payment = new Gateway(); payment.timeout = true; inventory = stock();
        service = new CheckoutService(inventory, payment, new InMemoryOrderStore(), CLOCK);
        rejected(service, request("A")); rejected(service, request("A"));
        record("no-recharge-after-accepted-but-timed-out-charge", payment.charges == 1,
               "remote accepted charges=" + payment.charges + " stock=" + inventory.available("A"));

        payment = new Gateway(); inventory = stock();
        OrderStore store = new InMemoryOrderStore();
        new CheckoutService(inventory, payment, store, CLOCK).checkout(request("A"));
        service = new CheckoutService(inventory, payment, store, CLOCK);
        boolean mismatch = rejected(service, request("B"));
        record("same-total-different-SKU-rejected-by-new-service", mismatch && payment.charges == 1
               && inventory.available("A") == 19 && inventory.available("B") == 20,
               "rejected=" + mismatch + " charges=" + payment.charges);

        payment = new Gateway(); inventory = stock(); store = new InMemoryOrderStore();
        CheckoutResult original = new CheckoutService(inventory, payment, store, CLOCK).checkout(request("A"));
        CheckoutResult replay = new CheckoutService(inventory, payment, store, CLOCK).checkout(request("A"));
        record("identical-replay-by-new-service-control", original.chargeId().equals(replay.chargeId())
               && payment.charges == 1 && inventory.available("A") == 19,
               "charges=" + payment.charges + " stock=" + inventory.available("A"));

        payment = new Gateway(); payment.reject = true; inventory = stock();
        service = new CheckoutService(inventory, payment, new InMemoryOrderStore(), CLOCK);
        boolean rejected = rejected(service, request("A"));
        record("known-rejection-rolls-back-control", rejected && inventory.available("A") == 20
               && payment.charges == 0, "charges=" + payment.charges + " stock=" + inventory.available("A"));

        System.out.println("SUMMARY total=" + count + " passed=" + (count - failed) + " failed=" + failed);
        System.exit(failed == 0 ? 0 : 1);
    }
}
