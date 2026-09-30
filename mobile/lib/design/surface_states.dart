import 'package:flutter/material.dart';

import 'behavior_primitives.dart';
import 'behavior_states.dart';
import 'makolo_theme.dart';

/// Presentation-only contract consumed after KA selection/adaptation.
/// Presentation-only availability. The owner/KA layers decide which value is
/// true; EF only renders it.
enum MakoloAvailabilityCue { initial, loading, content, empty }

/// Presentation-only freshness. This must never be inferred from reachability.
enum MakoloFreshnessCue {
  unknown,
  current,
  oldObservation,
  refreshRecommended,
  revalidationRequired,
  expired,
}

/// Presentation-only reachability of the remote owner/source.
enum MakoloReachabilityCue { unknown, reachable, temporarilyUnavailable }

/// Presentation-only authority already decided by the relevant owner/capability.
enum MakoloAuthorityCue {
  unknown,
  allowed,
  remoteConfirmationRequired,
  notAllowed,
}

/// Presentation-only lifecycle of a user intention/result.
enum MakoloCommitCue {
  none,
  savedOnDevice,
  pending,
  awaitingConfirmation,
  confirmed,
  conflict,
  failed,
}

/// Presentation-only failure severity. Business authority remains upstream.
enum MakoloFailureCue { none, recoverable, blocking, permissionDenied }

@immutable
class MakoloSurfacePresentation {
  const MakoloSurfacePresentation({
    required this.availability,
    this.freshness = MakoloFreshnessCue.unknown,
    this.reachability = MakoloReachabilityCue.unknown,
    this.authority = MakoloAuthorityCue.unknown,
    this.commit = MakoloCommitCue.none,
    this.failure = MakoloFailureCue.none,
    this.refreshing = false,
  });

  final MakoloAvailabilityCue availability;
  final MakoloFreshnessCue freshness;
  final MakoloReachabilityCue reachability;
  final MakoloAuthorityCue authority;
  final MakoloCommitCue commit;
  final MakoloFailureCue failure;
  final bool refreshing;

  bool get hasUsableContent => availability == MakoloAvailabilityCue.content;
}

/// Keeps already-usable content visible while refresh and degraded-state cues
/// are rendered around it. It deliberately contains no freshness calculation,
/// network probing, permission decision or domain rule.
class MakoloSurfaceStateView extends StatelessWidget {
  const MakoloSurfaceStateView({
    super.key,
    required this.state,
    required this.content,
    this.empty,
    this.initialLoading,
    this.recoverableErrorMessage,
    this.blockingErrorMessage,
    this.preservedMessage,
    this.onRetry,
    this.permissionDeniedMessage =
        'Vous n’avez pas l’autorisation nécessaire pour cette action.',
  });

  final MakoloSurfacePresentation state;
  final Widget content;
  final Widget? empty;
  final Widget? initialLoading;
  final String? recoverableErrorMessage;
  final String? blockingErrorMessage;
  final String? preservedMessage;
  final VoidCallback? onRetry;
  final String permissionDeniedMessage;

