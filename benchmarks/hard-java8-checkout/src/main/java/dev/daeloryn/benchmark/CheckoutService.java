package dev.daeloryn.benchmark;

import java.time.Clock;

public final class CheckoutService {
    private final StockStore stock;
    private final PaymentGateway payments;
    private final OrderStore orders;
    private final Clock clock;

    public CheckoutService(StockStore stock, PaymentGateway payments,
                           OrderStore orders, Clock clock) {
        this.stock = stock;
        this.payments = payments;
        this.orders = orders;
        this.clock = clock;
    }

    public CheckoutResult checkout(CheckoutRequest request) {
        if (request.expiresAt().isBefore(clock.instant())) {
            throw new IllegalArgumentException("expired");
        }

        CheckoutResult existing = orders.find(request.tenantId(), request.clientRequestId());
        if (existing != null) return existing;

        long totalCents = 0L;
        for (LineItem line : request.lines()) {
            totalCents += line.quantity() * line.unitPriceCents();
            stock.reserve(line.sku(), line.quantity());
        }

        String chargeId = payments.charge(
                request.tenantId(), request.clientRequestId(), totalCents);
        CheckoutResult result = new CheckoutResult(
                request.tenantId(), request.clientRequestId(), chargeId, totalCents);
        orders.save(result);
        return result;
    }

    public CheckoutResult receipt(String tenantId, String clientRequestId) {
        return orders.find(tenantId, clientRequestId);
    }
}
