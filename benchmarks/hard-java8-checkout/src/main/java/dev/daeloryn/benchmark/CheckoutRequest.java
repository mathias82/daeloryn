package dev.daeloryn.benchmark;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class CheckoutRequest {
    private final String tenantId;
    private final String clientRequestId;
    private final List<LineItem> lines;
    private final Instant expiresAt;

    public CheckoutRequest(String tenantId, String clientRequestId,
                           List<LineItem> lines, Instant expiresAt) {
        this.tenantId = tenantId;
        this.clientRequestId = clientRequestId;
        this.lines = Collections.unmodifiableList(new ArrayList<LineItem>(lines));
        this.expiresAt = expiresAt;
    }

    public String tenantId() { return tenantId; }
    public String clientRequestId() { return clientRequestId; }
    public List<LineItem> lines() { return lines; }
    public Instant expiresAt() { return expiresAt; }
}
