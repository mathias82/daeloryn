package dev.daeloryn.benchmark;

public interface PaymentGateway {
    /** Charge may throw when the remote provider rejects or times out. */
    String charge(String tenantId, String requestId, long totalCents);

    /** Refund may throw if the remote provider cannot be reached. */
    void refund(String chargeId);
}
