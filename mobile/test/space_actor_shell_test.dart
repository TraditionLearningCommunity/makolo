import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/app/app_shell.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/space/space_repository.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

import 'fakes.dart';

class _ActorStore implements ActorContextStore {
  ActorContext value = const PersonalActorContext();

  @override
  Future<ActorContext> readActorContext(String profileId) async => value;

  @override
  Future<void> writeActorContext(String profileId, ActorContext context) async {
    value = context;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    value = const PersonalActorContext();
  }
}

class _Harness {
  _Harness({
    required this.runtime,
    required this.actorContext,
    required this.database,
    required this.router,
  });

  final AppRuntime runtime;
  final ActorContextController actorContext;
  final MakoloDatabase database;
  final GoRouter router;

  Future<void> close() async {
    router.dispose();
    actorContext.dispose();
    await database.close();
  }
}

Future<_Harness> _harness({bool startInSpace = false}) async {
  final database = MakoloDatabase.memory();
  final store = ProfileStore(database, 'profile-a');
  await store.putProjection(
    kind: 'personal.me',
    schemaVersion: 1,
    payload: {
      'identity': {'display_name': 'Amina'},
    },
  );
  await store.putProjection(
    kind: SpaceSyncKeys.inventoryProjectionKind,
    schemaVersion: 1,
    payload: {
      'items': [
        {
          'id': 'space-x',
          'slug': 'space-x',
          'name': 'Space X',
          'archetype': 'generic',
          'lifecycle': 'active',
          'limited_to_activities': false,
        },
      ],
    },
  );
  await store.putProjection(
    kind: SpaceProjectionKind.workspace.wireValue,
    resourceKey: SpaceSyncKeys.resourceKey('space-x'),
    schemaVersion: 1,
    payload: {
      'space': {'id': 'space-x', 'slug': 'space-x', 'name': 'Space X'},
      'responsibilities': [
        {
          'key': 'all',
          'label': 'Toutes mes responsabilités',
          'scope': 'space',
          'combined': true,
        },
        {
          'key': 'mandate:a',
          'label': 'Exploitation',
          'scope': 'space',
          'combined': false,
        },
      ],
    },
  );

  final actorContext = await ActorContextController.restore(
    profileId: 'profile-a',
    store: _ActorStore(),
  );
  if (startInSpace) {
    await actorContext.selectSpace(
      SpaceActorIdentity(id: 'space-x', slug: 'space-x'),
    );
  }
  final recovery = SessionRecoveryController();
  final runtime = AppRuntime(
    tokens: MemoryTokenStore(),
    session: null,
    recovery: recovery,
    database: database,
    store: store,
    personal: PersonalRepository(store),
    actorContext: actorContext,
    space: WorkspaceContextRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      actorContext: actorContext,
    ),
  );

  final router = GoRouter(
    initialLocation: startInSpace ? '/space/now' : '/now',
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => AppShell(
          navigationShell: navigationShell,
          recovery: recovery,
          runtime: runtime,
        ),
        branches: [
          _branch('/now', 'Personal Now'),
          _branch('/discover', 'Personal Discover'),
          _branch('/ongoing', 'Personal Ongoing', counter: true),
          _branch('/me', 'Personal Me'),
          _branch('/space/now', 'Space Now'),
          _branch('/space/discover', 'Space Discover'),
          _branch('/space/work', 'Space Work', counter: true),
          _branch('/space/us', 'Space Us'),
        ],
      ),
      GoRoute(
        path: '/mark',
        builder: (context, state) => const Scaffold(body: Text('Mark')),
      ),
    ],
  );

  return _Harness(
    runtime: runtime,
    actorContext: actorContext,
    database: database,
    router: router,
  );
}

StatefulShellBranch _branch(
  String path,
  String label, {
  bool counter = false,
}) => StatefulShellBranch(
  routes: [
    GoRoute(
      path: path,
      builder: (context, state) => counter
          ? _CounterTab(label: label)
          : ListView(children: [Text(label)]),
    ),
  ],
);

