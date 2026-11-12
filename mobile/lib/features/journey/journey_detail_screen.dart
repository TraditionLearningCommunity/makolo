import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../design/action_controls.dart';

import '../../network/makolo_api_client.dart';
import '../../data/local/profile_store.dart';

import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../continuity/conversation_context_screen.dart';
import '../continuity/conversation_repository.dart';
import '../preparation/preparation_repository.dart';
import 'journey_composition.dart';
import 'journey_repository.dart';
import 'journey_selector.dart';
import 'journey_time_presentation.dart';

Color _journeyAccent(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark
    ? Theme.of(context).colorScheme.secondary
    : MakoloColors.indigo;

class JourneyDetailScreen extends StatefulWidget {
  const JourneyDetailScreen({
    super.key,
    required this.journeyId,
    required this.repository,
    this.api,
    this.resourcesRepository,
    this.onOpenPaymentObligation,
    this.onOpenCommerceOrder,
    required this.onOpenForm,
    required this.onOpenRequirement,
    required this.onOpenResources,
    required this.onOpenActivity,
    required this.onOpenOccurrence,
    required this.onOpenAccess,
    required this.onOpenDayOf,
    required this.onOpenLive,
    this.conversations,
    this.onOpenConversation,
  });

  final ConversationRepository? conversations;
  final ValueChanged<String>? onOpenConversation;
  final String journeyId;
  final JourneyRepository repository;
  final MakoloApiClient? api;
  final PreparationResourcesRepository? resourcesRepository;
  final ValueChanged<String>? onOpenPaymentObligation;
  final ValueChanged<String>? onOpenCommerceOrder;
  final void Function(JourneyFormSummary form) onOpenForm;
  final void Function(JourneyReference requirement) onOpenRequirement;
  final void Function(String resourcesLink) onOpenResources;
  final void Function(JourneyReference activity) onOpenActivity;
  final void Function(JourneyReference occurrence) onOpenOccurrence;
  final void Function(JourneyReference access) onOpenAccess;
  final void Function(String dayOfLink) onOpenDayOf;
  final void Function(String liveLink) onOpenLive;

  @override
  State<JourneyDetailScreen> createState() => _JourneyDetailScreenState();
}

class _JourneyDetailScreenState extends State<JourneyDetailScreen> {
  static const _selector = JourneyDetailSelector();
  static const _surfaceAdapter = ProjectionSurfaceAdapter();

  bool _refreshing = false;
  bool _respondingInvitation = false;
  String? _invitationDecision;
  MakoloActionPhase _invitationPhase = MakoloActionPhase.available;
  String? _invitationNotice;
  bool _requestedInitialRefresh = false;
  int _identityRevision = 0;

  bool _isCurrent(int revision, String id, JourneyRepository repository) =>
      mounted &&
      revision == _identityRevision &&
      id == widget.journeyId &&
      identical(repository, widget.repository);

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  @override
  void didUpdateWidget(covariant JourneyDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.journeyId != widget.journeyId ||
        oldWidget.repository != widget.repository) {
      // Old owner responses must not change another Journey/Profile's page.
      _identityRevision++;
      _refreshing = false;
      _respondingInvitation = false;
      _invitationDecision = null;
      _invitationPhase = MakoloActionPhase.available;
      _invitationNotice = null;
      _requestedInitialRefresh = false;
      unawaited(_acquireOrRefresh());
    }
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    final local = await repository.readDetail(id);
    final source = await repository.readSource(id);
    if (!_isCurrent(revision, id, repository)) return;
    if (local == null) {
      await _refresh();
      return;
    }
    final presentation = _selector.select(
      projection: local,
      source: source,
      now: DateTime.now(),
    );
    if (presentation.freshness != null &&
        presentation.freshness != FreshnessState.fresh) {
      await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    setState(() => _refreshing = true);
    var ownerReadSucceeded = false;
    try {
      await repository.refreshDetail(id);
      ownerReadSucceeded = true;
    } on Object {
      // Local content stays available independently of a transport result.
    } finally {
      if (_isCurrent(revision, id, repository)) {
        setState(() {
          _refreshing = false;
          if (ownerReadSucceeded &&
              !_respondingInvitation &&
              _invitationPhase == MakoloActionPhase.unavailable) {
            // Only a new owner read can unlock a changed-capability decision.
            _invitationPhase = MakoloActionPhase.available;
            _invitationDecision = null;
            _invitationNotice = null;
          }
        });
      }
    }
  }

  Future<void> _respondToInvitation(String decision) async {
    final api = widget.api;
    if (_respondingInvitation || api == null) return;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    setState(() {
      _respondingInvitation = true;
      _invitationDecision = decision;
      _invitationPhase = MakoloActionPhase.processing;
      _invitationNotice = null;
    });
    try {
      final endpoint =
          'api/v1/me/journeys/${Uri.encodeComponent(id)}/invitation/';
      final current = (await api.get(endpoint)).jsonObject();
      if (!_isCurrent(revision, id, repository)) return;
      final actions = current['capabilities'];
      if (current['journey_id'] != id ||
          actions is! List ||
          !actions.contains(decision)) {
        await _refresh();
        if (_isCurrent(revision, id, repository)) {
          setState(() {
            _invitationPhase = MakoloActionPhase.unavailable;
            _invitationNotice =
                'Cette invitation a changé. Consultez son état actuel.';
          });
        }
        return;
      }
      final result = (await api.post(
        endpoint,
        body: {'decision': decision},
      )).jsonObject();
      if (!_isCurrent(revision, id, repository)) return;
      if (result['journey_id'] != id ||
          (decision == 'accept' && result['status'] != 'confirmed') ||
          (decision == 'decline' && result['status'] != 'cancelled')) {
        throw const FormatException('Unconfirmed Journey invitation');
      }
      await _refresh();
      if (_isCurrent(revision, id, repository)) {
        setState(() {
          _invitationPhase = MakoloActionPhase.confirmed;
          _invitationNotice = decision == 'accept'
              ? 'Invitation acceptée.'
              : 'Invitation refusée.';
        });
      }
    } on Object {
      // A lost acknowledgement cannot be treated as failure or success.
      if (!_isCurrent(revision, id, repository)) return;
      try {
        final current = (await api.get(
          'api/v1/me/journeys/${Uri.encodeComponent(id)}/invitation/',
        )).jsonObject();
        if (!_isCurrent(revision, id, repository)) return;
        await _refresh();
        if (_isCurrent(revision, id, repository)) {
          final status = current['status'];
          setState(() {
            _invitationPhase = status == 'confirmed' || status == 'cancelled'
                ? MakoloActionPhase.confirmed
                : MakoloActionPhase.failed;
            _invitationNotice = status == 'confirmed'
                ? 'Invitation acceptée.'
                : status == 'cancelled'
                ? 'Invitation refusée.'
                : 'Vérifiez votre invitation avant de réessayer.';
          });
        }
      } on Object {
        if (_isCurrent(revision, id, repository)) {
          setState(() {
            _invitationPhase = MakoloActionPhase.failed;
            _invitationNotice = 'Aucune confirmation pour le moment. Vérifiez avant de réessayer.';
          });
        }
      }
    } finally {
      if (_isCurrent(revision, id, repository)) {
        setState(() => _respondingInvitation = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      key: ValueKey(
        'journey:${widget.repository.profileId}:${widget.journeyId}',
      ),
      stream: widget.repository.watchDetail(widget.journeyId),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<JourneySourceState>(
          stream: widget.repository.watchSource(widget.journeyId),
          initialData: JourneySourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? JourneySourceState.unknown;
            final presentation = _selector.select(
              projection: projection,
              source: source,
              now: DateTime.now(),
            );
            final available = presentation.available;
            // A missing local detail is not a transport failure. Keep the
            // page in its normal shell; only an explicit owner denial removes it.
            final ownerDenied =
                !available &&
                source.invalidated &&
                const {
                  'permission_denied',
                  'not_found',
                }.contains(source.lastErrorCode);
            final surface = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: projection?.payload,
                freshness: presentation.freshness,
                resources: const [],
                drafts: const [],
                pendingOperations: const [],
              ),
              availability: available
                  ? MakoloAvailabilityCue.content
                  : _refreshing ||
                        projectionSnapshot.connectionState ==
                            ConnectionState.waiting
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.empty,
              reachability: source.reachability,
              failure: ownerDenied
                  ? MakoloFailureCue.permissionDenied
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );

            return Scaffold(
              appBar: AppBar(
                title: const Text('Démarche'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloNetworkContextFrame(
                child: MakoloSurfaceStateView(
                  state: surface,
                  initialLoading: const MakoloLoadingState(
                    label: 'Chargement de la démarche…',
                  ),
                  empty: const MakoloEmptyState(
                    title: 'Démarche non disponible',
                    body: 'Aucun détail à afficher pour le moment.',
                  ),
                  onRetry: _refresh,
                  content: StreamBuilder<StoredProjection?>(
                    stream: widget.resourcesRepository?.watchResources(
                      widget.journeyId,
                    ),
                    builder: (context, resourcesSnapshot) => _JourneyContent(
                      presentation: presentation,
                      resourcesPreview: JourneyResourcePreview.fromProjection(
                        resourcesSnapshot.data,
                      ),
                      resourcesKnown: resourcesSnapshot.data != null,
                      onOpenPaymentObligation: widget.onOpenPaymentObligation,
                      onOpenCommerceOrder: widget.onOpenCommerceOrder,
                      invitationEnabled:
                          widget.api != null &&
                          !_respondingInvitation &&
                          _invitationPhase != MakoloActionPhase.confirmed &&
                          _invitationPhase != MakoloActionPhase.unavailable,
                      invitationDecision: _invitationDecision,
                      invitationPhase: _invitationPhase,
                      invitationNotice: _invitationNotice,
                      onInvitationDecision: _respondToInvitation,
                      onOpenForm: widget.onOpenForm,
                      onOpenRequirement: widget.onOpenRequirement,
                      onOpenResources: widget.onOpenResources,
                      onOpenActivity: widget.onOpenActivity,
                      onOpenOccurrence: widget.onOpenOccurrence,
                      onOpenAccess: widget.onOpenAccess,
                      onOpenDayOf: widget.onOpenDayOf,
                      onOpenLive: widget.onOpenLive,
                      conversationEntry:
                          widget.conversations != null &&
                              widget.onOpenConversation != null
                          ? ConversationContextAction(
                              repository: widget.conversations!,
                              kind: 'journey',
                              contextId: widget.journeyId,
                              onOpen: widget.onOpenConversation!,
                              iconOnly: true,
                            )
                          : null,
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _JourneyContent extends StatelessWidget {
  const _JourneyContent({
    required this.presentation,
    required this.resourcesPreview,
    required this.resourcesKnown,
    this.onOpenPaymentObligation,
    this.onOpenCommerceOrder,
    required this.invitationEnabled,
    required this.invitationDecision,
    required this.invitationPhase,
    required this.invitationNotice,
    required this.onInvitationDecision,
    required this.onOpenForm,
    required this.onOpenRequirement,
    required this.onOpenResources,
    required this.onOpenActivity,
    required this.onOpenOccurrence,
    required this.onOpenAccess,
    required this.onOpenDayOf,
    required this.onOpenLive,
    this.conversationEntry,
  });

  final Widget? conversationEntry;
  final JourneyDetailPresentation presentation;
  final List<JourneyResourcePreview> resourcesPreview;
  final bool resourcesKnown;
  final ValueChanged<String>? onOpenPaymentObligation;
  final ValueChanged<String>? onOpenCommerceOrder;
  final bool invitationEnabled;
  final String? invitationDecision;
  final MakoloActionPhase invitationPhase;
  final String? invitationNotice;
  final void Function(String decision) onInvitationDecision;
  final void Function(JourneyFormSummary form) onOpenForm;
  final void Function(JourneyReference requirement) onOpenRequirement;
  final void Function(String resourcesLink) onOpenResources;
  final void Function(JourneyReference activity) onOpenActivity;
  final void Function(JourneyReference occurrence) onOpenOccurrence;
  final void Function(JourneyReference access) onOpenAccess;
  final void Function(String dayOfLink) onOpenDayOf;
  final void Function(String liveLink) onOpenLive;

  @override
  Widget build(BuildContext context) {
    final action = _nextActionButton();
    final composition = JourneyComposition.from(
      presentation,
      resourcesKnown: resourcesKnown,
      resourcesCount: resourcesPreview.length,
    );
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: ListView(
          key: const PageStorageKey<String>('journey-detail-content'),
          padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
          children: [
            _JourneyIdentity(
              presentation: presentation,
              conversationEntry: conversationEntry,
              onOpenDayOf: onOpenDayOf,
              onOpenLive: onOpenLive,
            ),
            if (presentation.summary != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  MakoloSpacing.inner,
                  MakoloSpacing.sm,
                  MakoloSpacing.inner,
                  0,
                ),
                child: Text(
                  presentation.summary!,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
            if (presentation.isTerminal) ...[
              const SizedBox(height: MakoloSpacing.lg),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: _JourneyOutcomeCard(presentation: presentation),
              ),
            ],
            if (presentation.canRespondInvitation &&
                !presentation.isTerminal) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                  vertical: MakoloSpacing.lg,
                ),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(MakoloSpacing.inner),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Votre invitation',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: MakoloSpacing.md),
                        Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          children: [
                            MakoloActionButton(
                              label: 'Accepter',
                              icon: Icons.check_rounded,
                              onPressed: invitationEnabled
                                  ? () => onInvitationDecision('accept')
                                  : null,
                              appearance: MakoloActionAppearance.primary,
                              phase: invitationDecision == 'accept'
                                  ? invitationPhase
                                  : invitationEnabled
                                  ? MakoloActionPhase.available
                                  : MakoloActionPhase.unavailable,
                            ),
                            MakoloActionButton(
                              label: 'Refuser',
                              icon: Icons.close_rounded,
                              onPressed: invitationEnabled
                                  ? () => onInvitationDecision('decline')
                                  : null,
                              appearance: MakoloActionAppearance.secondary,
                              phase: invitationDecision == 'decline'
                                  ? invitationPhase
                                  : invitationEnabled
                                  ? MakoloActionPhase.available
                                  : MakoloActionPhase.unavailable,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
            if (invitationNotice != null)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: Text(invitationNotice!),
              ),
            if (!presentation.isTerminal &&
                !presentation.canRespondInvitation &&
                composition.situation != JourneySituation.calm) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: _JourneySituationPanel(
                  presentation: presentation,
                  composition: composition,
                  primaryAction: action,
                  ownerAction: (label, link) =>
                      _ownerActionForLink(label, link),
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
            ],
            if (presentation.steps.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Où j’en suis',
                child: _JourneyPath(
                  steps: presentation.steps,
                  hasBranches: composition.hasBranches,
                ),
              ),
            ],
            if (composition.hasPreparation) ...[
              const SizedBox(height: MakoloSpacing.sm),
              MakoloSection(
                title: 'Ma préparation',
                child: _JourneyPreparation(
                  presentation: presentation,
                  composition: composition,
                  ownerAction: (label, link) =>
                      _ownerActionForLink(label, link),
                  onOpenForm: onOpenForm,
                  onOpenRequirement: onOpenRequirement,
                ),
              ),
            ],
            if (composition.hasDocuments) ...[
              const SizedBox(height: MakoloSpacing.md),
              MakoloSection(
                title: 'Documents et ressources',
                child: MakoloCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (resourcesPreview.isNotEmpty)
                        SizedBox(
                          height: 105,
                          child: ListView.separated(
                            scrollDirection: Axis.horizontal,
                            itemCount: resourcesPreview.length,
                            separatorBuilder: (_, _) =>
                                const SizedBox(width: MakoloSpacing.sm),
                            itemBuilder: (context, index) =>
                                _JourneyResourceTile(
                                  resource: resourcesPreview[index],
                                ),
                          ),
                        ),
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton.icon(
                          onPressed: () =>
                              onOpenResources(presentation.resourcesLink!),
                          icon: const Icon(Icons.arrow_forward_rounded),
                          iconAlignment: IconAlignment.end,
                          label: Text(resourcesKnown
                              ? 'Voir les ${resourcesPreview.length} ressources'
                              : 'Voir les ressources'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            if (_hasAdditionalPracticalFacts(presentation.practical)) ...[
              const SizedBox(height: MakoloSpacing.md),
              MakoloSection(
                title: 'À savoir',
                child: _JourneyPracticalCard(facts: presentation.practical!),
              ),
            ],
            if (composition.hasEngagements) ...[
              const SizedBox(height: MakoloSpacing.md),
              MakoloSection(
                title: 'Mes engagements',
                child: _JourneyEngagements(
                  presentation: presentation,
                  onOpenPaymentObligation: onOpenPaymentObligation,
                  onOpenCommerceOrder: onOpenCommerceOrder,
                  onOpenAccess: onOpenAccess,
                ),
              ),
            ],
            if ((presentation.activity?.link != null &&
                    presentation.activity!.label != presentation.title) ||
                presentation.occurrence?.link != null) ...[
              const SizedBox(height: MakoloSpacing.md),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: MakoloCard(
                  child: Column(
                    children: [
                      if (presentation.activity?.link != null &&
                          presentation.activity!.label != presentation.title)
                        _ReferenceCard(
                          reference: presentation.activity!,
                          contextLabel: 'Activité',
                          onTap: () => onOpenActivity(presentation.activity!),
                        ),
                      if (presentation.occurrence?.link != null)
                        _ReferenceCard(
                          reference: presentation.occurrence!,
                          contextLabel: 'Occurrence',
                          hideRepeatedTitle: presentation.occurrence!.label ==
                              presentation.title,
                          onTap: () =>
                              onOpenOccurrence(presentation.occurrence!),
                        ),
                    ],
                  ),
                ),
              ),
            ],

          ],
        ),
      ),
    );
  }

  Widget? _nextActionButton() => _ownerActionForLink(
    presentation.nextActionLabel ?? 'Continuer',
    presentation.nextActionLink,
    primary: true,
  );

  /// Follow only links exposed by the actual owner projection. An unknown
  /// next-action URL remains visible as information, never as a false CTA.
  Widget? _ownerActionForLink(
    String label,
    String? link, {
    bool primary = false,
  }) {
    if (link == null || link.isEmpty || presentation.isTerminal) return null;
    final appearance = primary
        ? MakoloActionAppearance.primary
        : MakoloActionAppearance.secondary;

    for (final form in presentation.forms) {
      if (form.canComplete && form.detailLink == link) {
        return MakoloActionButton(
          appearance: appearance,
          label: label,
          onPressed: () => onOpenForm(form),
        );
      }
    }
    for (final requirement in presentation.requirements) {
      if (requirement.link == link) {
        return MakoloActionButton(
          appearance: appearance,
          label: label,
          onPressed: () => onOpenRequirement(requirement),
        );
      }
    }
    if (presentation.resourcesLink == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenResources(link),
      );
    }
    if (presentation.activity?.link == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenActivity(presentation.activity!),
      );
    }
    if (presentation.occurrence?.link == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenOccurrence(presentation.occurrence!),
      );
    }
    if (presentation.access?.link == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenAccess(presentation.access!),
      );
    }
    if (presentation.liveLink == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenLive(link),
      );
    }
    if (presentation.dayOfLink == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenDayOf(link),
      );
    }
    return null;
  }
}

class _JourneyEngagements extends StatelessWidget {
  const _JourneyEngagements({
    required this.presentation,
    this.onOpenPaymentObligation,
    this.onOpenCommerceOrder,
    required this.onOpenAccess,
  });

  final JourneyDetailPresentation presentation;
  final ValueChanged<String>? onOpenPaymentObligation;
  final ValueChanged<String>? onOpenCommerceOrder;
  final void Function(JourneyReference) onOpenAccess;

  @override
  Widget build(BuildContext context) {
    final order = presentation.order;
    return MakoloCard(
      child: Column(
        children: [
          for (final obligation in presentation.payments) ...[
            _JourneyPaymentCard(
              payment: obligation,
              onOpenPaymentObligation: onOpenPaymentObligation,
              onOpenCommerceOrder: onOpenCommerceOrder,
            ),
            const Divider(height: 8),
          ],
          if (order != null)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.shopping_bag_outlined,
                  color: _journeyAccent(context)),
              title: const Text('Ma commande'),
              subtitle: Text([
                if (presentation.payments.isEmpty &&
                    order.total != null && order.currency != null)
                  '${order.total} ${order.currency}',
                MakoloHumanization.presentationLabel(order.state) ??
                    order.state,
              ].join(' · ')),
              trailing: onOpenCommerceOrder == null
                  ? null : const Icon(Icons.chevron_right_rounded),
              onTap: onOpenCommerceOrder == null
                  ? null : () => onOpenCommerceOrder!(order.id),
            ),
          if (order != null && presentation.access != null)
            const Divider(height: 8),
          if (presentation.access != null)
            _ReferenceCard(
              reference: presentation.access!,
              onTap: presentation.access!.link == null
                  ? null : () => onOpenAccess(presentation.access!),
            ),
        ],
      ),
    );
  }
}

/// Terminal labels are solely the owner Journey state, never an invented
/// success or a percentage computed from unrelated capabilities.
/// One human-readable current situation. No synthetic task or owner state.
class _JourneySituationPanel extends StatelessWidget {
  const _JourneySituationPanel({
    required this.presentation,
    required this.composition,
    required this.primaryAction,
    required this.ownerAction,
  });

  final JourneyDetailPresentation presentation;
  final JourneyComposition composition;
  final Widget? primaryAction;
  final Widget? Function(String label, String? link) ownerAction;

  @override
  Widget build(BuildContext context) {
    final situation = composition.situation;
    final firstBlocker = presentation.blockers.isNotEmpty
        ? presentation.blockers.first
        : null;
    final firstWaiting = presentation.waiting.isNotEmpty
        ? presentation.waiting.first
        : null;
    final title = switch (situation) {
      JourneySituation.blocked => 'Ce qui bloque',
      JourneySituation.choices => 'Plusieurs possibilités',
      JourneySituation.waiting => 'En attente',
      JourneySituation.action => 'Pour avancer',
      _ => '',
    };
    final icon = switch (situation) {
      JourneySituation.blocked => Icons.report_problem_outlined,
      JourneySituation.choices => Icons.alt_route_rounded,
      JourneySituation.waiting => Icons.hourglass_top_rounded,
      _ => Icons.arrow_outward_rounded,
    };
    final detail = switch (situation) {
      JourneySituation.blocked =>
        firstBlocker?.summary ?? 'Une demande a été refusée.',
      JourneySituation.waiting =>
        firstWaiting?.summary ?? 'Une réponse est attendue.',
      JourneySituation.action || JourneySituation.choices =>
        presentation.nextActionLabel,
      _ => null,
    };
    final color = situation == JourneySituation.blocked
        ? Theme.of(context).colorScheme.error
        : _journeyAccent(context);
    final seen = <String>{};
    return DecoratedBox(
      key: const Key('journey-current-situation'),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(MakoloSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color, size: 21),
                const SizedBox(width: MakoloSpacing.sm),
                Expanded(
                  child: Text(title,
                    style: Theme.of(context).textTheme.titleMedium),
                ),
              ],
            ),
            if (detail != null && detail.trim().isNotEmpty &&
                detail.trim().toLowerCase() !=
                    presentation.title.trim().toLowerCase()) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(detail),
            ],
            if (situation == JourneySituation.choices) ...[
              const SizedBox(height: MakoloSpacing.sm),
              for (final item in presentation.actorInterventions)
                if (item.nextLink != null &&
                    item.nextLink!.isNotEmpty &&
                    seen.add(item.key.isNotEmpty ? item.key : item.nextLink!)) ...[
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.xs),
                    child: ownerAction(
                      item.nextLabel ?? item.summary,
                      item.nextLink,
                    ) ?? Text(item.summary),
                  ),
                ],
              if (presentation.nextActionLink != null &&
                  seen.add(presentation.nextActionKey ??
                      presentation.nextActionLink!))
                primaryAction ?? const SizedBox.shrink(),
            ] else if (primaryAction != null &&
                (situation == JourneySituation.action ||
                 situation == JourneySituation.blocked)) ...[
              const SizedBox(height: MakoloSpacing.sm),
              primaryAction!,
            ],
          ],
        ),
      ),
    );
  }
}

