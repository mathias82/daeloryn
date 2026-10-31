package dev.daeloryn.benchmark;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

public final class InMemoryOrderStore implements OrderStore {
    private final ConcurrentMap<String, CheckoutResult> receipts =
            new ConcurrentHashMap<String, CheckoutResult>();

    @Override
    public CheckoutResult find(String tenantId, String requestId) {
        return receipts.get(requestId);
    }

    @Override
    public void save(CheckoutResult result) {
        receipts.put(result.clientRequestId(), result);
    }
}
