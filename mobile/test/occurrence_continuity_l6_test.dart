import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/occurrence/occurrence_continuity.dart';
import 'package:makolo_mobile/features/occurrence/occurrence_experience_content.dart';
import 'package:makolo_mobile/sync/freshness.dart';

const _personal = <String, dynamic>{
  'identity': {'kind': 'occurrence', 'id': 'occ-one'},
  'context': {
    'viewer_profile_id': 'profile-a',
    'actor_space_id': null,
    'activity': {'title': 'Formation'},
    'occurrence': {'id': 'occ-one', 'label': 'Séance'},
  },
  'surface': 'day_of',
  'phase': 'arrival',
  'live': {'available': false},
  'sections': {},
  'capabilities': {},
  'actions': [],
};

void main() {
  test(
    'L6: locally stored Occurrence requires exact viewer and actor scope',
    () {
      expect(
        OccurrenceContinuity.matches(
          payload: _personal,
          occurrenceId: 'occ-one',
          profileId: 'profile-a',
          surface: 'day_of',
        ),
        isTrue,
      );
      for (final invalid in <Map<String, String?>>[
        {'occurrence': 'occ-two', 'viewer': 'profile-a'},
        {'occurrence': 'occ-one', 'viewer': 'profile-b'},
      ]) {
        expect(
          OccurrenceContinuity.matches(
            payload: _personal,
            occurrenceId: invalid['occurrence']!,
            profileId: invalid['viewer']!,
            surface: 'day_of',
          ),
          isFalse,
        );
      }
      expect(
        OccurrenceContinuity.matches(
          payload: _personal,
          occurrenceId: 'occ-one',
          profileId: 'profile-a',
          actorSpaceId: 'space-one',
          surface: 'day_of',
        ),
        isFalse,
      );
      expect(
        OccurrenceContinuity.matches(
          payload: _personal,
          occurrenceId: 'occ-one',
          profileId: 'profile-a',
          surface: 'live',
        ),
        isFalse,
      );
      final institutional = <String, dynamic>{
        ..._personal,
        'context': {
          ...(_personal['context'] as Map<String, dynamic>),
          'actor_space_id': 'space-one',
        },
      };
      expect(
        OccurrenceContinuity.matches(
          payload: institutional,
          occurrenceId: 'occ-one',
          profileId: 'profile-a',
          actorSpaceId: 'space-one',
          surface: 'day_of',
        ),
        isTrue,
      );
      expect(
        OccurrenceContinuity.matches(
          payload: institutional,
          occurrenceId: 'occ-one',
          profileId: 'profile-a',
          actorSpaceId: 'space-two',
          surface: 'day_of',
        ),
        isFalse,
      );
    },
  );

  test(
    'L6: returning to a Space actor requires a new successful owner read',
    () {
      final changed = DateTime.utc(2026, 11, 9, 15);
      expect(
        OccurrenceContinuity.verifiedAfterActorSwitch(
          lastSuccessAt: DateTime.utc(2026, 11, 9, 14, 59),
          actorSwitchedAt: changed,
        ),
        isFalse,
      );
      expect(
        OccurrenceContinuity.verifiedAfterActorSwitch(
          lastSuccessAt: null,
          actorSwitchedAt: changed,
        ),
        isFalse,
      );
      expect(
        OccurrenceContinuity.verifiedAfterActorSwitch(
          lastSuccessAt: DateTime.utc(2026, 11, 9, 15, 1),
          actorSwitchedAt: changed,
        ),
        isTrue,
      );
    },
  );

  test('L6: Live cannot stay current after its known end or cancellation', () {
    final now = DateTime.utc(2026, 11, 9, 15);
    final live = <String, dynamic>{
      ..._personal,
      'surface': 'live',
      'phase': 'live',
      'live': {'available': true, 'ends_at': '2026-11-09T14:59:59Z'},
    };
    expect(OccurrenceContinuity.liveWindowEnded(live, now: now), isTrue);
    expect(
      OccurrenceContinuity.liveWindowEnded({
        ...live,
        'live': {'available': true, 'ends_at': '2026-11-09T16:00:00Z'},
      }, now: now),
      isFalse,
    );
    expect(
      OccurrenceContinuity.liveWindowEnded({
        ...live,
        'phase': 'cancelled',
      }, now: now),
      isTrue,
    );
    expect(
      OccurrenceContinuity.liveWindowEnded({
        ...live,
        'live': {'available': false},
      }, now: now),
      isTrue,
    );
  });

  test('L6: last-known offline or revoked content never unlocks actions', () {
    bool allowed({
      required ReachabilityState reachability,
      required FreshnessState freshness,
      bool invalidated = false,
      bool offline = false,
      bool ended = false,
    }) => OccurrenceContinuity.canOfferActions(
      sourceInvalidated: invalidated,
      reachability: reachability,
      freshness: freshness,
      systemOffline: offline,
      liveEnded: ended,
    );

    expect(
      allowed(
        reachability: ReachabilityState.reachable,
        freshness: FreshnessState.fresh,
      ),
      isTrue,
    );
    expect(
      allowed(
        reachability: ReachabilityState.reachable,
        freshness: FreshnessState.usableButOld,
      ),
      isFalse,
    );
    expect(
      allowed(
        reachability: ReachabilityState.unreachable,
        freshness: FreshnessState.fresh,
      ),
      isFalse,
    );
    expect(
      allowed(
        reachability: ReachabilityState.reachable,
        freshness: FreshnessState.fresh,
        invalidated: true,
      ),
      isFalse,
    );
    expect(
      allowed(
        reachability: ReachabilityState.reachable,
        freshness: FreshnessState.fresh,
        offline: true,
      ),
      isFalse,
    );
    expect(
      allowed(
        reachability: ReachabilityState.reachable,
        freshness: FreshnessState.fresh,
        ended: true,
      ),
      isFalse,
    );
    expect(OccurrenceContinuity.isDenied('permission_denied'), isTrue);
    expect(OccurrenceContinuity.isDenied('not_found'), isTrue);
    expect(OccurrenceContinuity.isDenied('timeout'), isFalse);
  });

  testWidgets(
    'L6: both responsibilities stay visible compact and wide with scaling',
    (tester) async {
      final payload = <String, dynamic>{..._personal}
        ..['actions'] = [
          {
            'territory': 'participant',
            'kind': 'instruction',
            'label': 'Mon accès important',
          },
          {
            'territory': 'organizer',
            'kind': 'owner_handoff',
            'type': 'scanner',
            'label': 'Contrôler l’entrée',
          },
        ]
        ..['capabilities'] = {'scanner': {}};
      for (final width in [360.0, 940.0]) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Center(
                child: SizedBox(
                  width: width,
                  height: 690,
                  child: MediaQuery(
                    data: const MediaQueryData(
                      textScaler: TextScaler.linear(1.6),
                    ),
                    child: OccurrenceExperienceContent(
                      payload: payload,
                      live: false,
                      remoteActionsAvailable: false,
                      readOnlyReason: 'Dernière lecture connue.',
                      lastKnownAt: DateTime.utc(2026, 11, 9, 12),
                      onOpenScanner: () {},
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
        expect(find.text('Mon accès important'), findsOneWidget);
        expect(find.text('Contrôler l’entrée'), findsOneWidget);
        expect(find.text('Dernière lecture connue.'), findsOneWidget);
        await tester.ensureVisible(find.text('Ouvrir Scanner'));
        final button = tester.widget<FilledButton>(
          find.widgetWithText(FilledButton, 'Ouvrir Scanner'),
        );
        expect(button.onPressed, isNull);
      }
    },
  );
}