class _JourneyOutcomeCard extends StatelessWidget {
  const _JourneyOutcomeCard({required this.presentation});

  final JourneyDetailPresentation presentation;

  @override
  Widget build(BuildContext context) {
    final outcome = switch (presentation.stateCode) {
      'fulfilled' => ('Démarche réalisée', Icons.check_circle_outline_rounded),
      'rejected' => ('Demande refusée', Icons.info_outline_rounded),
      'cancelled' => ('Démarche annulée', Icons.cancel_outlined),
      'expired' => ('Démarche expirée', Icons.event_busy_outlined),
      _ => ('Démarche', Icons.route_outlined),
    };
    return MakoloCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(outcome.$2, size: 28, color: _journeyAccent(context)),
          const SizedBox(width: MakoloSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  outcome.$1,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                if (presentation.journeyState.trim().isNotEmpty)
                  Text(presentation.journeyState),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The top of N3 reads as a human objective, not a collection of owners.
class _JourneyIdentity extends StatelessWidget {
  const _JourneyIdentity({
    required this.presentation,
    this.conversationEntry,
    required this.onOpenDayOf,
    required this.onOpenLive,
  });

  final JourneyDetailPresentation presentation;
  final Widget? conversationEntry;
  final ValueChanged<String> onOpenDayOf;
  final ValueChanged<String> onOpenLive;

  IconData get _symbol => switch (presentation.workflowKind) {
    'purchase' => Icons.shopping_bag_outlined,
    'reservation' => Icons.event_available_outlined,
    'registration' => Icons.badge_outlined,
    'invitation' => Icons.mail_outline_rounded,
    'service' => Icons.handyman_outlined,
    'fulfillment' => Icons.task_alt_outlined,
    _ => Icons.route_outlined,
  };

  @override
  Widget build(BuildContext context) {
    final palette = Theme.of(context).colorScheme;
    final facts = presentation.practical;
    final date = JourneyDayPresentation.civilDate(facts?.startDate) ??
        facts?.startAt?.toLocal();
    final dateLabel = date == null
        ? null
        : DateFormat('EEE d MMM', 'fr').format(date);
    final startTime = JourneyDayPresentation.clock(facts?.startTime) ??
        (facts?.startAt == null
            ? null
            : DateFormat('HH:mm').format(facts!.startAt!.toLocal())
                .replaceFirst(':', 'h'));
    final endTime = JourneyDayPresentation.clock(facts?.endTime);
    final sameDay = facts?.endDate == null ||
        facts?.endDate == facts?.startDate;
    String shorten(String value) =>
        value.endsWith('h00') ? value.substring(0, value.length - 2) : value;
    final timeLabel = startTime == null
        ? null
        : sameDay && endTime != null
        ? '${shorten(startTime)}–${shorten(endTime)}'
        : shorten(startTime);
    final placeLabel = JourneyDayPresentation.place(
      name: facts?.placeName,
      locality: facts?.placeLocality,
    );
    final status = MakoloHumanization.presentationLabel(
      presentation.journeyState,
    );
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.inner,
        MakoloSpacing.sm,
        MakoloSpacing.inner,
        0,
      ),
      child: DecoratedBox(
        key: const Key('journey-identity'),
        decoration: BoxDecoration(
          color: palette.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: palette.outlineVariant),
        ),
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(_symbol, color: _journeyAccent(context), size: 24),
                  const SizedBox(width: MakoloSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'MON OBJECTIF',
                          style: Theme.of(context).textTheme.labelSmall
                              ?.copyWith(color: palette.onSurfaceVariant),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          presentation.title,
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(fontWeight: FontWeight.w800),
                        ),
                      ],
                    ),
                  ),
                  if (facts?.startDate != null)
                    Padding(
                      padding: const EdgeInsets.only(left: 4),
                      child: JourneyDayBadge(
                        occurrenceDate: facts!.startDate!,
                        timezoneName: facts.timezone,
                        onOpenDayOf: presentation.dayOfLink == null
                            ? null
                            : () => onOpenDayOf(presentation.dayOfLink!),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: MakoloSpacing.xs),
              Row(
                children: [
                  if (status != null) ...[
                    MakoloStatus(label: status),
                    const SizedBox(width: MakoloSpacing.xs),
                  ],
                  if (conversationEntry != null)
                    conversationEntry!,
                  if (presentation.liveLink != null)
                    IconButton(
                      tooltip: 'Ouvrir Makolo Live',
                      icon: const Icon(Icons.sensors_rounded),
                      onPressed: () => onOpenLive(presentation.liveLink!),
                    ),
                ],
              ),
              if (dateLabel != null || timeLabel != null ||
                  placeLabel != null) ...[
                const SizedBox(height: MakoloSpacing.xs),
                Divider(color: palette.outlineVariant, height: 12),
                Wrap(
                  spacing: MakoloSpacing.md,
                  runSpacing: MakoloSpacing.xs,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    if (dateLabel != null)
                      _JourneyHeroFact(
                        icon: Icons.calendar_today_outlined,
                        label: dateLabel,
                      ),
                    if (timeLabel != null)
                      _JourneyHeroFact(
                        icon: Icons.schedule_outlined,
                        label: timeLabel,
                      ),
                    if (placeLabel != null)
                      _JourneyHeroFact(
                        icon: Icons.place_outlined,
                        label: placeLabel,
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _JourneyHeroFact extends StatelessWidget {
  const _JourneyHeroFact({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.onSurfaceVariant;
    return Semantics(
      label: label,
      child: ExcludeSemantics(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 4),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

/// JourneySteps are shown as facts, not a locally computed percentage/timeline.
/// Dependencies are named only when the owner supplied both linked steps.
class _JourneyPath extends StatelessWidget {
  const _JourneyPath({
    required this.steps,
    required this.hasBranches,
  });

  final List<JourneyStepSummary> steps;
  final bool hasBranches;

  @override
  Widget build(BuildContext context) {
    final active = steps.where((step) => !step.isTerminal &&
        step.status != 'pending').toList();
    final future = steps.where((step) => step.status == 'pending').toList();
    final past = steps.where((step) => step.isTerminal).toList();
    final shownFuture = hasBranches ? future : future.take(2).toList();
    final hiddenFuture = hasBranches ? <JourneyStepSummary>[] :
        future.skip(2).toList();
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (hasBranches) ...[
            Row(
              children: [
                Icon(Icons.alt_route_rounded,
                    size: 18, color: _journeyAccent(context)),
                const SizedBox(width: MakoloSpacing.sm),
                const Expanded(
                  child: Text('Plusieurs chemins possibles'),
                ),
              ],
            ),
            const Divider(height: 16),
          ],
          for (final step in active)
            _JourneyStepRow(step: step, allSteps: steps),
          for (final step in shownFuture)
            _JourneyStepRow(step: step, allSteps: steps),
          if (hiddenFuture.isNotEmpty)
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: Text(
                'Voir les ${hiddenFuture.length} étapes suivantes',
              ),
              children: [
                for (final step in hiddenFuture)
                  _JourneyStepRow(step: step, allSteps: steps),
              ],
            ),
          if (past.isNotEmpty)
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              leading: Icon(Icons.check_circle_outline_rounded,
                  color: _journeyAccent(context)),
              title: Text(
                '${past.length} étape${past.length > 1 ? 's' : ''} passée${past.length > 1 ? 's' : ''}',
              ),
              children: [
                for (final step in past)
                  _JourneyStepRow(step: step, allSteps: steps),
              ],
            ),
        ],
      ),
    );
  }
}

class _JourneyStepRow extends StatelessWidget {
  const _JourneyStepRow({required this.step, required this.allSteps});

  final JourneyStepSummary step;
  final List<JourneyStepSummary> allSteps;

  @override
  Widget build(BuildContext context) {
    final label = switch (step.status) {
      'completed' => 'Terminée',
      'skipped' => 'Non retenue',
      'cancelled' => 'Annulée',
      'in_progress' => 'En cours',
      'blocked' => 'Bloquée',
      'ready' => 'Prête',
      'pending' => 'En attente',
      _ => null,
    };
    final icon = switch (step.status) {
      'completed' => Icons.check_circle_outline_rounded,
      'skipped' || 'cancelled' => Icons.remove_circle_outline_rounded,
      'blocked' => Icons.error_outline_rounded,
      'in_progress' => Icons.radio_button_checked_rounded,
      'ready' => Icons.play_circle_outline_rounded,
      _ => Icons.radio_button_unchecked_rounded,
    };
    final dependencies = [
      for (final id in step.dependsOn)
        for (final candidate in allSteps)
          if (candidate.id == id) candidate.title,
    ];
    return ListTile(
      dense: true,
      visualDensity: VisualDensity.compact,
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon, color: _journeyAccent(context)),
      title: Text(step.title),
      subtitle: label == null && dependencies.isEmpty
          ? null
          : Text(
              [
                if (label != null) label,
                if (dependencies.isNotEmpty)
                  'Après : ${dependencies.join(', ')}',
              ].join(' · '),
            ),
    );
  }
}

bool _showReadinessItem(
  JourneyDetailPresentation presentation,
  JourneyReadinessItem item,
) {
  if (item.key == presentation.nextActionKey &&
      presentation.nextActionKey != null)
    return false;
  final repeatingObjective =
      item.summary.trim().toLowerCase() ==
      presentation.title.trim().toLowerCase();
  return !(repeatingObjective && item.nextLink == null);
}

class _JourneyPreparation extends StatelessWidget {
  const _JourneyPreparation({
    required this.presentation,
    required this.composition,
    required this.ownerAction,
    required this.onOpenForm,
    required this.onOpenRequirement,
  });

  final JourneyDetailPresentation presentation;
  final JourneyComposition composition;
  final Widget? Function(String, String?) ownerAction;
  final void Function(JourneyFormSummary) onOpenForm;
  final void Function(JourneyReference) onOpenRequirement;

  @override
  Widget build(BuildContext context) {
    final hasReadiness = !presentation.isTerminal &&
        (presentation.ready.isNotEmpty ||
            presentation.waiting.isNotEmpty ||
            presentation.blockers.isNotEmpty ||
            composition.interventions.isNotEmpty);
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final form in presentation.forms) ...[
            _FormCard(form: form, onOpen: onOpenForm),
            const Divider(height: 8),
          ],
          for (final requirement in presentation.requirements) ...[
            _JourneyRequirementRow(
              reference: requirement,
              onOpen: onOpenRequirement,
            ),
            const Divider(height: 8),
          ],
          if (hasReadiness)
            _ReadinessGroups(
              presentation: presentation,
              composition: composition,
              ownerAction: ownerAction,
            ),
        ],
      ),
    );
  }
}

