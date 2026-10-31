package dev.daeloryn.benchmark;

public final class CheckoutResult {
    private final String tenantId;
    private final String clientRequestId;
    private final String chargeId;
    private final long totalCents;

    public CheckoutResult(String tenantId, String clientRequestId,
                          String chargeId, long totalCents) {
        this.tenantId = tenantId;
        this.clientRequestId = clientRequestId;
        this.chargeId = chargeId;
        this.totalCents = totalCents;
    }

    public String tenantId() { return tenantId; }
    public String clientRequestId() { return clientRequestId; }
    public String chargeId() { return chargeId; }
    public long totalCents() { return totalCents; }
}
