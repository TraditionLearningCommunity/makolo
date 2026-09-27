import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../sync/sync_status.dart';
import 'makolo_theme.dart';

class MakoloSkeleton extends StatelessWidget {
  const MakoloSkeleton({super.key, this.lines = 4, this.lineHeight = 16});

  final int lines;
  final double lineHeight;

  @override
  Widget build(BuildContext context) {
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final color = Theme.of(context).colorScheme.surfaceContainerHighest
        .withValues(alpha: 0.7);

    return Semantics(
      label: 'Chargement du contenu',
      liveRegion: true,
      child: ExcludeSemantics(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: List.generate(lines, (index) {
              final widthFactor = index == lines - 1 ? 0.58 : 1.0;
              return Padding(
                padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                child: AnimatedContainer(
                  duration: reduceMotion ? Duration.zero : MakoloMotion.short,
                  height: lineHeight,
                  width: double.infinity,
                  constraints: const BoxConstraints(minWidth: 48),
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(MakoloRadii.small),
                  ),
                  child: FractionallySizedBox(
                    widthFactor: widthFactor,
                    alignment: Alignment.centerLeft,
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}

enum SuccessFeedbackKind { savedOnDevice, pendingSync, synced, confirmed }

class SuccessFeedback extends StatelessWidget {
  const SuccessFeedback({super.key, required this.kind, this.compact = false});

  final SuccessFeedbackKind kind;
  final bool compact;

  String get _label => switch (kind) {
    SuccessFeedbackKind.savedOnDevice => 'Enregistré sur cet appareil',
    SuccessFeedbackKind.pendingSync => 'En attente de synchronisation',
    SuccessFeedbackKind.synced => 'Synchronisé',
    SuccessFeedbackKind.confirmed => 'Confirmé',
  };

  IconData get _icon => switch (kind) {
    SuccessFeedbackKind.savedOnDevice => Icons.save_outlined,
    SuccessFeedbackKind.pendingSync => Icons.schedule_outlined,
    SuccessFeedbackKind.synced => Icons.cloud_done_outlined,
    SuccessFeedbackKind.confirmed => Icons.check_circle_outline,
  };

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    label: _label,
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(_icon, size: compact ? 16 : 20),
        const SizedBox(width: MakoloSpacing.sm),
        Flexible(child: Text(_label)),
      ],
    ),
  );
}

enum MakoloNoticeKind { info, success, warning, error }

enum MakoloNoticeBehavior { transient, persistent }

class MakoloNotice extends StatelessWidget {
  const MakoloNotice({
    super.key,
    required this.message,
    this.kind = MakoloNoticeKind.info,
    this.behavior = MakoloNoticeBehavior.transient,
    this.onDismiss,
    this.actionLabel,
    this.onAction,
    this.liveRegion = true,
  });

  final String message;
  final MakoloNoticeKind kind;
  final MakoloNoticeBehavior behavior;
  final VoidCallback? onDismiss;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool liveRegion;

  Color _accent(BuildContext context) {
    final surfaces = context.makoloSurfaces;
    return switch (kind) {
      MakoloNoticeKind.info => surfaces.info,
      MakoloNoticeKind.success => surfaces.success,
      MakoloNoticeKind.warning => surfaces.warning,
      MakoloNoticeKind.error => Theme.of(context).colorScheme.error,
    };
  }

  IconData get _icon => switch (kind) {
    MakoloNoticeKind.info => Icons.info_outline,
    MakoloNoticeKind.success => Icons.check_circle_outline,
    MakoloNoticeKind.warning => Icons.warning_amber_rounded,
    MakoloNoticeKind.error => Icons.error_outline,
  };

  String get _semanticKind => switch (kind) {
    MakoloNoticeKind.info => 'Information',
    MakoloNoticeKind.success => 'Succès',
    MakoloNoticeKind.warning => 'Attention',
    MakoloNoticeKind.error => 'Erreur',
  };

  @override
  Widget build(BuildContext context) {
    final accent = _accent(context);
    final dismissible =
        behavior == MakoloNoticeBehavior.persistent && onDismiss != null;
    final hasInteractiveChild =
        dismissible || (actionLabel != null && onAction != null);
    return Semantics(
      container: true,
      liveRegion: liveRegion,
      label: '$_semanticKind. $message',
      excludeSemantics: !hasInteractiveChild,
      child: AnimatedContainer(
        duration: MakoloMotion.effective(context, MakoloMotion.short),
        padding: const EdgeInsets.symmetric(
          horizontal: MakoloSpacing.md,
          vertical: MakoloSpacing.sm,
        ),
        decoration: BoxDecoration(
          color: context.makoloSurfaces.raised,
          border: Border.all(color: accent.withValues(alpha: 0.28)),
          borderRadius: BorderRadius.circular(MakoloRadii.medium),
          boxShadow: [
            BoxShadow(
              color: Theme.of(context).colorScheme.shadow
                  .withValues(alpha: 0.06),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            ExcludeSemantics(child: Icon(_icon, color: accent, size: 20)),
            const SizedBox(width: MakoloSpacing.sm),
            Expanded(
              child: Text(
                message,
                style: Theme.of(context).textTheme.bodyMedium
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(width: MakoloSpacing.xs),
              TextButton(onPressed: onAction, child: Text(actionLabel!)),
            ],
            if (dismissible)
              IconButton(
                tooltip: 'Fermer',
                constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                onPressed: onDismiss,
                icon: const Icon(Icons.close, size: 18),
              ),
          ],
        ),
      ),
    );
  }
}

class NetworkStateIndicator extends StatelessWidget {
  const NetworkStateIndicator({super.key, required this.status});

  final SyncStatus status;

  String get _label => switch (status.state) {
    SyncVisualState.synced => 'À jour',
    SyncVisualState.syncing => 'Mise à jour…',
    SyncVisualState.pending =>
      status.pendingCount > 1
          ? '${status.pendingCount} actions en attente de synchronisation'
          : 'En attente de synchronisation',
    SyncVisualState.offline =>
      'Hors connexion · Ce qui est déjà disponible reste utilisable.',
    SyncVisualState.conflict => 'Une modification demande votre attention.',
    SyncVisualState.failed => 'Impossible de mettre à jour pour le moment.',
    SyncVisualState.stale => 'Données disponibles, vérification nécessaire.',
  };

  MakoloNoticeKind get _kind => switch (status.state) {
    SyncVisualState.synced ||
    SyncVisualState.syncing ||
    SyncVisualState.pending => MakoloNoticeKind.info,
    SyncVisualState.offline ||
    SyncVisualState.conflict ||
    SyncVisualState.stale => MakoloNoticeKind.warning,
    SyncVisualState.failed => MakoloNoticeKind.error,
  };

  @override
  Widget build(BuildContext context) {
    if (status.state == SyncVisualState.synced) {
      return const SizedBox.shrink();
    }
    if (status.state == SyncVisualState.syncing) {
      return Align(
        alignment: Alignment.centerLeft,
        child: Semantics(
          liveRegion: true,
          label: 'Information. Mise à jour en cours',
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: context.makoloSurfaces.info.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(MakoloRadii.pill),
              border: Border.all(
                color: context.makoloSurfaces.info.withValues(alpha: 0.24),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.sm,
                vertical: MakoloSpacing.xs,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.sync_rounded,
                    size: 16,
                    color: context.makoloSurfaces.info,
                  ),
                  const SizedBox(width: MakoloSpacing.xs),
                  Text(
                    'Mise à jour…',
                    style: TextStyle(
                      color: context.makoloSurfaces.info,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }
    return MakoloNotice(
      message: _label,
      kind: _kind,
      behavior: status.state == SyncVisualState.conflict
          ? MakoloNoticeBehavior.persistent
          : MakoloNoticeBehavior.transient,
    );
  }
}

ScaffoldFeatureController<SnackBar, SnackBarClosedReason> showMakoloNotice(
  BuildContext context,
  String message, {
  MakoloNoticeKind kind = MakoloNoticeKind.info,
  MakoloNoticeBehavior behavior = MakoloNoticeBehavior.transient,
  Duration duration = const Duration(seconds: 3),
  String? actionLabel,
  VoidCallback? onAction,
}) {
  final messenger = ScaffoldMessenger.of(context);
  messenger.hideCurrentSnackBar();
  late ScaffoldFeatureController<SnackBar, SnackBarClosedReason> controller;
  controller = messenger.showSnackBar(
    SnackBar(
      backgroundColor: Colors.transparent,
      elevation: 0,
      behavior: SnackBarBehavior.floating,
      margin: const EdgeInsets.all(MakoloSpacing.md),
      padding: EdgeInsets.zero,
      duration: behavior == MakoloNoticeBehavior.persistent
          ? const Duration(days: 365)
          : duration,
      content: MakoloNotice(
        message: message,
        kind: kind,
        behavior: behavior,
        onDismiss: behavior == MakoloNoticeBehavior.persistent
            ? () => controller.close()
            : null,
        actionLabel: actionLabel,
        onAction: onAction == null
            ? null
            : () {
                controller.close();
                onAction();
              },
      ),
    ),
  );
  return controller;
}

void showMakoloToast(
  BuildContext context,
  String message, {
  Duration duration = const Duration(seconds: 3),
  MakoloNoticeKind kind = MakoloNoticeKind.info,
}) {
  showMakoloNotice(context, message, kind: kind, duration: duration);
}

void showMakoloUndoToast(
  BuildContext context, {
  required String message,
  required VoidCallback onUndo,
  String undoLabel = 'Annuler',
}) {
  showMakoloNotice(
    context,
    message,
    kind: MakoloNoticeKind.info,
    actionLabel: undoLabel,
    onAction: onUndo,
  );
}

Future<bool> showMakoloConfirmationDialog(
  BuildContext context, {
  required String title,
  required String message,
  String confirmLabel = 'Confirmer',
  String cancelLabel = 'Annuler',
  bool destructive = false,
}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(cancelLabel),
        ),
        FilledButton(
          style: destructive
              ? FilledButton.styleFrom(
                  backgroundColor: Theme.of(context).colorScheme.error,
                )
              : null,
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  return result ?? false;
}

Future<T?> showMakoloBottomSheet<T>(
  BuildContext context, {
  required WidgetBuilder builder,
}) {
  return showModalBottomSheet<T>(
    context: context,
    useSafeArea: true,
    isScrollControlled: true,
    showDragHandle: true,
    builder: builder,
  );
}

class PermissionExplainer extends StatelessWidget {
  const PermissionExplainer({
    super.key,
    required this.title,
    required this.message,
    required this.actionLabel,
    required this.onContinue,
    this.denied = false,
    this.deniedMessage,
  });

  final String title;
  final String message;
  final String actionLabel;
  final VoidCallback onContinue;
  final bool denied;
  final String? deniedMessage;

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    child: Padding(
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: MakoloSpacing.sm),
          Text(message),
          if (denied) ...[
            const SizedBox(height: MakoloSpacing.md),
            Text(
              deniedMessage ?? 'Cette autorisation est refusée. Vous pouvez continuer sans cette fonction et la réactiver plus tard si nécessaire.',
            ),
          ],
          const SizedBox(height: MakoloSpacing.lg),
          FilledButton(onPressed: onContinue, child: Text(actionLabel)),
        ],
      ),
    ),
  );
}

abstract final class MakoloHaptics {
  static Future<void> selection() => HapticFeedback.selectionClick();
  static Future<void> success() => HapticFeedback.lightImpact();
  static Future<void> warning() => HapticFeedback.mediumImpact();
}