class _JourneyRequirementRow extends StatelessWidget {
  const _JourneyRequirementRow({
    required this.reference,
    required this.onOpen,
  });

  final JourneyReference reference;
  final void Function(JourneyReference) onOpen;

  @override
  Widget build(BuildContext context) {
    final state = MakoloHumanization.presentationLabel(reference.state);
    final fulfilled = const {
      'satisfied', 'accepted', 'approved', 'completed',
    }.contains(reference.state);
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        fulfilled ? Icons.check_circle_outline_rounded :
            Icons.assignment_turned_in_outlined,
        color: _journeyAccent(context),
      ),
      title: Text(reference.label),
      subtitle: Text([
        if (reference.isRequired) 'Obligatoire',
        if (state != null) state,
      ].join(' · ')),
      trailing: reference.link == null
          ? null : const Icon(Icons.chevron_right_rounded),
      onTap: reference.link == null ? null : () => onOpen(reference),
    );
  }
}

bool _usefulReadySummary(String value) {
  final normalized = value.toLowerCase().trim();
  return !normalized.startsWith("l'état de la démarche permet") &&
      !normalized.startsWith('aucun obstacle actif') &&
      !normalized.startsWith("l’occurrence est exploitable") &&
      !normalized.startsWith("l'occurrence est exploitable");
}

