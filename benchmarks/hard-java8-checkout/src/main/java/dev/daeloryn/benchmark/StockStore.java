package dev.daeloryn.benchmark;

import java.util.HashMap;
import java.util.Map;

public final class StockStore {
    private final Map<String, Integer> available = new HashMap<String, Integer>();

    public synchronized void seed(String sku, int units) {
        if (sku == null || units < 0) throw new IllegalArgumentException();
        available.put(sku, units);
    }

    public synchronized void reserve(String sku, int quantity) {
        int existing = available.getOrDefault(sku, 0);
        if (existing < quantity) throw new IllegalStateException("out of stock");
        available.put(sku, existing - quantity);
    }

    public synchronized void release(String sku, int quantity) {
        int current = available.getOrDefault(sku, 0);
        available.put(sku, Math.addExact(current, quantity));
    }

    public synchronized int available(String sku) {
        return available.getOrDefault(sku, 0);
    }
}
