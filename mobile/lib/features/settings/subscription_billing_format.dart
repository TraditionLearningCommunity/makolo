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
  final cadence =
      (count > 1 ? count.toString() + ' ' : '') +
      unit +
      (count > 1 && unit != 'mois' ? 's' : '');
  return currency + ' ' + amount + ' / ' + cadence;
}

String subscriptionDateLabel(Object? raw) {
  if (raw == null) return '';
  final instant = DateTime.tryParse(raw.toString());
  if (instant == null) return '';
  final local = instant.toLocal();
  return '${local.day.toString().padLeft(2, '0')}/'
      '${local.month.toString().padLeft(2, '0')}/${local.year}';
}

String subscriptionObligationStatusLabel(Object? raw) {
  switch (raw?.toString()) {
    case 'pending':
      return 'À régler';
    case 'processing':
      return 'En cours de traitement';
    case 'satisfied':
      return 'Réglée';
    case 'waived':
      return 'Dispensée';
    case 'expired':
      return 'Expirée';
    case 'cancelled':
      return 'Annulée';
    case 'refunded':
      return 'Remboursée';
    default:
      return 'État à vérifier';
  }
}

String subscriptionConditionStatusLabel(Object? raw) {
  switch (raw?.toString()) {
    case 'satisfied':
    case 'not_applicable':
      return 'Remplie';
    case 'unsatisfied':
      return 'À corriger';
    case 'pending':
      return 'En attente';
    default:
      return 'À vérifier';
  }
}