class _ReadinessGroups extends StatelessWidget {
  const _ReadinessGroups({
    required this.presentation,
    required this.composition,
    required this.ownerAction,
  });

  final JourneyDetailPresentation presentation;
  final JourneyComposition composition;
  final Widget? Function(String label, String? link) ownerAction;

  @override
  Widget build(BuildContext context) {
    final situation = composition.situation;
    final interventions = situation == JourneySituation.choices
        ? <JourneyReadinessItem>[]
        : composition.interventions;
    final blockers = situation == JourneySituation.blocked &&
            presentation.blockers.isNotEmpty
        ? presentation.blockers.skip(1).toList()
        : presentation.blockers;
    final waiting = situation == JourneySituation.waiting &&
            presentation.waiting.isNotEmpty
        ? presentation.waiting.skip(1).toList()
        : presentation.waiting;
    final groups = <(String, List<JourneyReadinessItem>, IconData)>[
      ('Encore à résoudre', blockers, Icons.warning_amber_rounded),
      ('De votre côté', interventions, Icons.touch_app_outlined),
      ('En attente', waiting, Icons.hourglass_empty_rounded),
    ].where((item) => item.$2.isNotEmpty).toList();
    final readableReady = presentation.ready
        .where((item) => _usefulReadySummary(item.summary))
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final group in groups) ...[
          Row(
            children: [
              Icon(group.$3, size: 18, color: _journeyAccent(context)),
              const SizedBox(width: MakoloSpacing.sm),
              Expanded(
                child: Text(group.$1,
                    style: Theme.of(context).textTheme.titleSmall),
              ),
            ],
          ),
          for (final item in group.$2)
            Padding(
              padding: const EdgeInsets.only(left: 27, top: 5, bottom: 6),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(item.summary),
                  if (item.nextLabel != null && item.nextLink != null &&
                      item.nextLink != presentation.nextActionLink)
                    Padding(
                      padding: const EdgeInsets.only(top: 5),
                      child: ownerAction(item.nextLabel!, item.nextLink) ??
                          const SizedBox.shrink(),
                    ),
                ],
              ),
            ),
          const Divider(height: 12),
        ],
        if (presentation.ready.isNotEmpty)
          readableReady.isEmpty
              ? ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.check_circle_outline_rounded,
                      color: _journeyAccent(context)),
                  title: Text(
                    '${presentation.ready.length} points vérifiés',
                  ),
                )
              : ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: EdgeInsets.zero,
                  leading: Icon(Icons.check_circle_outline_rounded,
                      color: _journeyAccent(context)),
                  title: Text(
                    '${presentation.ready.length} points vérifiés',
                  ),
                  children: [
                    for (final item in readableReady)
                      ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.check_rounded, size: 18),
                        title: Text(item.summary),
                      ),
                  ],
                ),
      ],
    );
  }
}

