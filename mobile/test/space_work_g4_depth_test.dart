import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/space/space_work_g4_depth.dart';
import 'package:makolo_mobile/features/space/space_work_surface.dart';

void main() {
  testWidgets('MT6 Creative shows real dates but no fabricated action', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            children: [
              SpaceWorkG4Depth(
                slug: 'atelier',
                sourceKind: 'activity',
                sourceId: 'work-1',
                archetype: 'creative',
                isActivity: true,
                detail: const {'description': 'Œuvre en préparation'},
                related: const {
                  'items': [],
                  'offset': 0,
                  'limit': 12,
                  'has_more': false,
                },
                mediaBindings: const [],
                onPageChange: (_) {},
              ),
            ],
          ),
        ),
      ),
    );
    expect(find.text('Œuvre en préparation'), findsOneWidget);
    expect(find.text('Présentations et réalisations'), findsOneWidget);
    expect(find.textContaining('Aucune présentation datée'), findsOneWidget);
    expect(find.text('Publier'), findsNothing);
    expect(find.text('Acheter'), findsNothing);
  });

  testWidgets('MT6 Media paginates real owner dates and disables old links', (
    tester,
  ) async {
    int? page;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            children: [
              SpaceWorkG4Depth(
                slug: 'studio',
                sourceKind: 'activity',
                sourceId: 'work-2',
                archetype: 'media',
                isActivity: true,
                detail: const {},
                related: const {
                  'items': [
                    {
                      'source': {'kind': 'occurrence', 'id': 'old-edition'},
                      'title': 'Édition à régulariser',
                      'state': 'scheduled',
                      'timing': {'start_date': '2026-01-05'},
                      'openable': false,
                    },
                  ],
                  'offset': 12,
                  'limit': 12,
                  'has_more': true,
                },
                mediaBindings: const [],
                onPageChange: (offset) => page = offset,
              ),
            ],
          ),
        ),
      ),
    );
    expect(find.text('Éditions et réalisations'), findsOneWidget);
    expect(find.text('Édition à régulariser'), findsOneWidget);
    expect(find.textContaining('Date non ouvrable'), findsOneWidget);
    await tester.tap(find.text('Précédentes'));
    expect(page, 0);
    await tester.tap(find.text('Voir les suivantes'));
    expect(page, 24);
  });

  testWidgets('MT6 rejects a published image bound to a different owner', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            children: [
              SpaceWorkG4Depth(
                slug: 'atelier',
                sourceKind: 'activity',
                sourceId: 'current-work',
                archetype: 'creative',
                isActivity: true,
                detail: const {},
                related: const {
                  'items': [],
                  'offset': 0,
                  'limit': 12,
                  'has_more': false,
                },
                mediaBindings: const [
                  {
                    'authorized': true,
                    'purpose': 'recognize',
                    'kind': 'image',
                    'mime_type': 'image/png',
                    'url': '/presentation/media/uses/other/file/',
                    'owner': {'kind': 'occurrence', 'id': 'other-edition'},
                  },
                ],
                mediaBaseUri: Uri.parse('https://makolo.example/'),
                onPageChange: (_) {},
              ),
            ],
          ),
        ),
      ),
    );
    expect(find.byType(Image), findsNothing);
  });

  testWidgets(
    'MT6 create requires owner capability and global responsibility',
    (tester) async {
      Future<void> show(
        String archetype, {
        required bool permission,
        String responsibility = 'all',
      }) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: SpaceWorkSurface(
                payload: {
                  'primary_business_label': archetype == 'creative'
                      ? 'Créations'
                      : 'Productions',
                  'archetype': archetype,
                  'responsibility': responsibility,
                  'space': {'slug': 'studio'},
                  'capabilities': {'create_activity': permission},
                  'presentation': {'empty_message': 'Aucun travail.'},
                  'sections': <String, dynamic>{},
                },
              ),
            ),
          ),
        );
      }

      await show('creative', permission: true);
      expect(find.text('Nouvelle création'), findsOneWidget);
      await show('media', permission: true);
      expect(find.text('Nouvelle production'), findsOneWidget);
      await show('creative', permission: false);
      expect(find.text('Nouvelle création'), findsNothing);
      await show(
        'media',
        permission: true,
        responsibility: 'mandate:restricted',
      );
      expect(find.text('Nouvelle production'), findsNothing);
    },
  );
}
