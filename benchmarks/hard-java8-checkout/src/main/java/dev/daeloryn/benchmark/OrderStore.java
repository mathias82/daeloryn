package dev.daeloryn.benchmark;

public interface OrderStore {
    CheckoutResult find(String tenantId, String requestId);

    /** Persist may throw, including after a payment has been accepted. */
    void save(CheckoutResult result);
}