bool _hasAdditionalPracticalFacts(JourneyPracticalFacts? facts) {
  if (facts == null) return false;
  final location = JourneyDayPresentation.additionalPlace(
    name: facts.placeName,
    locality: facts.placeLocality,
    address: facts.placeAddress,
  );
  final endIsDifferent =
      facts.endDate != null &&
      (facts.endDate != facts.startDate || facts.endTime != facts.startTime);
  final hasEndTime = facts.endTime != null && facts.endTime != facts.startTime;
  return location != null ||
      (facts.accessInstructions?.trim().isNotEmpty ?? false) ||
      endIsDifferent ||
      hasEndTime;
}

/// The hero already owns the main date, hour and location; show only genuinely
/// additional practical information here.
IconData _resourceIcon(JourneyResourcePreview resource) {
  final mime = resource.mimeType?.toLowerCase() ?? '';
  if (mime.startsWith('image/')) return Icons.image_outlined;
  if (mime.startsWith('video/')) return Icons.videocam_outlined;
  if (mime == 'application/pdf') return Icons.picture_as_pdf_outlined;
  return switch (resource.kind) {
    'url' => Icons.link_rounded,
    'text' => Icons.notes_rounded,
    'file' => Icons.description_outlined,
    _ => Icons.folder_open_outlined,
  };
}

