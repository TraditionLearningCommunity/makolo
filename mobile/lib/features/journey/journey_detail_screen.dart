import 'dart:async';

import 'package:flutter/material.dart';

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
import 'journey_repository.dart';
import 'journey_selector.dart';
import 'journey_time_presentation.dart';

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
    try {
      await repository.refreshDetail(id);
    } on Object {
      // Local content stays available independently of a transport result.
    } finally {
      if (_isCurrent(revision, id, repository)) {
        setState(() => _refreshing = false);
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
            _invitationPhase =
                status == 'confirmed' || status == 'cancelled'
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
            _invitationNotice =
                'Aucune confirmation pour le moment. Vérifiez avant de réessayer.';
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
                          widget.api != null && !_respondingInvitation,
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
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: ListView(
          key: const PageStorageKey<String>('journey-detail-content'),
          padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
          children: [
            _JourneyIdentity(presentation: presentation),
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
                presentation.nextActionLabel != null) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: MakoloCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(
                            Icons.arrow_outward_rounded,
                            color: Color(0xFF5232DB),
                          ),
                          const SizedBox(width: MakoloSpacing.sm),
                          Text(
                            'Pour avancer',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ],
                      ),
                      const SizedBox(height: MakoloSpacing.sm),
                      Text(presentation.nextActionLabel!),
                      if (action != null) ...[
                        const SizedBox(height: MakoloSpacing.md),
                        action,
                      ],
                    ],
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.lg),
            ],
            if (presentation.rejectedRequests > 0) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: MakoloAttentionBlock(
                  title: 'Une demande a été refusée',
                  body: 'Consultez les informations de votre démarche.',
                  icon: Icons.info_outline_rounded,
                ),
              ),
              const SizedBox(height: MakoloSpacing.lg),
            ],
            if (presentation.pendingRequests > 0 &&
                presentation.waiting.isEmpty &&
                presentation.actorInterventions.isEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: const MakoloCard(
                  child: ListTile(
                    leading: Icon(Icons.hourglass_empty_rounded),
                    title: Text('En attente de réponse'),
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.lg),
            ],
            if (presentation.liveLink != null ||
                presentation.dayOfLink != null) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: MakoloCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            presentation.liveLink != null
                                ? Icons.bolt_rounded
                                : Icons.today_rounded,
                            color: const Color(0xFF5232DB),
                          ),
                          const SizedBox(width: MakoloSpacing.sm),
                          Text(
                            presentation.liveLink != null
                                ? 'Makolo Live'
                                : 'Jour J',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ],
                      ),
                      const SizedBox(height: MakoloSpacing.sm),
                      MakoloActionButton(
                        label: presentation.liveLink != null
                            ? 'Ouvrir Makolo Live'
                            : 'Ouvrir Jour J',
                        onPressed: presentation.liveLink != null
                            ? () => onOpenLive(presentation.liveLink!)
                            : () => onOpenDayOf(presentation.dayOfLink!),
                        appearance: MakoloActionAppearance.primary,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.lg),
            ],
            if (presentation.steps.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Où j’en suis',
                child: _JourneyPath(steps: presentation.steps),
              ),
            ],
            if (!presentation.isTerminal &&
                _hasVisiblePreparation(presentation)) ...[
              MakoloSection(
                title: 'Préparation',
                child: _ReadinessGroups(
                  presentation: presentation,
                  ownerAction: _ownerActionForLink,
                ),
              ),
            ],
            if (presentation.resourcesLink != null &&
                (!resourcesKnown || resourcesPreview.isNotEmpty)) ...[
              const SizedBox(height: MakoloSpacing.md),
              MakoloSection(
                title: 'Pour me préparer',
                child: MakoloCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (final resource in resourcesPreview.take(3))
                        ListTile(
                          dense: true,
                          visualDensity: VisualDensity.compact,
                          contentPadding: EdgeInsets.zero,
                          leading: Icon(
                            _resourceIcon(resource),
                            color: const Color(0xFF5232DB),
                          ),
                          title: Text(resource.title),
                          subtitle: resource.description == null
                              ? null
                              : Text(
                                  resource.description!,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                        ),
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton.icon(
                          onPressed: () =>
                              onOpenResources(presentation.resourcesLink!),
                          icon: const Icon(Icons.arrow_forward_rounded),
                          iconAlignment: IconAlignment.end,
                          label: Text(
                            !resourcesKnown
                                ? 'Voir les documents'
                                : resourcesPreview.length > 3
                                ? 'Voir les ${resourcesPreview.length} ressources'
                                : 'Voir toutes les ressources',
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            if (presentation.forms.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.xl),
              MakoloSection(
                title: 'Formulaires',
                child: Column(
                  children: [
                    for (
                      var index = 0;
                      index < presentation.forms.length;
                      index++
                    ) ...[
                      _FormCard(
                        form: presentation.forms[index],
                        onOpen: onOpenForm,
                      ),
                      if (index < presentation.forms.length - 1)
                        const SizedBox(height: MakoloSpacing.sm),
                    ],
                  ],
                ),
              ),
            ],
            if (presentation.requirements.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.xl),
              MakoloSection(
                title: 'Éléments nécessaires',
                child: Column(
                  children: [
                    for (
                      var index = 0;
                      index < presentation.requirements.length;
                      index++
                    ) ...[
                      _ReferenceCard(
                        reference: presentation.requirements[index],
                        onTap: () =>
                            onOpenRequirement(presentation.requirements[index]),
                      ),
                      if (index < presentation.requirements.length - 1)
                        const SizedBox(height: MakoloSpacing.sm),
                    ],
                  ],
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
            if (presentation.payments.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Paiement',
                child: Column(
                  children: [
                    for (final item in presentation.payments) ...[
                      _JourneyPaymentCard(
                        payment: item,
                        onOpenPaymentObligation: onOpenPaymentObligation,
                        onOpenCommerceOrder: onOpenCommerceOrder,
                      ),
                      const SizedBox(height: MakoloSpacing.sm),
                    ],
                  ],
                ),
              ),
            ],
            if (presentation.activity != null ||
                presentation.occurrence != null) ...[
              const SizedBox(height: MakoloSpacing.xl),
              MakoloSection(
                title: 'Contexte',
                child: Column(
                  children: [
                    if (presentation.activity != null)
                      _ReferenceCard(
                        reference: presentation.activity!,
                        contextLabel: 'Activité',
                        hideRepeatedTitle:
                            presentation.activity!.label == presentation.title,
                        onTap: presentation.activity!.link == null
                            ? null
                            : () => onOpenActivity(presentation.activity!),
                      ),
                    if (presentation.activity != null &&
                        presentation.occurrence != null)
                      const SizedBox(height: MakoloSpacing.sm),
                    if (presentation.occurrence != null)
                      _ReferenceCard(
                        reference: presentation.occurrence!,
                        contextLabel: 'Occurrence',
                        hideRepeatedTitle:
                            presentation.occurrence!.label ==
                            presentation.title,
                        onTap: presentation.occurrence!.link == null
                            ? null
                            : () => onOpenOccurrence(presentation.occurrence!),
                      ),
                  ],
                ),
              ),
            ],
            if (presentation.access != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Accès',
                child: _ReferenceCard(
                  reference: presentation.access!,
                  onTap: presentation.access!.link == null
                      ? null
                      : () => onOpenAccess(presentation.access!),
                ),
              ),
            ],
            if (conversationEntry != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              conversationEntry!,
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

/// Terminal labels are solely the owner Journey state, never an invented
/// success or a percentage computed from unrelated capabilities.
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
          Icon(outcome.$2, size: 28, color: const Color(0xFF5232DB)),
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
  const _JourneyIdentity({required this.presentation});

  final JourneyDetailPresentation presentation;

  IconData get _symbol => switch (presentation.workflowKind) {
    'purchase' => Icons.shopping_bag_outlined,
    'reservation' => Icons.event_available_outlined,
    'registration' => Icons.badge_outlined,
    'invitation' => Icons.mark_email_read_outlined,
    'service' => Icons.handyman_outlined,
    'fulfillment' => Icons.task_alt_outlined,
    'order_approval' => Icons.fact_check_outlined,
    _ => Icons.route_outlined,
  };

  @override
  Widget build(BuildContext context) {
    final state = MakoloHumanization.presentationLabel(
      presentation.journeyState,
    );
    final facts = presentation.practical;
    final civil = JourneyDayPresentation.civilDate(facts?.startDate);
    final date =
        civil ?? (facts?.startAt == null ? null : facts!.startAt!.toLocal());
    final dateLabel = date == null
        ? null
        : MaterialLocalizations.of(context).formatMediumDate(date);
    final timeLabel =
        JourneyDayPresentation.clock(facts?.startTime) ??
        (facts?.startAt == null
            ? null
            : JourneyDayPresentation.clock(
                '${facts!.startAt!.toLocal().hour.toString().padLeft(2, '0')}'
                ':${facts.startAt!.toLocal().minute.toString().padLeft(2, '0')}',
              ));
    final placeLabel = JourneyDayPresentation.place(
      name: facts?.placeName,
      locality: facts?.placeLocality,
    );
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.inner,
        MakoloSpacing.md,
        MakoloSpacing.inner,
        0,
      ),
      child: Container(
        key: const Key('journey-identity'),
        width: double.infinity,
        decoration: BoxDecoration(
          color: const Color(0xFF2B176E),
          borderRadius: BorderRadius.circular(20),
        ),
        padding: const EdgeInsets.all(MakoloSpacing.inner),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(MakoloSpacing.md),
                  decoration: BoxDecoration(
                    color: const Color(0xFF5232DB),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(_symbol, color: Colors.white, size: 27),
                ),
                const SizedBox(width: MakoloSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'MON OBJECTIF',
                        style: TextStyle(
                          color: Color(0xFFD5CCFF),
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.7,
                        ),
                      ),
                      const SizedBox(height: MakoloSpacing.xs),
                      Text(
                        presentation.title,
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                            ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (presentation.summary != null) ...[
              const SizedBox(height: MakoloSpacing.md),
              Text(
                presentation.summary!,
                style: const TextStyle(color: Color(0xFFE6DEFF)),
              ),
            ],
            if (state != null || presentation.kindLabel != 'Démarche') ...[
              const SizedBox(height: MakoloSpacing.md),
              Wrap(
                spacing: MakoloSpacing.md,
                runSpacing: MakoloSpacing.xs,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  if (state != null)
                    _JourneyHeroFact(
                      icon: Icons.circle,
                      label: state,
                      smallIcon: true,
                    ),
                  if (presentation.kindLabel != 'Démarche')
                    Text(
                      presentation.kindLabel,
                      style: const TextStyle(color: Color(0xFFD5CCFF)),
                    ),
                ],
              ),
            ],
            if (dateLabel != null ||
                timeLabel != null ||
                placeLabel != null ||
                civil != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              Container(height: 1, color: const Color(0xFF6F60A4)),
              const SizedBox(height: MakoloSpacing.md),
              Wrap(
                spacing: MakoloSpacing.md,
                runSpacing: MakoloSpacing.md,
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
                  if (civil != null)
                    JourneyDayBadge(occurrenceDate: facts!.startDate!),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _JourneyHeroFact extends StatelessWidget {
  const _JourneyHeroFact({
    required this.icon,
    required this.label,
    this.smallIcon = false,
  });

  final IconData icon;
  final String label;
  final bool smallIcon;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, color: const Color(0xFFDBD2FF), size: smallIcon ? 9 : 18),
      const SizedBox(width: MakoloSpacing.xs),
      Flexible(
        child: Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    ],
  );
}

/// JourneySteps are shown as facts, not a locally computed percentage/timeline.
/// Dependencies are named only when the owner supplied both linked steps.
class _JourneyPath extends StatelessWidget {
  const _JourneyPath({required this.steps});

  final List<JourneyStepSummary> steps;

  @override
  Widget build(BuildContext context) {
    final current = steps.where((step) => !step.isTerminal).toList();
    final previous = steps.where((step) => step.isTerminal).toList();
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final step in current)
            _JourneyStepRow(step: step, allSteps: steps),
          if (previous.isNotEmpty && current.isNotEmpty)
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              leading: const Icon(
                Icons.check_circle_outline_rounded,
                color: Color(0xFF5232DB),
              ),
              title: Text(
                '${previous.length} étape${previous.length > 1 ? 's' : ''} passée${previous.length > 1 ? 's' : ''}',
              ),
              children: [
                for (final step in previous)
                  _JourneyStepRow(step: step, allSteps: steps),
              ],
            ),
          if (current.isEmpty)
            for (final step in previous)
              _JourneyStepRow(step: step, allSteps: steps),
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
      leading: Icon(icon, color: const Color(0xFF5232DB)),
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

bool _hasVisiblePreparation(JourneyDetailPresentation presentation) {
  return presentation.ready.isNotEmpty ||
      presentation.blockers.isNotEmpty ||
      presentation.waiting.isNotEmpty ||
      presentation.actorInterventions.any(
        (item) => _showReadinessItem(presentation, item),
      );
}

class _ReadinessGroups extends StatelessWidget {
  const _ReadinessGroups({
    required this.presentation,
    required this.ownerAction,
  });

  final JourneyDetailPresentation presentation;
  final Widget? Function(String label, String? link) ownerAction;

  @override
  Widget build(BuildContext context) {
    final interventions = presentation.actorInterventions
        .where((item) => _showReadinessItem(presentation, item))
        .toList();
    final groups = <(String, List<JourneyReadinessItem>, IconData)>[
      ('Bloque la suite', presentation.blockers, Icons.warning_amber_rounded),
      ('De votre côté', interventions, Icons.touch_app_outlined),
      ('En attente', presentation.waiting, Icons.hourglass_empty_rounded),
    ].where((item) => item.$2.isNotEmpty).toList();
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var index = 0; index < groups.length; index++) ...[
            if (index > 0) const Divider(height: MakoloSpacing.lg),
            Row(
              children: [
                Icon(
                  groups[index].$3,
                  size: 21,
                  color: const Color(0xFF5232DB),
                ),
                const SizedBox(width: MakoloSpacing.sm),
                Expanded(
                  child: Text(
                    groups[index].$1,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: MakoloSpacing.xs),
            for (final item in groups[index].$2)
              Padding(
                padding: const EdgeInsets.only(
                  left: 30,
                  top: MakoloSpacing.xs,
                  bottom: MakoloSpacing.xs,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(item.summary),
                    if (item.nextLabel != null &&
                        item.nextLink != presentation.nextActionLink) ...[
                      const SizedBox(height: MakoloSpacing.sm),
                      if (ownerAction(item.nextLabel!, item.nextLink)
                          case final action?)
                        action,
                    ],
                  ],
                ),
              ),
          ],
          if (presentation.ready.isNotEmpty) ...[
            if (groups.isNotEmpty) const Divider(height: MakoloSpacing.lg),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              leading: const Icon(
                Icons.check_circle_outline_rounded,
                color: Color(0xFF5232DB),
              ),
              title: Text(
                '${presentation.ready.length} élément${presentation.ready.length > 1 ? 's' : ''} en ordre',
              ),
              children: [
                for (final item in presentation.ready)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(
                      Icons.check_rounded,
                      color: Color(0xFF5232DB),
                    ),
                    title: Text(item.summary),
                  ),
              ],
            ),
          ],
        ],
      ),
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
              leading: const Icon(
                Icons.directions_outlined,
                color: Color(0xFF5232DB),
              ),
              title: const Text('Adresse'),
              subtitle: Text(additionalPlace),
            ),
          if (endLabel.isNotEmpty)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(
                Icons.event_available_outlined,
                color: Color(0xFF5232DB),
              ),
              title: const Text('Fin prévue'),
              subtitle: Text(endLabel),
            ),
          if (facts.accessInstructions?.trim().isNotEmpty == true)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(
                Icons.info_outline_rounded,
                color: Color(0xFF5232DB),
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
    return MakoloCard(
      onTap: open,
      child: ListTile(
        contentPadding: EdgeInsets.zero,
        leading: const Icon(
          Icons.account_balance_wallet_outlined,
          color: Color(0xFF5232DB),
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
      ),
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
    return MakoloCard(
      onTap: form.detailLink.isEmpty ? null : () => onOpen(form),
      child: ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(
          form.canComplete ? Icons.edit_document : Icons.description_outlined,
          color: const Color(0xFF5232DB),
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
      ),
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
    return MakoloCard(
      onTap: onTap,
      child: ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(symbol, color: const Color(0xFF5232DB)),
        title: Text(title),
        subtitle: subtitle.isEmpty ? null : Text(subtitle),
        trailing: onTap == null
            ? null
            : const Icon(Icons.chevron_right_rounded),
      ),
    );
  }
}
