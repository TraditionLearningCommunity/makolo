import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/me_country_choices.dart';

void main() {
  test('Space reuses the Profile country names and canonical ISO codes', () {
    final congo = countryForValue('CD');
    expect(congo, isNotNull);
    expect(congo!.label, 'Congo-Kinshasa');
    expect(countryForValue('Congo-Kinshasa')?.code, 'CD');
    expect(countryForValue('cd')?.label, 'Congo-Kinshasa');

    // No second Space-only catalog and no arbitrary country code accepted.
    expect(makoloCountries.contains(congo), isTrue);
    expect(countryForValue('XX'), isNull);
    expect(countryForValue('Pays fictif'), isNull);
    expect(countryForValue(''), isNull);
  });

  test('country selection stores the code, not the visible label', () {
    final choice = makoloCountries.firstWhere((item) => item.code == 'FR');
    expect(choice.label, 'France');
    expect(countryForValue(choice.label)?.code, 'FR');
  });
}