class _JourneyResourceTile extends StatelessWidget {
  const _JourneyResourceTile({required this.resource});

  final JourneyResourcePreview resource;

  @override
  Widget build(BuildContext context) {
    final type = switch (resource.kind) {
      'url' => 'Lien',
      'text' => 'Instruction',
      'file' => 'Document',
      _ => 'Ressource',
    };
    return Semantics(
      label: '${resource.title}. $type',
      child: ExcludeSemantics(
        child: Container(
          width: 154,
          padding: const EdgeInsets.all(MakoloSpacing.sm),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(_resourceIcon(resource),
                  size: 22, color: _journeyAccent(context)),
              const SizedBox(height: 5),
              Text(resource.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall
                      ?.copyWith(fontWeight: FontWeight.w700)),
              if (resource.description != null)
                Text(resource.description!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall),
            ],
          ),
        ),
      ),
    );
  }
}

class _JourneyPracticalCard extends StatelessWidget {
  const _JourneyPracticalCard({required this.facts});

  final JourneyPracticalFacts facts;

  @override
  Widget build(BuildContext context) {
    final additionalPlace = JourneyDayPresentation.additionalPlace(
      name: facts.placeName,
      locality: facts.placeLocality,
      address: facts.placeAddress,
    );
    final endDate = JourneyDayPresentation.civilDate(facts.endDate);
    final endTime = JourneyDayPresentation.clock(facts.endTime);
    final showEnd =
        facts.endDate != null &&
        (facts.endDate != facts.startDate || facts.endTime != facts.startTime);
    final showTimeOnly =
        endTime != null &&
        endTime != JourneyDayPresentation.clock(facts.startTime);
    final endLabel = [
      if (showEnd && endDate != null)
        MaterialLocalizations.of(context).formatMediumDate(endDate),
      if (showTimeOnly) endTime,
    ].join(' · ');
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (additionalPlace != null)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                Icons.directions_outlined,
                color: _journeyAccent(context),
              ),
              title: const Text('Adresse'),
              subtitle: Text(additionalPlace),
            ),
          if (endLabel.isNotEmpty)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                Icons.event_available_outlined,
                color: _journeyAccent(context),
              ),
              title: const Text('Fin prévue'),
              subtitle: Text(endLabel),
            ),
          if (facts.accessInstructions?.trim().isNotEmpty == true)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                Icons.info_outline_rounded,
                color: _journeyAccent(context),
              ),
              title: const Text('Sur place'),
              subtitle: Text(facts.accessInstructions!),
            ),
        ],
      ),
    );
  }
}