Future<void> _pump(
  WidgetTester tester,
  _Harness harness, {
  double textScale = 1,
}) async {
  await tester.pumpWidget(
    MaterialApp.router(
      theme: buildMakoloTheme(),
      routerConfig: harness.router,
      builder: (context, child) => textScale == 1
          ? child!
          : MediaQuery(
              data: MediaQuery.of(context)
                  .copyWith(textScaler: TextScaler.linear(textScale)),
              child: child!,
            ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _disposeUi(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
}

Future<void> _chooseActor(WidgetTester tester, String label) async {
  await tester.tap(find.byTooltip('Avatar'));
  await tester.pumpAndSettle();
  expect(find.text('Amina'), findsOneWidget);
  await tester.tap(find.text('Agir comme'));
  await tester.pumpAndSettle();
  await tester.tap(find.text(label));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('Agir comme switches the same shell from personal to Space', (
    tester,
  ) async {
    final harness = await _harness();
    addTearDown(harness.close);
    await _pump(tester, harness);

    expect(find.text('En cours'), findsOneWidget);
    expect(find.text('Moi'), findsOneWidget);
    expect(find.text('Métier'), findsNothing);

    await _chooseActor(tester, 'Space X');

    expect(harness.actorContext.value, isA<SpaceActorContext>());
    expect(find.text('Space Now'), findsOneWidget);
    expect(find.text('Métier'), findsOneWidget);
    expect(find.text('Nous'), findsOneWidget);
    expect(find.text('En cours'), findsNothing);
    expect(find.text('Space X'), findsOneWidget);
    expect(find.text('Toutes mes responsabilités'), findsOneWidget);
    await _disposeUi(tester);
  });

  testWidgets('actor switch preserves the semantic door and branch state', (
    tester,
  ) async {
    final harness = await _harness();
    addTearDown(harness.close);
    await _pump(tester, harness);

    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Incrémenter'));
    await tester.pump();
    expect(find.text('Personal Ongoing · 1'), findsOneWidget);

    await _chooseActor(tester, 'Space X');
    expect(find.text('Space Work · 0'), findsOneWidget);
    await tester.tap(find.text('Incrémenter'));
    await tester.pump();
    expect(find.text('Space Work · 1'), findsOneWidget);

    await _chooseActor(tester, 'Moi');
    expect(find.text('Personal Ongoing · 1'), findsOneWidget);
    expect(find.text('En cours'), findsOneWidget);
    expect(find.text('Moi'), findsOneWidget);
    await _disposeUi(tester);
  });

  testWidgets('perspective uses server label without changing authority', (
    tester,
  ) async {
    final harness = await _harness(startInSpace: true);
    addTearDown(harness.close);
    await _pump(tester, harness);

    await tester.tap(find.text('Toutes mes responsabilités'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Exploitation'));
    await tester.pumpAndSettle();

    final actor = harness.actorContext.value as SpaceActorContext;
    expect(actor.perspective.id, 'mandate:a');
    expect(find.text('Exploitation'), findsOneWidget);
    expect(find.text('mandate:a'), findsNothing);
    await _disposeUi(tester);
  });

  testWidgets('revoked Space context returns to the personal counterpart', (
    tester,
  ) async {
    final harness = await _harness(startInSpace: true);
    addTearDown(harness.close);
    await _pump(tester, harness);

    await tester.tap(find.text('Métier'));
    await tester.pumpAndSettle();
    expect(find.text('Space Work · 0'), findsOneWidget);

    await harness.actorContext.selectPersonal();
    await tester.pumpAndSettle();

    expect(find.text('Personal Ongoing · 0'), findsOneWidget);
    expect(find.text('En cours'), findsOneWidget);
    await _disposeUi(tester);
  });

  testWidgets('Space shell stays usable at large text on a small phone', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final harness = await _harness(startInSpace: true);
    addTearDown(harness.close);

    await _pump(tester, harness, textScale: 2);

    expect(find.text('Métier'), findsOneWidget);
    expect(find.text('Nous'), findsOneWidget);
    expect(find.text('Space X'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await _disposeUi(tester);
  });

  testWidgets('wide Space shell exposes the same semantics in the rail', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final harness = await _harness(startInSpace: true);
    addTearDown(harness.close);

    await _pump(tester, harness);

    expect(find.byKey(const Key('makolo-navigation-rail')), findsOneWidget);
    expect(find.text('Métier'), findsOneWidget);
    expect(find.text('Nous'), findsOneWidget);
    await _disposeUi(tester);
  });
}

class _CounterTab extends StatefulWidget {
  const _CounterTab({required this.label});

  final String label;

  @override
  State<_CounterTab> createState() => _CounterTabState();
}

class _CounterTabState extends State<_CounterTab> {
  int count = 0;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        Text('${widget.label} · $count'),
        TextButton(
          onPressed: () => setState(() => count += 1),
          child: const Text('Incrémenter'),
        ),
      ],
    );
  }
}
