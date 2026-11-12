import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/journey/journey_composition.dart';
import 'package:makolo_mobile/features/journey/journey_selector.dart';
import 'package:makolo_mobile/features/journey/journey_time_presentation.dart';

JourneyDetailPresentation _journey({
  String status = 'in_progress',
  List<JourneyReadinessItem> interventions = const [],
  List<JourneyReadinessItem> waiting = const [],
  List<JourneyReadinessItem> blocked = const [],
  List<JourneyReadinessItem> ready = const [],
  List<JourneyStepSummary> steps = const [],
  List<JourneyFormSummary> forms = const [],
  List<JourneyReference> requirements = const [],
  List<JourneyPaymentSummary> payments = const [],
  JourneyOrderSummary? order,
  JourneyReference? access,
  int pending = 0,
  int rejected = 0,
  String? nextKey,
  String? nextLink,
  bool canInvite = false,
  String? resourcesLink,
}) => JourneyDetailPresentation(
  available: true,
  title: 'Préparer mon inscription',
  kindLabel: 'Démarche',
  journeyState: status,
  readinessState: 'unknown',
  stateCode: status,
  actorInterventions: interventions,
  waiting: waiting,
  blockers: blocked,
  ready: ready,
  steps: steps,
  forms: forms,
  requirements: requirements,
  payments: payments,
  order: order,
  access: access,
  pendingRequests: pending,
  rejectedRequests: rejected,
  nextActionKey: nextKey,
  nextActionLink: nextLink,
  canRespondInvitation: canInvite,
  resourcesLink: resourcesLink,
  capabilities: const {},
  freshness: null,
  sourceInvalidated: false,
);

const _action = JourneyReadinessItem(
  key: 'form.a',
  summary: 'Compléter mon formulaire',
  nextLabel: 'Remplir',
  nextLink: '/api/v1/questionnaires/requests/a/',
);

void main() {
  test('universal empty composition shows no invented territory', () {
    final composed = JourneyComposition.from(_journey());
    expect(composed.situation, JourneySituation.calm);
    expect(composed.hasPreparation, isFalse);
    expect(composed.hasDocuments, isFalse);
    expect(composed.hasEngagements, isFalse);
    expect(composed.hasBranches, isFalse);
  });

  test('active and awaiting owner facts are different situations', () {
    expect(
      JourneyComposition.from(_journey(interventions: [_action])).situation,
      JourneySituation.action,
    );
    expect(
      JourneyComposition.from(
        _journey(
          waiting: const [
            JourneyReadinessItem(key: 'review', summary: 'Réponse attendue'),
          ],
        ),
      ).situation,
      JourneySituation.waiting,
    );
    expect(
      JourneyComposition.from(_journey(pending: 1)).situation,
      JourneySituation.waiting,
    );
  });

  test(
    'an owner blocker dominates action; rejected request is not waiting',
    () {
      final blocked = JourneyComposition.from(
        _journey(
          interventions: const [_action],
          blocked: const [
            JourneyReadinessItem(
              key: 'required-id',
              summary: 'Pièce manquante',
            ),
          ],
        ),
      );
      expect(blocked.situation, JourneySituation.blocked);
      expect(
        JourneyComposition.from(_journey(rejected: 1)).situation,
        JourneySituation.blocked,
      );
    },
  );

  test('multiple owner actions remain multiple, not one fabricated CTA', () {
    final composed = JourneyComposition.from(
      _journey(
        interventions: const [
          _action,
          JourneyReadinessItem(
            key: 'requirement.b',
            summary: 'Fournir une pièce',
            nextLink: '/api/v1/me/journeys/id/requirements/b/',
          ),
        ],
      ),
    );
    expect(composed.situation, JourneySituation.choices);
    expect(composed.interventions.length, 2);
  });

  test('a technical, repeated objective is not an extra user task', () {
    final p = JourneyComposition.from(
      _journey(
        interventions: const [
          JourneyReadinessItem(
            key: 'technical',
            summary: 'Préparer mon inscription',
          ),
        ],
      ),
    );
    expect(p.interventions, isEmpty);
    expect(p.situation, JourneySituation.calm);
  });

  test('rich owner facts show only contextual territories they authorize', () {
    final rich = JourneyComposition.from(
      _journey(
        forms: const [
          JourneyFormSummary(
            id: 'f',
            required: true,
            state: 'requested',
            canComplete: true,
            detailLink: '/api/v1/questionnaires/requests/f/',
          ),
        ],
        requirements: const [
          JourneyReference(id: 'r', label: 'Pièce', isRequired: true),
        ],
        payments: const [
          JourneyPaymentSummary(
            amount: '25.00',
            currency: 'USD',
            state: 'pending',
          ),
        ],
        order: const JourneyOrderSummary(id: 'o', state: 'pending'),
        access: const JourneyReference(id: 'a', label: 'Accès'),
        resourcesLink: '/api/v1/preparation/journeys/id/resources/',
      ),
      resourcesKnown: true,
      resourcesCount: 3,
    );
    expect(rich.hasPreparation, isTrue);
    expect(rich.hasEngagements, isTrue);
    expect(rich.hasDocuments, isTrue);
    expect(
      JourneyComposition.from(
        _journey(resourcesLink: '/api/v1/preparation/journeys/id/resources/'),
        resourcesKnown: true,
        resourcesCount: 0,
      ).hasDocuments,
      isFalse,
    );
  });

  test('real dependency graph reveals branches without a percentage', () {
    const root = JourneyStepSummary(
      id: 'root',
      title: 'Choisir',
      status: 'completed',
      kind: 'choice',
      dependsOn: [],
    );
    const left = JourneyStepSummary(
      id: 'left',
      title: 'Option A',
      status: 'pending',
      kind: 'activity',
      dependsOn: ['root'],
    );
    const right = JourneyStepSummary(
      id: 'right',
      title: 'Option B',
      status: 'pending',
      kind: 'activity',
      dependsOn: ['root'],
    );
    expect(
      JourneyComposition.from(_journey(steps: [root, left, right])).hasBranches,
      isTrue,
    );
  });

  test('terminal owner Journey overrides all stale current actions', () {
    final composed = JourneyComposition.from(
      _journey(
        status: 'fulfilled',
        blocked: const [
          JourneyReadinessItem(key: 'old', summary: 'Ancienne difficulté'),
        ],
        interventions: const [_action],
      ),
    );
    expect(composed.situation, JourneySituation.completed);
  });

  testWidgets('Jour J is tappable only on date and with owner admission', (
    tester,
  ) async {
    final now = DateTime.now();
    String day(int offset) {
      final day = DateTime(now.year, now.month, now.day + offset);
      return '${day.year.toString().padLeft(4, '0')}-'
          '${day.month.toString().padLeft(2, '0')}-'
          '${day.day.toString().padLeft(2, '0')}';
    }

    var opened = 0;
    Future<void> show(String date, {bool owner = false}) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: JourneyDayBadge(
                key: ValueKey(date + owner.toString()),
                occurrenceDate: date,
                onOpenDayOf: owner ? () => opened++ : null,
              ),
            ),
          ),
        ),
      );
      await tester.pump();
    }

    await show(day(-2), owner: true);
    await tester.tap(find.byKey(const Key('journey-relative-day')));
    expect(opened, 0);
    await show(day(0));
    await tester.tap(find.byKey(const Key('journey-relative-day')));
    expect(opened, 0);
    await show(day(0), owner: true);
    await tester.tap(find.byKey(const Key('journey-relative-day')));
    expect(opened, 1);
  });
}