class _JourneyPaymentCard extends StatelessWidget {
  const _JourneyPaymentCard({
    required this.payment,
    this.onOpenPaymentObligation,
    this.onOpenCommerceOrder,
  });

  final JourneyPaymentSummary payment;
  final ValueChanged<String>? onOpenPaymentObligation;
  final ValueChanged<String>? onOpenCommerceOrder;

  @override
  Widget build(BuildContext context) {
    final label = switch (payment.state) {
      'paid' || 'succeeded' || 'completed' || 'settled' => 'Payé',
      'pending' || 'pending_payment' => 'En attente',
      'processing' => 'En cours',
      'satisfied' => 'Réglé',
      'waived' => 'Dispensé',
      'refunded' => 'Remboursé',
      'expired' => 'Expiré',
      'failed' => 'Échec',
      'cancelled' => 'Annulé',
      _ => null,
    };
    VoidCallback? open;
    if (payment.obligationId != null && onOpenPaymentObligation != null) {
      open = () => onOpenPaymentObligation!(payment.obligationId!);
    } else if (payment.orderId != null && onOpenCommerceOrder != null) {
      open = () => onOpenCommerceOrder!(payment.orderId!);
    }
    return ListTile(
      onTap: open,
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        Icons.account_balance_wallet_outlined,
        color: _journeyAccent(context),
      ),
      title: Text('${payment.amount} ${payment.currency}'),
      subtitle: label == null && payment.reason == null
          ? null
          : Text(
              [
                if (label != null) label,
                if (payment.reason != null && payment.reason!.isNotEmpty)
                  payment.reason!,
              ].join(' · '),
            ),
      trailing: open == null ? null : const Icon(Icons.chevron_right_rounded),
    );
  }
}

