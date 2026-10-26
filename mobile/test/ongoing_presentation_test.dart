import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/ongoing/ongoing_presentation.dart';

StoredProjection _projection(List<Object> items) => StoredProjection(
  kind: 'personal.ongoing',
  schemaVersion: 1,
  payload: {'items': items},
  receivedAt: DateTime.utc(2026, 10, 3, 16),
);

void main() {
  test('adapts the real ongoing shape and preserves owner identity', () {
    final items = OngoingContinuityPresentation.fromProjection(
      _projection([
        {
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': '42'},
          'state': 'waiting',
          'title': 'Visa Canada',
          'ready': [
            {'title': 'Frais réglés'},
          ],
          'actor_interventions': [],
          'continuation': {
            'state': 'waiting',
            'summary': 'Le consulat examine votre dossier.',
          },
          'blocker': null,
          'next': {'title': 'Biométrie'},
          'timing': {'deadline_date': '2026-11-15'},
          'place': null,
          'capabilities': ['open_detail'],
          'links': {'detail': '/api/v1/me/journeys/42/'},
        },
      ]),
    );

    expect(items, hasLength(1));
    expect(items.single.ownerKind, 'journey');
    expect(items.single.ownerId, '42');
    expect(items.single.settled, contains('Frais réglés'));
    expect(
      items.single.elsewhere,
      contains('Le consulat examine votre dossier.'),
    );
    expect(items.single.next, contains('Biométrie'));
    expect(items.single.blocker, isNull);
  });

  test('server synthesis wins over local fallback interpretation', () {
    final items = OngoingContinuityPresentation.fromProjection(
      _projection([
        {
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': 'server-summary'},
          'state': 'waiting',
          'title': 'Visa Canada',
          'summary': 'Votre dossier est suivi par Makolo.',
          'ready': [
            {'title': 'Frais réglés'},
          ],
          'actor_interventions': [],
          'continuation': {'state': 'waiting', 'summary': 'Réponse attendue.'},
          'blocker': null,
          'next': null,
          'timing': {},
          'place': null,
          'capabilities': [],
          'links': {},
        },
      ]),
    );

    expect(items.single.synthesis, 'Votre dossier est suivi par Makolo.');
  });

  test('waiting stays distinct from blocker', () {
    final items = OngoingContinuityPresentation.fromProjection(
      _projection([
        {
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': '1'},
          'state': 'waiting',
          'title': 'Demande',
          'ready': [],
          'actor_interventions': [],
          'continuation': {'state': 'waiting', 'summary': 'Réponse attendue.'},
          'blocker': null,
          'next': null,
          'timing': {},
          'place': null,
          'capabilities': [],
          'links': {},
        },
        {
          'kind': 'dossier',
          'source': {'kind': 'dossier', 'id': '2'},
          'state': 'blocked',
          'title': 'Dossier',
          'ready': [],
          'actor_interventions': [],
          'continuation': null,
          'blocker': {'state': 'blocked', 'title': 'Passeport manquant'},
          'next': null,
          'timing': {},
          'place': null,
          'capabilities': [],
          'links': {},
        },
      ]),
    );

    expect(items[0].waiting, isNotNull);
    expect(items[0].blocker, isNull);
    expect(items[1].blocker, 'Passeport manquant');
    expect(items[1].waiting, isNull);
  });

  test('parallel movements remain independently readable', () {
    final items = OngoingContinuityPresentation.fromProjection(
      _projection([
        {
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': '3'},
          'state': 'ready',
          'title': 'Voyage Nairobi',
          'ready': [
            {'title': 'Vol confirmé'},
          ],
          'actor_interventions': [
            {'title': 'Document avant le 20 novembre'},
          ],
          'continuation': {
            'state': 'waiting',
            'summary': 'La compagnie prépare le vol.',
          },
          'blocker': null,
          'next': {'title': 'Départ'},
          'timing': {},
          'place': {},
          'capabilities': [],
          'links': {},
        },
        {
          'kind': 'project',
          'source': {'kind': 'project', 'id': '9'},
          'state': 'active',
          'title': 'Formation Data Science',
          'ready': [],
          'actor_interventions': [],
          'continuation': null,
          'blocker': null,
          'next': {'title': 'Document avant le 20 novembre'},
          'timing': {},
          'place': {},
          'capabilities': [],
          'links': {},
        },
      ]),
    );

    expect(items, hasLength(2));
    expect(items.map((item) => item.ownerId), containsAll(['3', '9']));
    expect(items.first.hasParallelMovement, isTrue);
  });

  test('N1 parses the same human cue, date and published recognition media', () {
    final items = OngoingContinuityPresentation.fromProjection(
      _projection([
        {
          'id': 'continuity:confirmed-travel',
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': 'travel-1'},
          'state': 'available',
          'title': 'Lubumbashi → Kolwezi',
          'summary': 'Place confirmée.',
          'n1': {
            'cue': 'Accès disponible',
            'tone': 'ready',
            'when_label': '12/11/2026 · 14:00',
            'supporting': 'Départ prévu',
            'place_label': 'Lubumbashi',
          },
          'ready': [],
          'actor_interventions': [],
          'continuation': null,
          'blocker': null,
          'next': null,
          'timing': {},
          'place': null,
          'capabilities': [],
          'links': {},
          'media_bindings': [
            {
              'purpose': 'RECOGNIZE',
              'resource': {
                'url': '/presentation/media/uses/abc/file/',
                'mime_type': 'image/jpeg',
                'alt_text': 'Véhicule du voyage',
              },
            },
            {
              'purpose': 'PREPARE',
              'resource': {
                'url': '/private/document.pdf',
                'mime_type': 'application/pdf',
              },
            },
          ],
        },
      ]),
    );
    final item = items.single;
    expect(item.id, 'continuity:confirmed-travel');
    expect(item.cue, 'Accès disponible');
    expect(item.cueTone, 'ready');
    expect(item.whenLabel, '12/11/2026 · 14:00');
    expect(item.supporting, 'Départ prévu');
    expect(item.placeLabel, 'Lubumbashi');
    expect(item.mediaUrl, '/presentation/media/uses/abc/file/');
    expect(item.mediaAlt, 'Véhicule du voyage');
  });

  test('old offline snapshots remain usable without N1 extensions', () {
    final items = OngoingContinuityPresentation.fromProjection(
      _projection([
        {
          'kind': 'waitlist',
          'source': {'kind': 'waitlist', 'id': 'concert-wait'},
          'state': 'waiting',
          'title': 'Concert du samedi',
          'summary': 'Vous attendez une place.',
          'ready': [],
          'actor_interventions': [],
          'continuation': {'state': 'waiting'},
          'blocker': null,
          'next': null,
          'timing': {},
          'place': {},
          'capabilities': [],
          'links': {},
        },
      ]),
    );
    expect(items.single.title, 'Concert du samedi');
    expect(items.single.cue, 'En attente');
    expect(items.single.mediaUrl, isNull);
  });

  test('true empty has no synthetic suggestion', () {
    expect(
      OngoingContinuityPresentation.fromProjection(_projection(const [])),
      isEmpty,
    );
  });
}
