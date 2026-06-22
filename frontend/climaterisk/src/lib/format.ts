/** Compact money formatting, e.g. 1234567 -> "$1.2M". */
export function money(value: number, currency = "USD"): string {
  try {
    return new Intl.NumberFormat("en", {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    // Unknown currency code → fall back to a plain compact number.
    return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(
      value,
    );
  }
}