  @override
  Widget build(BuildContext context) {
    if (state.failure == MakoloFailureCue.permissionDenied) {
      return MakoloEmptyState(
        title: 'Action non disponible',
        body: permissionDeniedMessage,
        icon: Icons.lock_outline,
      );
    }

    if (state.failure == MakoloFailureCue.blocking) {
      return MakoloErrorState(
        message:
            blockingErrorMessage ?? 'Impossible de continuer pour le moment.',
        preservedMessage: preservedMessage,
        onRetry: onRetry,
      );
    }

    if (!state.hasUsableContent) {
      switch (state.availability) {
        case MakoloAvailabilityCue.initial:
        case MakoloAvailabilityCue.loading:
          return initialLoading ?? const MakoloSkeleton(lines: 5);
        case MakoloAvailabilityCue.empty:
          return empty ??
              const MakoloEmptyState(title: 'Rien à afficher pour le moment');
        case MakoloAvailabilityCue.content:
          break;
      }
    }

    final cues = <Widget>[
      if (state.refreshing) const MakoloRefreshIndicator(),
      if (state.failure == MakoloFailureCue.recoverable)
        MakoloNotice(
          message: recoverableErrorMessage ?? 'La mise à jour n’a pas abouti. Le contenu disponible est conservé.',
          kind: MakoloNoticeKind.error,
          behavior: MakoloNoticeBehavior.persistent,
          liveRegion: true,
        ),
      if (state.freshness != MakoloFreshnessCue.unknown &&
          state.freshness != MakoloFreshnessCue.current)
        MakoloFreshnessNotice(freshness: state.freshness),
      if (state.reachability == MakoloReachabilityCue.temporarilyUnavailable)
        const MakoloNotice(
          message: 'La source distante est momentanément indisponible. Le contenu déjà disponible reste utilisable.',
          kind: MakoloNoticeKind.warning,
        ),
      if (state.commit != MakoloCommitCue.none)
        MakoloCommitIndicator(commit: state.commit),
    ];

    if (cues.isEmpty) return content;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final cue in cues) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.md,
              MakoloSpacing.sm,
              MakoloSpacing.md,
              0,
            ),
            child: cue,
          ),
        ],
        Expanded(child: content),
      ],
    );
  }
}

class MakoloRefreshIndicator extends StatelessWidget {
  const MakoloRefreshIndicator({super.key, this.label = 'Mise à jour…'});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      liveRegion: true,
      label: label,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: MakoloSpacing.sm),
          Flexible(
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class MakoloFreshnessNotice extends StatelessWidget {
  const MakoloFreshnessNotice({super.key, required this.freshness});

  final MakoloFreshnessCue freshness;

  String get _message {
    return switch (freshness) {
      MakoloFreshnessCue.unknown => '',
      MakoloFreshnessCue.current => '',
      MakoloFreshnessCue.oldObservation =>
        'Données plus anciennes, encore disponibles pour consultation.',
      MakoloFreshnessCue.refreshRecommended =>
        'Une mise à jour est recommandée lorsque la source est joignable.',
      MakoloFreshnessCue.revalidationRequired =>
        'Une vérification distante est nécessaire avant l’action.',
      MakoloFreshnessCue.expired =>
        'Cette observation a expiré. Une revalidation distante est nécessaire avant de continuer.',
    };
  }

  @override
  Widget build(BuildContext context) {
    if (freshness == MakoloFreshnessCue.unknown ||
        freshness == MakoloFreshnessCue.current) {
      return const SizedBox.shrink();
    }
    final requiresRevalidation =
        freshness == MakoloFreshnessCue.revalidationRequired ||
        freshness == MakoloFreshnessCue.expired;
    return MakoloNotice(
      message: _message,
      kind: requiresRevalidation
          ? MakoloNoticeKind.warning
          : MakoloNoticeKind.info,
      behavior: requiresRevalidation
          ? MakoloNoticeBehavior.persistent
          : MakoloNoticeBehavior.transient,
    );
  }
}

class MakoloCommitIndicator extends StatelessWidget {
  const MakoloCommitIndicator({super.key, required this.commit});

  final MakoloCommitCue commit;

  @override
  Widget build(BuildContext context) {
    return switch (commit) {
      MakoloCommitCue.none => const SizedBox.shrink(),
      MakoloCommitCue.savedOnDevice => const SuccessFeedback(
        kind: SuccessFeedbackKind.savedOnDevice,
      ),
      MakoloCommitCue.pending => const PendingIndicator(),
      MakoloCommitCue.awaitingConfirmation => const PendingIndicator(
        label: 'En attente de confirmation',
      ),
      MakoloCommitCue.confirmed => const SuccessFeedback(
        kind: SuccessFeedbackKind.confirmed,
      ),
      MakoloCommitCue.conflict => const MakoloNotice(
        message: 'Une modification demande votre attention.',
        kind: MakoloNoticeKind.warning,
        behavior: MakoloNoticeBehavior.persistent,
      ),
      MakoloCommitCue.failed => const MakoloNotice(
        message: 'Cette action n’a pas pu être confirmée.',
        kind: MakoloNoticeKind.error,
        behavior: MakoloNoticeBehavior.persistent,
      ),
    };
  }
}
