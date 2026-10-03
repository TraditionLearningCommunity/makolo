import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/dev/scenarios/presentation_fixture_resolver.dart';
import 'package:makolo_mobile/dev/scenarios/presentation_scenarios.dart';

void main() {
  test('scenario clock is fixed and timezone independent', () {
    expect(
      PresentationScenarioClock.fixedNow.toIso8601String(),
      '2026-11-12T13:42:00.000Z',
    );
  });

  test('scenario ids are unique and every Golden G01-G14 is represented', () {
    final ids = PresentationScenarioCatalog.all
        .map((scenario) => scenario.id)
        .toList(growable: false);
    expect(ids.toSet().length, ids.length);
    expect(PresentationScenarioCatalog.goldenScenarioIds.length, 14);
    for (final id in PresentationScenarioCatalog.goldenScenarioIds.values) {
      expect(ids, contains(id));
    }
  });

  test('same Visa owner reference survives Now and Ongoing projections', () {
    final now = PresentationFixtureUniverse.visaNow.reference;
    final ongoing = PresentationFixtureUniverse.visaOngoing.reference;

    expect(now.kind, ongoing.kind);
    expect(now.id, ongoing.id);
    expect(now.id, PresentationFixtureUniverse.demoVisaId);
  });

  test('runtime-compatible and target Presentation fixtures stay explicit', () {
    expect(
      PresentationScenarioCatalog.byId('discover-compact-field').dataKind,
      PresentationScenarioDataKind.runtimeCompatible,
    );
    expect(
      PresentationScenarioCatalog.byId('discover-wide-spatial').dataKind,
      PresentationScenarioDataKind.targetPresentation,
    );
  });

  test('demo media is fixture-only and needs no public network', () {
    const reference = 'fixture://discover/data-science-nairobi';
    expect(FixtureMediaResolver.supports(reference), isTrue);
    expect(
      FixtureMediaResolver.supports('https://example.invalid/image.jpg'),
      isFalse,
    );
    expect(
      PresentationFixtureUniverse.discoverRuntimePayload.toString(),
      isNot(contains('https://')),
    );
  });
}
