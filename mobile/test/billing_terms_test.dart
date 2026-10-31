import 'package:flutter_test/flutter_test.dart';
import 'package:makolo/features/settings/billing_screen.dart';

void main() {
  test('Unknown billing terms are not confused with free', () {
    expect(subscriptionPriceLabel(null), 'Tarif non communiqué');
    expect(subscriptionPriceLabel({}), 'Tarif non communiqué');
    expect(
      subscriptionPriceLabel({
        'amount': '0.00',
        'currency': 'USD',
        'period_unit': 'month',
        'period_count': 1,
      }),
      'Gratuit',
    );
  });

  test('Existing canonical terms display period and currency', () {
    expect(
      subscriptionPriceLabel({
        'amount': '12.00',
        'currency': 'USD',
        'period_unit': 'month',
        'period_count': 1,
      }),
      'USD 12.00 / mois',
    );
    expect(
      subscriptionPriceLabel({
        'amount': '8.50',
        'currency': 'EUR',
        'period_unit': 'year',
        'period_count': 2,
      }),
      'EUR 8.50 / 2 ans',
    );
  });
}