class _FormCard extends StatelessWidget {
  const _FormCard({required this.form, required this.onOpen});

  final JourneyFormSummary form;
  final void Function(JourneyFormSummary form) onOpen;

  @override
  Widget build(BuildContext context) {
    final label = form.canComplete
        ? 'À compléter'
        : MakoloHumanization.presentationLabel(form.state);
    final deadline = form.dueAt == null
        ? null
        : MaterialLocalizations.of(context)
              .formatMediumDate(form.dueAt!.toLocal());
    return ListTile(
        dense: true,
        onTap: form.detailLink.isEmpty ? null : () => onOpen(form),
        contentPadding: EdgeInsets.zero,
        leading: Icon(
          form.canComplete ? Icons.edit_outlined : Icons.description_outlined,
          color: _journeyAccent(context),
        ),
        title: Text(form.title),
        subtitle: Text(
          [
            if (label != null) label,
            if (form.required) 'Obligatoire',
            if (deadline != null) 'Avant le $deadline',
          ].join(' · '),
        ),
        trailing: form.detailLink.isNotEmpty
            ? const Icon(Icons.chevron_right_rounded)
            : null,
    );
  }
}

class _ReferenceCard extends StatelessWidget {
  const _ReferenceCard({
    required this.reference,
    this.onTap,
    this.contextLabel,
    this.hideRepeatedTitle = false,
  });

  final JourneyReference reference;
  final VoidCallback? onTap;
  final String? contextLabel;
  final bool hideRepeatedTitle;

  @override
  Widget build(BuildContext context) {
    final title = switch (contextLabel) {
      'Activité' => 'À propos de l’activité',
      'Occurrence' => 'Date ou séance',
      _ => reference.label == 'Accès' ? 'Mon accès' : reference.label,
    };
    final symbol = switch (contextLabel) {
      'Activité' => Icons.info_outline_rounded,
      'Occurrence' => Icons.calendar_today_outlined,
      _ =>
        reference.label == 'Accès'
            ? Icons.badge_outlined
            : Icons.fact_check_outlined,
    };
    final state = MakoloHumanization.presentationLabel(reference.state);
    final subtitle = [
      if (contextLabel != null &&
          !hideRepeatedTitle &&
          reference.label.trim().isNotEmpty &&
          reference.label != contextLabel)
        reference.label,
      if (contextLabel == null && reference.isRequired) 'Obligatoire',
      if (state != null) state,
    ].join(' · ');
    return ListTile(
        dense: true,
        onTap: onTap,
        contentPadding: EdgeInsets.zero,
        leading: Icon(symbol, color: _journeyAccent(context)),
        title: Text(title),
        subtitle: subtitle.isEmpty ? null : Text(subtitle),
        trailing: onTap == null
            ? null
            : const Icon(Icons.chevron_right_rounded),
    );
  }
}
