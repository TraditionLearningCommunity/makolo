/// Human-facing formatting for canonical Subscription PlanVersionBillingTerms.
///
/// A missing term never means free, and this helper never calculates a quote.
String subscriptionPriceLabel(Object? raw) {
  if (raw is! Map) return 'Tarif non communiqué';
  final amount = raw['amount']?.toString() ?? '';
  final currency = raw['currency']?.toString() ?? '';
  if (amount.isEmpty || currency.isEmpty) return 'Tarif non communiqué';
  if (num.tryParse(amount) == 0) return 'Gratuit';
  const units = {
    'day': 'jour',
    'week': 'semaine',
    'month': 'mois',
    'year': 'an',
  };
  final unit = units[raw['period_unit']] ?? 'période';
  final count = raw['period_count'] is int
      ? raw['period_count'] as int
      : int.tryParse(raw['period_count']?.toString() ?? '') ?? 1;
  final cadence = (count > 1 ? count.toString() + ' ' : '') +
      unit + (count > 1 && unit != 'mois' ? 's' : '');
  return currency + ' ' + amount + ' / ' + cadence;
}
