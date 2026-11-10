const numberFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 2,
});

export function formatCurrencyINR(value: number): string {
  return `₹${numberFormatter.format(value)}`;
}

export function formatQuantity(quantity: number, unit: string): string {
  const label = unit === 'piece' && quantity !== 1 ? 'pieces' : unit;
  return `${numberFormatter.format(quantity)} ${label}`;
}
