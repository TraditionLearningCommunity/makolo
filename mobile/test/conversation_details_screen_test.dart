import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/conversation_details_screen.dart';
import 'package:makolo_mobile/features/continuity/conversation_repository.dart';

void main() {
  late MakoloDatabase database;
  late ProfileStore store;
  late ConversationRepository repository;

  setUp(() {
    database = MakoloDatabase.memory();
    store = ProfileStore(database, 'profile-a');
    repository = ConversationRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
    );
  });

  tearDown(() async {
    await database.close();
  });

  Future<void> putDetail({
    String scope = 'restricted',
    List<Map<String, dynamic>> people = const [],
    List<Map<String, dynamic>> media = const [],
    List<Map<String, dynamic>> resources = const [],
  }) => store.putProjection(
    kind: ConversationRepository.detailProjectionKind,
    resourceKey: 'conv-1',
    schemaVersion: 1,
    payload: {
      'id': 'conv-1',
      'title': 'Préparation pratique — Salon des mines',
      'purpose': 'Préparer la participation et suivre les décisions.',
      'context': {'kind': 'group', 'label': 'Salon des mines'},
      'subject': {
        'kind': 'group',
        'label': 'Salon des mines',
        'image_url': null,
      },
      'members': {'scope': scope, 'people': people},
      'media': media,
      'resources': resources,
      'personal_state': {
        'muted': true,
        'pinned': false,
        'revisit': false,
        'hidden': false,
        'archived': false,
      },
      'points': [],
      'essential': [],
      'elsewhere': [],
    },
  );

  testWidgets('detail hero and restricted members are local-first', (
    tester,
  ) async {
    await putDetail();
    await tester.pumpWidget(
      MaterialApp(
        home: ConversationDetailsScreen(
          repository: repository,
          conversationId: 'conv-1',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Salon des mines'), findsOneWidget);
    expect(
      find.text('Préparer la participation et suivre les décisions.'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('conversation-details-tabs')), findsOneWidget);
    expect(
      find.textContaining('Leur liste n’est pas affichée ici.'),
      findsOneWidget,
    );
    expect(find.text('Partager'), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('authorized media index and personal settings are separate', (
    tester,
  ) async {
    await putDetail(
      scope: 'direct',
      people: const [
        {'label': 'Vous', 'is_me': true},
        {'label': 'Marie', 'is_me': false},
      ],
      media: const [
        {
          'id': 'media-1',
          'kind': 'image',
          'name': 'salon.jpg',
          'mime_type': 'image/jpeg',
        },
      ],
      resources: const [
        {
          'id': 'resource-1',
          'kind': 'text',
          'title': 'Préparer mon badge',
          'description': 'Consignes pratiques',
        },
      ],
    );
    await tester.pumpWidget(
      MaterialApp(
        home: ConversationDetailsScreen(
          repository: repository,
          conversationId: 'conv-1',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Marie'), findsOneWidget);

    await tester.tap(find.text('Médias'));
    await tester.pumpAndSettle();
    expect(find.text('salon.jpg'), findsOneWidget);

    await tester.ensureVisible(find.text('Ressources'));
    await tester.tap(find.text('Ressources'));
    await tester.pumpAndSettle();
    expect(find.text('Préparer mon badge'), findsOneWidget);

    await tester.ensureVisible(find.text('Paramètres'));
    await tester.tap(find.text('Paramètres'));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('conversation-detail-setting-mute')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('conversation-detail-setting-archive')),
      findsOneWidget,
    );
    final mute = tester.widget<SwitchListTile>(
      find.byKey(const Key('conversation-detail-setting-mute')),
    );
    expect(mute.value, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
