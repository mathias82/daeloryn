package dev.daeloryn.benchmark;

public final class LineItem {
    private final String sku;
    private final int quantity;
    private final long unitPriceCents;

    public LineItem(String sku, int quantity, long unitPriceCents) {
        this.sku = sku;
        this.quantity = quantity;
        this.unitPriceCents = unitPriceCents;
    }

    public String sku() { return sku; }
    public int quantity() { return quantity; }
    public long unitPriceCents() { return unitPriceCents; }
}
